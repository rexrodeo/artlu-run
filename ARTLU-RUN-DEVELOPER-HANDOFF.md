# ARTLU.RUN — Developer Handoff Document

## Architecture Overview

```
artlu-run/
├── app.py               # Flask routes, Stripe integration, view logic
├── models.py            # Database schema, CRUD operations, seed data
├── email_service.py     # Gmail SMTP email sending
├── templates/
│   ├── base.html        # Base layout (nav, footer, flash messages)
│   ├── landing.html     # Homepage with hero, features, pricing
│   ├── race_browser.html # Browse/search/filter all races
│   ├── race_page.html   # Individual race page (free content + purchase CTA)
│   ├── purchase.html    # Purchase form (name, email, goal, city/state)
│   ├── success.html     # Post-purchase confirmation
│   ├── cancel.html      # Payment cancelled
│   ├── dashboard_login.html # Email + access code login
│   ├── dashboard.html   # User's purchased plans
│   ├── report.html      # Premium report viewer (no ads, gear referral slots)
│   ├── about.html       # About page
│   ├── contact.html     # Contact page
│   ├── privacy.html     # Privacy policy
│   ├── 404.html         # Not found
│   └── 500.html         # Server error
├── static/
│   ├── style.css        # Complete stylesheet (CSS custom properties)
│   └── app.js           # Client JS (elevation charts, filtering, AJAX forms)
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
├── Procfile             # Production deployment (gunicorn)
└── setup.py             # Legacy setup script
```

## Tech Stack

- **Backend:** Python 3.8+ / Flask 2.3
- **Database:** SQLite (file: `artlu.db`)
- **Payments:** Stripe Checkout (server-side sessions)
- **Email:** Gmail SMTP via `smtplib`
- **Frontend:** Vanilla HTML/CSS/JS (no frameworks, no build step)
- **Deployment:** gunicorn + any PaaS (Railway, Fly.io, etc.)

## Database Schema

### `races`
Core race catalog. Each row is a configurable race.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| slug | TEXT UNIQUE | URL slug (e.g. `leadville-100`) |
| name | TEXT | Display name |
| distance | TEXT | Human-readable (e.g. "100 miles") |
| distance_miles | REAL | Numeric miles for filtering |
| elevation_gain | TEXT | Human-readable (e.g. "15,600 ft") |
| elevation_gain_ft | INTEGER | Numeric feet for sorting |
| location | TEXT | City, State or region |
| state | TEXT | US state abbreviation (NULL for international) |
| country | TEXT | Country name (default: USA) |
| description | TEXT | 2-3 sentence overview |
| month | TEXT | Race month |
| cutoff_time | TEXT | Time limit |
| difficulty | TEXT | Moderate / Hard / Expert / Extreme |
| gpx_available | BOOLEAN | Whether GPX elevation data exists |
| elevation_profile_json | TEXT | JSON array of elevation points |
| created_at | TIMESTAMP | Auto-set |

### `race_sections`
Course breakdown for each race (displayed as free content).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| race_id | INTEGER FK | References races.id |
| section_number | INTEGER | Display order |
| name | TEXT | Section name (e.g. "Hope Pass") |
| miles_start | REAL | Starting mile |
| miles_end | REAL | Ending mile |
| elevation_gain | TEXT | Section elevation change |
| description | TEXT | What this section is like |
| strategy_tip | TEXT | Free strategy advice |
| is_crux | BOOLEAN | Key/hardest section flag |
| icon | TEXT | Emoji icon |

### `purchases`
Paid race plan orders.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| email | TEXT | Customer email |
| name | TEXT | Customer name |
| race_id | INTEGER FK | References races.id |
| race_name | TEXT | Race name (denormalized for display) |
| access_code | TEXT UNIQUE | Login credential (e.g. TVYW1HX-) |
| stripe_payment_id | TEXT | Stripe payment intent ID |
| stripe_session_id | TEXT | Stripe checkout session ID |
| goal_time | TEXT | Customer's target finish time |
| city | TEXT | Training city |
| state | TEXT | Training state |
| report_ready | BOOLEAN | Whether the plan has been built |
| report_content | TEXT | HTML content of the premium plan |
| created_at | TIMESTAMP | Order timestamp |

