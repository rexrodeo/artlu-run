"""
ARTLU.RUN - Email Service
=========================
Handles all outbound email via Gmail SMTP.
Configure with environment variables:
  EMAIL_USERNAME  - Gmail address (e.g. vonrexroad@gmail.com)
  EMAIL_PASSWORD  - Gmail app password (NOT your regular password)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
FROM_NAME = 'ARTLU.RUN'


def send_email(to_email, subject, html_body):
    """
    Send an HTML email via Gmail SMTP.
    Returns True on success, False on failure.
    Falls back to console logging if credentials aren't configured.
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print(f"[EMAIL NOT CONFIGURED] To: {to_email} | Subject: {subject}")
        print(f"  Body preview: {html_body[:200]}...")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'{FROM_NAME} <{EMAIL_USERNAME}>'
        msg['To'] = to_email

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USERNAME, to_email, msg.as_string())

        print(f"[EMAIL SENT] To: {to_email} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] To: {to_email} | Error: {e}")
        return False


def send_access_code_email(to_email, name, race_name, access_code):
    """Send the purchase confirmation with access code."""
    subject = f"Your {race_name} Race Plan — Access Code Inside"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e74c3c;">
            <h1 style="color: #e74c3c; margin: 0;">ARTLU.RUN</h1>
        </div>

        <div style="padding: 30px 0;">
            <h2 style="color: #2c3e50;">Hey {name or 'Runner'}!</h2>
            <p style="color: #555; line-height: 1.6;">
                Thanks for purchasing a personalized race plan for <strong>{race_name}</strong>.
                We're building your custom analysis now — it'll be ready within 24-48 hours.
            </p>

            <div style="background: #f8f9fa; border: 2px solid #e74c3c; border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0;">
                <p style="color: #666; margin: 0 0 8px 0; font-size: 14px;">YOUR ACCESS CODE</p>
                <p style="font-size: 28px; font-weight: 700; color: #e74c3c; margin: 0; letter-spacing: 2px;">{access_code}</p>
            </div>

            <p style="color: #555; line-height: 1.6;">
                Use this code along with your email to access your plan at:
                <br><a href="https://artlu.run/dashboard" style="color: #e74c3c;">artlu.run/dashboard</a>
            </p>

            <p style="color: #555; line-height: 1.6;">
                We'll send you another email when your personalized plan is ready to view.
            </p>
        </div>

        <div style="border-top: 1px solid #eee; padding: 20px 0; color: #999; font-size: 13px; text-align: center;">
            ARTLU.RUN — Custom ultra race strategy
        </div>
    </div>
    """
    return send_email(to_email, subject, html)


def send_report_ready_email(to_email, name, race_name):
    """Notify the user their report is ready."""
    subject = f"Your {race_name} Plan is Ready!"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e74c3c;">
            <h1 style="color: #e74c3c; margin: 0;">ARTLU.RUN</h1>
        </div>

        <div style="padding: 30px 0;">
            <h2 style="color: #2c3e50;">Your plan is ready, {name or 'Runner'}!</h2>
            <p style="color: #555; line-height: 1.6;">
                Your personalized <strong>{race_name}</strong> race strategy is complete
                and waiting for you.
            </p>

            <div style="text-align: center; margin: 24px 0;">
                <a href="https://artlu.run/dashboard" style="display: inline-block; background: #e74c3c; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                    View Your Plan
                </a>
            </div>

            <p style="color: #555; line-height: 1.6;">
                Log in with your email and access code to see your full personalized strategy,
                training segments, pacing plan, and more.
            </p>
        </div>

        <div style="border-top: 1px solid #eee; padding: 20px 0; color: #999; font-size: 13px; text-align: center;">
            ARTLU.RUN — Custom ultra race strategy
        </div>
    </div>
    """
    return send_email(to_email, subject, html)


def send_order_notification(admin_email, purchase_data):
    """Notify admin/Bro about a new order that needs analysis."""
    subject = f"New ARTLU.RUN Order: {purchase_data.get('race_name', 'Unknown Race')}"
    html = f"""
    <div style="font-family: monospace; padding: 20px;">
        <h2>New Race Plan Order</h2>
        <table style="border-collapse: collapse;">
            <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Customer:</td><td>{purchase_data.get('name', 'N/A')}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Email:</td><td>{purchase_data.get('email', 'N/A')}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Race:</td><td>{purchase_data.get('race_name', 'N/A')}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Goal Time:</td><td>{purchase_data.get('goal_time', 'N/A')}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Training City:</td><td>{purchase_data.get('city', 'N/A')}, {purchase_data.get('state', 'N/A')}</td></tr>
        </table>
    </div>
    """
    return send_email(admin_email, subject, html)
