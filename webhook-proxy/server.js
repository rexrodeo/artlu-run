/**
 * ARTLU.RUN — Stripe → OpenClaw Webhook Proxy
 *
 * Receives Stripe webhooks after purchases, extracts race plan metadata,
 * and forwards a trigger message to OpenClaw Gateway to generate the
 * personalized premium report.
 *
 * Runs locally alongside OpenClaw (both on your machine).
 * Stripe sends webhooks here via ngrok or similar tunnel.
 *
 * Usage:
 *   npm install
 *   cp .env.example .env  (fill in your keys)
 *   npm start
 *
 *   Then in Stripe dashboard or CLI:
 *   stripe listen --forward-to localhost:3000/stripe-webhook
 */

const express = require('express');
const stripe = require('stripe');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PORT = process.env.PORT || 3000;
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || '';
const OPENCLAW_GATEWAY_URL = process.env.OPENCLAW_GATEWAY_URL || 'http://localhost:18789';
const OPENCLAW_GATEWAY_TOKEN = process.env.OPENCLAW_GATEWAY_TOKEN || '';

const app = express();

// Stripe webhooks need raw body for signature verification
app.post('/stripe-webhook', express.raw({ type: 'application/json' }), handleStripeWebhook);

// Health check (JSON parsed normally)
app.use(express.json());
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'artlu-webhook-proxy',
    openclaw_target: OPENCLAW_GATEWAY_URL,
    stripe_configured: !!STRIPE_WEBHOOK_SECRET,
    uptime: process.uptime(),
  });
});

// ---------------------------------------------------------------------------
// Stripe Webhook Handler
// ---------------------------------------------------------------------------
async function handleStripeWebhook(req, res) {
  let event;

  // Verify signature if webhook secret is configured
  if (STRIPE_WEBHOOK_SECRET) {
    const sig = req.headers['stripe-signature'];
    try {
      event = stripe('').webhooks.constructEvent(req.body, sig, STRIPE_WEBHOOK_SECRET);
    } catch (err) {
      log('ERROR', `Signature verification failed: ${err.message}`);
      return res.status(401).json({ error: 'Invalid signature' });
    }
  } else {
    // Dev mode — no signature verification
    try {
      event = JSON.parse(req.body.toString());
    } catch (err) {
      return res.status(400).json({ error: 'Invalid JSON' });
    }
    log('WARN', 'No STRIPE_WEBHOOK_SECRET — skipping signature verification');
  }

  log('INFO', `Received event: ${event.type} (${event.id})`);

  // Only process completed checkouts
  if (event.type !== 'checkout.session.completed' && event.type !== 'payment_intent.succeeded') {
    log('INFO', `Ignoring event type: ${event.type}`);
    return res.json({ received: true, processed: false });
  }

  // Extract metadata
  const session = event.data.object;
  const metadata = session.metadata || {};

  const purchaseData = {
    race_name: metadata.race_name,
    race_slug: metadata.race_slug,
    user_name: metadata.user_name || metadata.name,
    user_email: metadata.user_email || metadata.email || session.customer_email,
    goal_time: metadata.goal_time,
    city: metadata.city,
    state: metadata.state,
    purchase_id: metadata.purchase_id || session.payment_intent || session.id,
  };

  // Validate required fields
  const required = ['race_name', 'race_slug', 'user_email', 'goal_time', 'purchase_id'];
  const missing = required.filter(f => !purchaseData[f]);
  if (missing.length > 0) {
    log('WARN', `Missing required metadata: ${missing.join(', ')}`, purchaseData);
    return res.status(400).json({
      error: 'Missing required metadata',
      missing,
      received: purchaseData,
    });
  }

  log('INFO', `Processing purchase: ${purchaseData.user_name} → ${purchaseData.race_name} (${purchaseData.goal_time})`, purchaseData);

  // Forward to OpenClaw
  try {
    await forwardToOpenClaw(purchaseData);
    log('INFO', `Successfully forwarded to OpenClaw: purchase ${purchaseData.purchase_id}`);
    return res.json({ received: true, processed: true, forwarded: true });
  } catch (err) {
    log('ERROR', `Failed to forward to OpenClaw: ${err.message}`);
    // Still return 200 to Stripe so it doesn't retry endlessly
    // But log the error for manual retry
    return res.status(200).json({
      received: true,
      processed: true,
      forwarded: false,
      error: err.message,
      retry_data: purchaseData,
    });
  }
}

// ---------------------------------------------------------------------------
// OpenClaw Gateway Integration
// ---------------------------------------------------------------------------
async function forwardToOpenClaw(purchaseData) {
  const message = [
    `ARTLU_PURCHASE: Generate premium race report.`,
    `Race: ${purchaseData.race_name} (${purchaseData.race_slug})`,
    `Runner: ${purchaseData.user_name} (${purchaseData.user_email})`,
    `Goal Time: ${purchaseData.goal_time}`,
    `Training Location: ${purchaseData.city}, ${purchaseData.state}`,
    ``,
    `Use the artlu-race-report skill to:`,
    `1. First, look up the purchase_id:`,
    `   GET https://artlu.run/api/purchase-lookup?email=${encodeURIComponent(purchaseData.user_email)}&race_slug=${purchaseData.race_slug}`,
    `   (Header: X-API-Key with the OPENCLAW_API_KEY)`,
    `   This returns the purchase_id needed for step 5. If 404, wait 10 seconds and retry — the Stripe webhook may still be processing.`,
    `2. Research ${purchaseData.race_name} course details via Brave Search`,
    `3. Find real Strava segments near ${purchaseData.city}, ${purchaseData.state} matching course terrain`,
    `4. Calculate pacing splits for a ${purchaseData.goal_time} finish`,
    `5. POST the complete JSON to https://artlu.run/api/premium-data/{purchase_id} (from step 1)`,
  ].join('\n');

  const payload = {
    channel: 'main',
    message: message,
  };

  log('DEBUG', `Sending to OpenClaw: ${OPENCLAW_GATEWAY_URL}/api/message`);

  const response = await fetch(`${OPENCLAW_GATEWAY_URL}/api/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${OPENCLAW_GATEWAY_TOKEN}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`OpenClaw returned ${response.status}: ${text}`);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------
function log(level, message, data) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level}]`;
  if (data) {
    console.log(`${prefix} ${message}`, JSON.stringify(data, null, 2));
  } else {
    console.log(`${prefix} ${message}`);
  }
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  log('INFO', `artlu-webhook-proxy running on port ${PORT}`);
  log('INFO', `OpenClaw target: ${OPENCLAW_GATEWAY_URL}`);
  log('INFO', `Stripe signature verification: ${STRIPE_WEBHOOK_SECRET ? 'ENABLED' : 'DISABLED (dev mode)'}`);
  console.log('');
  log('INFO', 'Ready to receive Stripe webhooks at POST /stripe-webhook');
  log('INFO', 'Health check at GET /health');
});