### `race_requests`
User-submitted requests for new races.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| email | TEXT | Requester email (optional) |
| race_name | TEXT | Requested race name |
| race_url | TEXT | Link to race website (optional) |
| notes | TEXT | Additional info |
| created_at | TIMESTAMP | Request timestamp |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| FLASK_SECRET_KEY | Yes | Session encryption key |
| STRIPE_SECRET_KEY | For payments | Stripe secret key (sk_test_...) |
| STRIPE_PUBLISHABLE_KEY | For payments | Stripe publishable key (pk_test_...) |
| STRIPE_WEBHOOK_SECRET | For payments | Stripe webhook signing secret |
| EMAIL_USERNAME | For email | Gmail address |
| EMAIL_PASSWORD | For email | Gmail App Password |
| ADMIN_EMAIL | No | Admin notification email (default: vonrexroad@gmail.com) |

## Key Flows

### Purchase Flow
1. User browses `/races` → clicks a race → views free content at `/race/<slug>`
2. Clicks "Get My Plan" → goes to `/race/<slug>/purchase`
3. Fills form (name, email, goal time, city, state) → submits
4. If Stripe configured: redirects to Stripe Checkout → webhook creates purchase
5. If no Stripe (dev): creates purchase directly, redirects to `/success`
6. Customer gets email with access code
7. Admin gets email with order details

### Dashboard Flow
1. User visits `/dashboard` → sees login form
2. Enters email + access code → POST to `/dashboard/login`
3. Session cookie set → redirected to `/dashboard` with purchased plans
4. Clicks "View My Plan" → `/dashboard/report/<id>` shows premium content

### Report Fulfillment (Manual/LLM)
1. New purchase creates record with `report_ready = 0`
2. Admin/LLM builds the personalized plan
3. Call `mark_report_ready(purchase_id, html_content)` from `models.py`
4. Customer gets "plan ready" email via `send_report_ready_email()`

## Content Tiers

### Free (Race Pages)
- Course overview and section breakdown
- General strategy tips per section
- Elevation profile chart
- Ad placeholder slots for gear/nutrition sponsors

### Premium (Purchased Plans)
- Everything free, plus:
- Personalized pacing table for goal time
- Strava training segments near user's city
- Race-day playbook (nutrition, gear, mental game)
- Gear recommendation slots (referral link placeholders)
- No ads

## Ad & Monetization Slots

### Free Pages (ad placeholders)
- `data-slot="race-top"` — Top of course section content
- `data-slot="race-mid"` — Between sections and purchase CTA
- `data-slot="race-bottom"` — Bottom of race page

### Premium Pages (referral placeholders)
- `data-referral="shoes"` — Trail shoe recommendations
- `data-referral="hydration"` — Hydration gear
- `data-referral="nutrition"` — Nutrition products
- `data-referral="lighting"` — Headlamp/lighting gear

## Adding a New Race

Insert into the `races` table with all fields. Optionally add `race_sections` rows for the course breakdown. Elevation profile is a JSON array of elevation values (feet) evenly spaced across the course distance.

Example:
```python
from models import get_db
conn = get_db()
conn.execute('''INSERT INTO races (slug, name, distance, distance_miles, ...) VALUES (?, ?, ?, ?, ...)''', (...))
conn.commit()
conn.close()
```

## Races Currently Missing GPX Data

- Hardrock 100 (gpx_available = 0)
- Badwater 135 (gpx_available = 0)
- Bear 100 (gpx_available = 0)
- Javelina Jundred (gpx_available = 0)
- Run Rabid Raccoon 50 (gpx_available = 0)

These races have approximate elevation profiles but need real GPX files for accuracy.

## Running Locally

```bash
cp .env.example .env
# Edit .env with your Stripe keys and Gmail app password
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
# Test login: test@example.com / TEST-123
```
