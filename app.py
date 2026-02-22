"""
ARTLU.RUN - Ultra Race Training Analysis Platform
==================================================
Flask web app for personalized ultramarathon race strategy.

Architecture:
  - models.py        → Database schema and data operations
  - email_service.py → Gmail SMTP email sending
  - app.py           → Routes, Stripe integration, view logic (this file)
  - templates/       → Jinja2 HTML templates
  - static/          → CSS, JS, images

Environment variables (see .env.example):
  FLASK_SECRET_KEY, STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY,
  STRIPE_WEBHOOK_SECRET, EMAIL_USERNAME, EMAIL_PASSWORD
"""

import os
import json
from dotenv import load_dotenv
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, flash, session)
import stripe

from models import (init_db, seed_races, get_all_races, get_race_by_slug,
                    get_race_sections, create_purchase, get_purchase_by_code,
                    get_purchases_by_email, mark_report_ready, create_race_request,
                    get_race_content, get_premium_data, save_premium_data,
                    get_purchase_for_race, save_race_content, create_or_update_race,
                    save_gpx_data)
from email_service import (send_access_code_email, send_order_notification)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Stripe configuration
# Only treat as configured if key looks like a real Stripe key (sk_test_... or sk_live_...)
_stripe_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_CONFIGURED = _stripe_key.startswith('sk_test_') or _stripe_key.startswith('sk_live_')
if STRIPE_CONFIGURED:
    stripe.api_key = _stripe_key
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'vonrexroad@gmail.com')

# Price in cents ($39.00)
PLAN_PRICE_CENTS = 3900
PLAN_PRICE_DISPLAY = '$39'


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    """Make common variables available in all templates."""
    return {
        'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY,
        'plan_price': PLAN_PRICE_DISPLAY,
        'plan_price_cents': PLAN_PRICE_CENTS,
        'current_year': 2026,
    }


# ======================================================================
# PUBLIC ROUTES
# ======================================================================

@app.route('/')
def landing():
    """Landing page with hero, features, sample, and popular races."""
    races = get_all_races()
    # Show first 4 races on landing page
    featured = list(races)[:4]
    return render_template('landing.html', featured_races=featured)


@app.route('/races')
def race_browser():
    """Browse all configured races with cards, search, and filters."""
    races = get_all_races()
    return render_template('race_browser.html', races=races)


@app.route('/race/<slug>')
def race_page(slug):
    """Individual free race page with course overview and purchase CTA."""
    race = get_race_by_slug(slug)
    if not race:
        return render_template('404.html', message='Race not found'), 404

    sections = get_race_sections(race['id'])

    # Parse elevation profile for the chart
    elevation_data = []
    if race['elevation_profile_json']:
        try:
            elevation_data = json.loads(race['elevation_profile_json'])
        except (json.JSONDecodeError, TypeError):
            pass

    # Get rich race content if available
    race_content = None
    if race['race_content_json']:
        race_content = get_race_content(race['id'])

    # Check if logged-in user has purchased this race
    user_email = session.get('user_email')
    purchase = None
    premium_data = None
    if user_email:
        purchase = get_purchase_for_race(user_email, race['id'])
        if purchase and purchase['premium_data_json']:
            premium_data = get_premium_data(purchase['id'])

    return render_template('race_page.html',
                           race=race,
                           sections=sections,
                           elevation_data=json.dumps(elevation_data),
                           race_content=race_content,
                           purchase=purchase,
                           premium_data=premium_data)


# ======================================================================
# PURCHASE FLOW
# ======================================================================

