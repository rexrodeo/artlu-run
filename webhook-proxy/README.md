# artlu-webhook-proxy

Bridges Stripe payment webhooks to OpenClaw for automated premium report generation.

## How it works

```
Stripe Payment → webhook-proxy (your machine) → OpenClaw Gateway → artlu-race-report skill
                                                                          ↓
                                                          artlu.run API ← premium report JSON
```

## Setup

```bash
cd webhook-proxy
npm install
cp .env.example .env
```

Edit `.env`:
```
STRIPE_WEBHOOK_SECRET=whsec_...    # From Stripe dashboard
OPENCLAW_GATEWAY_URL=http://localhost:18789
OPENCLAW_GATEWAY_TOKEN=5be46b22720e5259fe5752c4ef401a7b01b618288a4d87f8
PORT=3000
```

## Running

```bash
npm start
```

## Exposing to Stripe

For local development, use the Stripe CLI:
```bash
stripe listen --forward-to localhost:3000/stripe-webhook
```

For production, use ngrok or similar:
```bash
ngrok http 3000
# Then set the ngrok URL as your webhook endpoint in Stripe dashboard
# e.g., https://abc123.ngrok.io/stripe-webhook
```

In the Stripe dashboard, add the webhook endpoint and select the `checkout.session.completed` event.

## Testing

```bash
# Health check
curl http://localhost:3000/health

# Trigger a test webhook via Stripe CLI
stripe trigger checkout.session.completed

# Or send a mock webhook directly
curl -X POST http://localhost:3000/stripe-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "type": "checkout.session.completed",
    "data": {
      "object": {
        "id": "cs_test_123",
        "payment_intent": "pi_test_123",
        "customer_email": "test@test.com",
        "metadata": {
          "race_slug": "leadville-100",
          "race_name": "Leadville Trail 100",
          "name": "Test Runner",
          "email": "test@test.com",
          "goal_time": "25:00",
          "city": "Denver",
          "state": "CO"
        }
      }
    }
  }'
```

## Flow details

1. User completes Stripe Checkout on artlu.run
2. Stripe sends `checkout.session.completed` webhook to this proxy
3. Proxy extracts purchase metadata (race, runner details, goal time)
4. Proxy sends trigger message to OpenClaw Gateway
5. OpenClaw's artlu-race-report skill activates:
   - Calls `GET /api/purchase-lookup?email=...&race_slug=...` to get the `purchase_id`
   - Researches the course via Brave Search
   - Finds real Strava segments near the runner's city
   - Generates personalized pacing, gear, nutrition plan
   - POSTs the JSON to `POST /api/premium-data/{purchase_id}`
6. Runner's browser (polling every 5s) detects the data and triggers cascade reveal
