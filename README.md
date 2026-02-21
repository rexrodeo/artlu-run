# ARTLU.RUN — Ultra Race Strategy

Personalized ultramarathon race plans with custom pacing, local Strava training segments, and deep course insights.

## Quick Start

```bash
git clone https://github.com/rexrodeo/artlu-run.git
cd artlu-run
cp .env.example .env        # Edit with your Stripe keys + Gmail app password
pip install -r requirements.txt
python app.py                # http://localhost:5000
```

Test credentials: `test@example.com` / `TEST-123`

## What It Does

**Free:** Browse race pages with course breakdowns, elevation profiles, and strategy tips. Ad placeholder slots for gear/nutrition sponsors.

**Paid ($39):** Personalized race plan with pacing for your goal time, Strava training segments near your city, race-day playbook, and gear recommendations. No ads.

## Architecture

See [ARTLU-RUN-DEVELOPER-HANDOFF.md](ARTLU-RUN-DEVELOPER-HANDOFF.md) for the full developer reference.

| File | Purpose |
|------|---------|
| `app.py` | Flask routes + Stripe integration |
| `models.py` | Database schema + CRUD operations |
| `email_service.py` | Gmail SMTP email sending |
| `templates/` | Jinja2 HTML templates |
| `static/` | CSS + JavaScript |

## Stack

Python/Flask, SQLite, Stripe Checkout, Gmail SMTP, vanilla HTML/CSS/JS.