@app.route('/race/<slug>/purchase')
def purchase_page(slug):
    """Purchase form for a personalized race plan."""
    race = get_race_by_slug(slug)
    if not race:
        return render_template('404.html', message='Race not found'), 404
    return render_template('purchase.html', race=race)


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe Checkout session and redirect to payment."""
    race_slug = request.form.get('race_slug', '')
    race_name = request.form.get('race_name', '')
    user_email = request.form.get('email', '')
    user_name = request.form.get('name', '')
    goal_time = request.form.get('goal_time', '')
    city = request.form.get('city', '')
    state = request.form.get('state', '')

    if not user_email or not race_name:
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('purchase_page', slug=race_slug))

    # If Stripe isn't configured, create purchase directly (dev mode)
    if not STRIPE_CONFIGURED:
        race = get_race_by_slug(race_slug)
        race_id = race['id'] if race else None
        access_code = create_purchase(
            email=user_email, name=user_name, race_id=race_id,
            race_name=race_name, goal_time=goal_time, city=city, state=state
        )
        send_access_code_email(user_email, user_name, race_name, access_code)
        send_order_notification(ADMIN_EMAIL, {
            'name': user_name, 'email': user_email, 'race_name': race_name,
            'goal_time': goal_time, 'city': city, 'state': state
        })
        # Auto-login and redirect to the race page in "building" state
        session['user_email'] = user_email
        return redirect(url_for('race_page', slug=race_slug, purchased=1, code=access_code))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Personalized Race Plan — {race_name}',
                        'description': f'Custom pacing, training segments near {city}, {state}, and race strategy',
                    },
                    'unit_amount': PLAN_PRICE_CENTS,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + f'race/{race_slug}/purchase?cancelled=1',
            customer_email=user_email,
            metadata={
                'race_slug': race_slug,
                'race_name': race_name,
                'email': user_email,
                'name': user_name,
                'goal_time': goal_time,
                'city': city,
                'state': state,
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f'Payment error: {str(e)}', 'error')
        return redirect(url_for('purchase_page', slug=race_slug))


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhook events.
    Called by Stripe after successful payment.
    Creates purchase record, sends access code email, notifies admin.
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        sess = event['data']['object']
        meta = sess.get('metadata', {})

        race = get_race_by_slug(meta.get('race_slug', ''))
        race_id = race['id'] if race else None

        access_code = create_purchase(
            email=meta.get('email', ''),
            name=meta.get('name', ''),
            race_id=race_id,
            race_name=meta.get('race_name', ''),
            goal_time=meta.get('goal_time', ''),
            city=meta.get('city', ''),
            state=meta.get('state', ''),
            stripe_payment_id=sess.get('payment_intent'),
            stripe_session_id=sess.get('id'),
        )

        # Send access code email to customer
        send_access_code_email(
            meta.get('email', ''),
            meta.get('name', ''),
            meta.get('race_name', ''),
            access_code
        )

        # Notify admin about new order
        send_order_notification(ADMIN_EMAIL, meta)

    return 'Success', 200


@app.route('/success')
def success():
    """Payment success — auto-login and redirect to race page in building state."""
    access_code = request.args.get('access_code', '')
    session_id = request.args.get('session_id', '')

    # If coming from Stripe, look up the session to get metadata
    if session_id and STRIPE_CONFIGURED:
        try:
            stripe_sess = stripe.checkout.Session.retrieve(session_id)
            meta = stripe_sess.get('metadata', {})
            email = meta.get('email', '')
            race_slug = meta.get('race_slug', '')
            if email:
                session['user_email'] = email
            if race_slug:
                return redirect(url_for('race_page', slug=race_slug, purchased=1))
        except Exception:
            pass

    # Fallback to generic success page
    return render_template('success.html', access_code=access_code)


@app.route('/cancel')
def cancel():
    """Payment cancelled page."""
    return render_template('cancel.html')


# ======================================================================
# USER DASHBOARD
# ======================================================================

@app.route('/dashboard')
def dashboard():
    """User dashboard — login form or purchased reports."""
    # Check if user is "logged in" via session
    if session.get('user_email'):
        purchases = get_purchases_by_email(session['user_email'])
        return render_template('dashboard.html',
                               purchases=purchases,
                               user_email=session['user_email'])
    return render_template('dashboard_login.html')


@app.route('/dashboard/login', methods=['POST'])
def dashboard_login():
    """Authenticate user with email + access code."""
    email = request.form.get('email', '').strip()
    access_code = request.form.get('access_code', '').strip().upper()

    if not email or not access_code:
        flash('Please enter both email and access code.', 'error')
        return redirect(url_for('dashboard'))

    purchase = get_purchase_by_code(email, access_code)
    if purchase:
        session['user_email'] = email
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid email or access code. Please try again.', 'error')
        return redirect(url_for('dashboard'))


@app.route('/dashboard/logout')
def dashboard_logout():
    """Clear session and redirect to landing."""
    session.pop('user_email', None)
    return redirect(url_for('landing'))


@app.route('/dashboard/report/<int:purchase_id>')
def view_report(purchase_id):
    """View a specific purchased report (premium content)."""
    if not session.get('user_email'):
        return redirect(url_for('dashboard'))

    purchases = get_purchases_by_email(session['user_email'])
    purchase = None
    for p in purchases:
        if p['id'] == purchase_id:
            purchase = p
            break

    if not purchase:
        flash('Report not found.', 'error')
        return redirect(url_for('dashboard'))

    race = get_race_by_slug(purchase['race_name'].lower().replace(' ', '-').replace("'", ''))
    return render_template('report.html', purchase=purchase, race=race)


# ======================================================================
# RACE REQUESTS
# ======================================================================

@app.route('/request-race', methods=['POST'])
def request_race():
    """Handle user-submitted race requests."""
    email = request.form.get('email', '')
    race_name = request.form.get('race_name', '')
    race_url = request.form.get('race_url', '')
    notes = request.form.get('notes', '')

    if not race_name:
        return jsonify({'error': 'Race name is required'}), 400

    create_race_request(email, race_name, race_url, notes)
    return jsonify({'success': True, 'message': 'Thanks! We\'ll look into adding this race.'})


# ======================================================================
# PREMIUM DATA API
# ======================================================================

@app.route('/api/premium-data/<int:purchase_id>', methods=['POST'])
def receive_premium_data(purchase_id):
    """Receive premium data from OpenClaw skill."""
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.getenv('OPENCLAW_API_KEY', 'dev-key'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    save_premium_data(purchase_id, json.dumps(data))
    mark_report_ready(purchase_id)

    return jsonify({'success': True})


@app.route('/api/my-premium/<slug>')
def get_my_premium(slug):
    """Return premium data status for logged-in user's purchased race.
    Returns: {status: 'none'|'building'|'ready', data: {...}}
    """
    if not session.get('user_email'):
        return jsonify({'status': 'none', 'unlocked': False})

    race = get_race_by_slug(slug)
    if not race:
        return jsonify({'status': 'none', 'unlocked': False})

    purchase = get_purchase_for_race(session['user_email'], race['id'])
    if not purchase:
        return jsonify({'status': 'none', 'unlocked': False})

    # Purchased but no premium data yet = building
    if not purchase['premium_data_json']:
        return jsonify({
            'status': 'building',
            'unlocked': False,
            'purchase_id': purchase['id'],
            'purchased_at': purchase['created_at']
        })

    # Premium data exists = ready
    try:
        premium_data = json.loads(purchase['premium_data_json'])
        return jsonify({
            'status': 'ready',
            'unlocked': True,
            'data': premium_data
        })
    except (json.JSONDecodeError, TypeError):
        return jsonify({'status': 'building', 'unlocked': False})


# ======================================================================
# OPENCLAW CONTENT APIs
# ======================================================================

@app.route('/api/race-content/<slug>', methods=['POST'])
def receive_race_content(slug):
    """
    Receive free race content from OpenClaw skill.
    This populates the detailed course breakdown, weather, strategy tips,
    essentials checklist, training targets, and finisher tips.
    """
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.getenv('OPENCLAW_API_KEY', 'dev-key'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    success = save_race_content(slug, data)
    if not success:
        return jsonify({'error': 'Race not found', 'slug': slug}), 404

    return jsonify({'success': True, 'slug': slug})


@app.route('/api/race-gpx/<slug>', methods=['POST'])
def receive_race_gpx(slug):
    """
    Receive GPX data for a race. Parses GPX to auto-generate
    elevation profile, distance, and elevation gain stats.
    Accepts either raw GPX XML in body or JSON with a 'gpx' field.
    """
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.getenv('OPENCLAW_API_KEY', 'dev-key'):
        return jsonify({'error': 'Unauthorized'}), 401

    # Accept GPX as raw XML or as JSON {"gpx": "<xml>..."}
    content_type = request.content_type or ''
    if 'application/json' in content_type:
        data = request.get_json()
        if not data or 'gpx' not in data:
            return jsonify({'error': 'JSON body must include "gpx" field with GPX XML'}), 400
        gpx_xml = data['gpx']
    else:
        gpx_xml = request.get_data(as_text=True)
        if not gpx_xml:
            return jsonify({'error': 'No GPX data provided'}), 400

    result = save_gpx_data(slug, gpx_xml)
    if result is None:
        return jsonify({'error': 'Race not found or GPX has no elevation data', 'slug': slug}), 404

    return jsonify({'success': True, 'slug': slug, **result})


@app.route('/api/race', methods=['POST'])
def create_race():
    """
    Create a new race or update an existing one.
    Allows OpenClaw to add races dynamically.
    """
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.getenv('OPENCLAW_API_KEY', 'dev-key'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or 'slug' not in data or 'name' not in data:
        return jsonify({'error': 'slug and name required'}), 400

    race_id = create_or_update_race(data)
    return jsonify({'success': True, 'race_id': race_id, 'slug': data['slug']})


@app.route('/api/races', methods=['GET'])
def list_races_api():
    """
    List all races with their content status.
    Useful for OpenClaw to know which races need content.
    """
    api_key = request.headers.get('X-API-Key', '')
    if api_key != os.getenv('OPENCLAW_API_KEY', 'dev-key'):
        return jsonify({'error': 'Unauthorized'}), 401

    races = get_all_races()
    return jsonify([{
        'slug': r['slug'],
        'name': r['name'],
        'distance': r['distance'],
        'location': r['location'],
        'has_content': bool(r['race_content_json']),
    } for r in races])


# ======================================================================
# STATIC PAGES
# ======================================================================

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


# ======================================================================
# ERROR HANDLERS
# ======================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ======================================================================
# STARTUP — runs on import (required for gunicorn) and via __main__
# ======================================================================

# Initialize database and seed races on first load.
# Safe to call repeatedly (uses CREATE IF NOT EXISTS / checks row count).
init_db()
seed_races()

if __name__ == '__main__':
    app.run(debug=True)
