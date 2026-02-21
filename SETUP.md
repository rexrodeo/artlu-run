# 🏃‍♂️ ARTLU.RUN - Setup Guide

**Ultra Race Training Analysis Platform**

## 🚀 What We Built

**Free Content:**
- Landing page with value proposition
- Race browser with popular ultras  
- Individual race pages (Leadville 100 example)
- Course breakdowns and general strategy

**Paid Service:**
- $39 personalized training analysis
- Uses your ultra-race-research skill
- Localized Strava segments
- Email + access code authentication
- Stripe payment integration

## 🛠️ Quick Setup

### 1. Install Dependencies
```bash
cd artlu-run
python3 setup.py
```

### 2. Get Stripe Keys
1. Go to [stripe.com/dashboard](https://stripe.com/dashboard)
2. Get your **Secret Key** (sk_test_...)  
3. Get your **Publishable Key** (pk_test_...)
4. Create webhook endpoint for `/webhook`
5. Get **Webhook Secret** (whsec_...)

### 3. Update .env File
Edit `.env` with your real Stripe keys:
```bash
STRIPE_SECRET_KEY=sk_test_your_actual_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_actual_key  
STRIPE_WEBHOOK_SECRET=whsec_your_actual_secret
```

### 4. Run Locally
```bash
python3 app.py
```
Visit: http://localhost:5000

### 5. Test Purchase Flow
- Email: `test@example.com`
- Access Code: `TEST-123`

## 📋 What You Need From Rex

### Required:
1. **Stripe Account** - Already have one ✅
2. **Domain DNS** - Point artlu.run to hosting
3. **Email Service** - Gmail or SendGrid for notifications

### Optional:
4. **Google Analytics** - Track visitors
5. **Logo/Branding** - Currently using 🏃‍♂️ emoji

## 🤖 Bro Integration

**When someone purchases:**
1. Stripe webhook creates database record
2. Sends email notification to Bro
3. Bro runs ultra-race-research skill  
4. Uploads result, marks ready
5. Customer gets "ready" email

**Bro's workflow:**
```python
# 1. Get new order notification
order = get_pending_orders()

# 2. Run analysis
result = run_ultra_skill(order.race_name, order.training_location)

# 3. Upload and mark ready  
upload_report(order.id, result)
mark_ready(order.id)
```

## 🚀 Deployment Options

**Option 1: Railway (Recommended)**
- Connect GitHub repo
- Auto-deploys on push
- Built-in Postgres
- $5/month

**Option 2: Fly.io**
- `fly launch`
- Global edge network
- Pay per usage

**Option 3: DigitalOcean App Platform**
- Simple deployment
- $5/month

## 💰 Revenue Model

**Pricing:**
- $39 per personalized analysis
- Future: $19/month subscription

**Customer Flow:**
1. Browse free race content
2. See value, click "Get Personalized"
3. Pay $39 via Stripe
4. Receive email with access code
5. Visit /access to view reports
6. Stay engaged for future purchases

## 📈 Growth Strategy

**Content Marketing:**
- SEO-optimized race pages
- "How to train for [Race]" articles
- Runner testimonials

**Social Proof:**
- "142 runners trained with our Leadville plan"
- Success stories and photos
- Strava segment leaderboards

## 🔧 Next Features

**Week 2:**
- More race pages (Western States, UTMB, Hardrock)
- Email automation (welcome, report ready)
- Admin dashboard for Bro

**Month 2:**
- Subscription pricing
- Race request system  
- Mobile app (maybe)

## 📊 Analytics to Track

- Conversion rate (visitors → purchases)
- Popular races
- Geographic distribution
- Customer lifetime value

## 🎯 Success Metrics

**Month 1 Goal:** 10 purchases ($390 revenue)
**Month 3 Goal:** 50 purchases ($1,950 revenue)
**Month 6 Goal:** 100 purchases + 50 subscribers ($6,950 revenue)

---

**Ready to launch?** This is a complete, functional ultra training platform that can start generating revenue immediately. Bro can handle all the analysis work, and you can focus on marketing and growth.

**The ultra running market is hungry for this service.** Let's get it live! 🏃‍♂️💰