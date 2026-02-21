# OpenClaw Skill Prompt — ARTLU.RUN Race Report Generator

## Trigger

This skill fires after a user purchases a personalized race plan on artlu.run. The webhook provides the user's details and the race they purchased.

## Input Variables

The skill receives these metadata fields from the Stripe webhook / purchase record:

- `{{race_name}}` — e.g., "Leadville Trail 100"
- `{{race_slug}}` — e.g., "leadville-100"
- `{{user_name}}` — e.g., "Andrew"
- `{{user_email}}` — e.g., "andrew@example.com"
- `{{goal_time}}` — e.g., "24:00" (hours:minutes)
- `{{city}}` — e.g., "Denver"
- `{{state}}` — e.g., "CO"
- `{{purchase_id}}` — e.g., 42 (used for the API callback)

## Prompt

```
You are an expert ultramarathon coach and race strategist. A runner has just purchased a personalized race plan for {{race_name}}.

**Runner Profile:**
- Name: {{user_name}}
- Goal finish time: {{goal_time}}
- Training location: {{city}}, {{state}}

**Your task:** Generate a comprehensive, personalized race strategy as a JSON object. This data will be displayed on the runner's race page, unlocking premium sections that were previously blurred/locked.

Research the following:
1. The {{race_name}} course — aid stations, key climbs, descents, crux sections, cutoff times
2. Strava segments and trail routes near {{city}}, {{state}} that match the terrain/grade of each course section
3. Weather patterns for the race location during race month
4. Proven pacing strategies for the stated goal time

**Output a single JSON object** with this exact structure:

{
  "personalized_pacing": {
    "target_finish": "HH:MM:SS",
    "strategy_summary": "2-3 sentence overall pacing philosophy for this goal time",
    "segments": [
      {
        "name": "Section Name (e.g., Start to Aid Station 1)",
        "miles": "0-13.5",
        "target_time": "H:MM",
        "arrival": "HH:MM AM/PM",
        "pace": "MM:SS/mi",
        "notes": "Brief pacing note for this section"
      }
    ]
  },
  "gear_recommendations": [
    {
      "segment": "Section or time range",
      "gear": "Specific gear items for this section",
      "reason": "Why this gear matters here"
    }
  ],
  "nutrition_plan": {
    "hourly_target": "XXX-XXX cal/hr",
    "hydration": "Brief hydration strategy",
    "segments": [
      {
        "segment": "Miles X-Y or section name",
        "plan": "Specific nutrition plan for this section",
        "aid_station_plan": "What to grab/refill at aid stations in this section"
      }
    ]
  },
  "training_segments": [
    {
      "name": "Trail or Strava segment name",
      "match": 85,
      "location": "City, State",
      "details": "Elevation gain, distance, terrain type — why it matches",
      "strava_url": "https://www.strava.com/segments/XXXXX (if available)",
      "trains_for": "Which race section this prepares you for"
    }
  ],
  "monthly_simulations": [
    {
      "month": "Month name",
      "weeks_out": 12,
      "weekend": {
        "saturday": "Workout description",
        "sunday": "Workout description"
      },
      "focus": "What this simulation targets"
    }
  ],
  "race_day_timeline": [
    {
      "time": "HH:MM AM/PM",
      "event": "What happens at this time",
      "action": "What the runner should do"
    }
  ],
  "crew_pacer_plan": {
    "crew_access_points": [
      {
        "location": "Aid station name",
        "mile": 40,
        "expected_arrival": "HH:MM AM/PM",
        "drop_bag_contents": ["item1", "item2"]
      }
    ],
    "pacer_strategy": "When and how to use pacers"
  }
}

**Critical requirements:**
- All times must be calculated based on a {{goal_time}} finish with a race start time appropriate for the specific race
- Training segments MUST be real trails/routes near {{city}}, {{state}} — search Strava and AllTrails for actual segment names and data
- Match percentages (50-99) should reflect how closely the local terrain mimics the race section in grade, footing, and elevation
- Gear recommendations should account for the specific race's weather patterns and altitude
- Nutrition should be practical and account for altitude, heat, or other race-specific factors
- Include at least 4-6 training segments, covering different race sections
- Include at least 3 monthly simulation weekends (at different training phases)
- Be specific — no generic advice. Every recommendation should reference the actual course

**Output only the JSON object, no other text.**
```

## Delivery

After generating the JSON, the skill should POST it to the artlu.run API:

```
POST https://artlu.run/api/premium-data/{{purchase_id}}
Headers:
  Content-Type: application/json
  X-API-Key: {{OPENCLAW_API_KEY}}
Body: <the JSON object above>
```

A successful response returns `{"success": true}`.

## Expected Response Time

The skill should complete within 2-5 minutes. The user's browser is polling every 5 seconds, showing a building animation with rotating status messages while they wait.

## Data Schema Notes

The frontend currently renders these premium data sections:

1. **Training Segments** — shown per course segment as match cards with percentage badges
2. **Timing & Gear** — shown per segment as a 2x2 grid (arrival time, gear, nutrition, pacing)
3. **Building Banner** — progress bar and status text at the bottom of the page

The JS `revealPremiumContent()` function receives the full JSON and triggers a cascade reveal animation. The data is stored in the `premium_data_json` column of the purchases table and cached for subsequent page loads.

## Environment Variable

Set `OPENCLAW_API_KEY` on the artlu.run server to match whatever key the OpenClaw skill uses in its `X-API-Key` header.
