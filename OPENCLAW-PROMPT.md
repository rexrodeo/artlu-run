# OpenClaw Integration — ARTLU.RUN

Two skills power the site. Skill 1 populates the free race pages. Skill 2 generates personalized premium reports after purchase.

---

## Skill 1: Free Race Content Populator

### Purpose

Populate each race page with rich, detailed free content — course breakdowns, strategy, weather, essentials. This content includes **blurred premium teasers** within each segment that act as CTAs for the paid plan.

### Discovery — Which Races Need Content

```
GET https://artlu.run/api/races
Headers:
  X-API-Key: {{OPENCLAW_API_KEY}}
```

Returns a list of all races. Populate any where `has_content: false`:

```json
[
  {"slug": "hardrock-100", "name": "Hardrock 100", "distance": "100 miles", "location": "Silverton, Colorado", "has_content": false},
  {"slug": "leadville-100", "name": "Leadville Trail 100", "distance": "100 miles", "location": "Leadville, Colorado", "has_content": true}
]
```

### Prompt

```
You are an expert ultramarathon course analyst. Research {{race_name}} ({{distance}}, {{location}}) thoroughly and generate a detailed race page as a JSON object.

Research:
1. The full course — every major climb, descent, technical section, and aid station
2. Typical race-day weather by time of day and altitude
3. Proven strategies from veteran finishers
4. Required and recommended gear
5. Training benchmarks for peak training phase

Break the course into 4-8 logical segments. Each segment gets:
- Free content: full description, aid stations, strategy tips (3 per segment)
- Premium teasers: placeholder text showing what the paid plan includes (target times, gear specifics, nutrition, local training segment matches). These appear blurred on the page as purchase motivation.

**Output a single JSON object** with this exact structure:

{
  "callout": {
    "icon": "⛰️",
    "title": "Short punchy title about this race's defining challenge",
    "text": "2-3 sentences about what makes this race uniquely hard. Be specific — reference actual course features."
  },
  "weather": [
    {"label": "START (time)", "value": "temp range"},
    {"label": "MIDDAY", "value": "temp + conditions"},
    {"label": "AFTERNOON", "value": "temp + storm risk"},
    {"label": "NIGHT", "value": "temp range"}
  ],
  "segments": [
    {
      "number": 1,
      "name": "Segment Name (e.g., Start to First Major Aid)",
      "miles_start": 0,
      "miles_end": 13.5,
      "tags": ["+2,500 ft", "Singletrack", "Dawn"],
      "is_crux": false,
      "description": "2-4 sentences describing the terrain, footing, and character of this section. Be vivid and specific — mention actual trail names, landmarks, and what runners will see/feel.",
      "aid_stations": "Station Name (Mile X) — what's typically available",
      "strategy": [
        "Specific actionable tip #1 for this section",
        "Specific actionable tip #2 referencing course features",
        "Specific actionable tip #3 about pacing/effort"
      ],
      "premium_preview": {
        "arrival_time": "Target: X:XX AM based on 28hr finish",
        "gear": "Specific gear items for this section",
        "nutrition": "Calorie targets and specific foods",
        "training_segments": [
          {
            "name": "Realistic trail or Strava segment name",
            "match": 92,
            "details": "Elevation/distance stats — why it matches this race section"
          },
          {
            "name": "Another matching segment",
            "match": 85,
            "details": "What this trains and how it compares"
          }
        ]
      }
    }
  ],
  "race_essentials": [
    "Required item 1 (be specific — brand/type if relevant)",
    "Required item 2",
    "Recommended item with brief reason",
    "At least 6-10 items total"
  ],
  "weekly_targets": {
    "volume": "XX-XX mi/wk",
    "vertical": "XX,000-XX,000 ft/wk",
    "components": [
      "Key workout type 1 with specifics",
      "Key workout type 2 with specifics",
      "Key workout type 3 with specifics"
    ]
  },
  "finisher_tips": [
    "Hard-won insight #1 from actual finishers — be specific and non-obvious",
    "Hard-won insight #2",
    "Hard-won insight #3",
    "Include 4-6 tips total"
  ]
}

**Critical requirements:**
- Every segment MUST include the `premium_preview` object. This is what creates the blurred premium teasers that drive purchases. Without it, there's no visible premium content to tease.
- `premium_preview.training_segments` should have 1-2 plausible local training matches per segment (use realistic segment names — the premium skill will replace these with actual personalized matches later)
- `premium_preview.arrival_time` should reference a reasonable mid-pack goal time for this specific race
- `is_crux: true` on the 1-2 hardest/most decisive segments (these get highlighted styling)
- Strategy tips must be specific to THIS course — no generic ultramarathon advice
- Weather data should reflect actual race-month conditions at the race location and altitude
- The `tags` array should include elevation change, terrain type, and time-of-day

**Output only the JSON object, no other text.**
```

### Delivery

```
POST https://artlu.run/api/race-content/{{slug}}
Headers:
  Content-Type: application/json
  X-API-Key: {{OPENCLAW_API_KEY}}
Body: <the JSON object above>
```

Returns `{"success": true, "slug": "hardrock-100"}`.

### Adding New Races

To add a race that doesn't exist yet:

```
POST https://artlu.run/api/race
Headers:
  Content-Type: application/json
  X-API-Key: {{OPENCLAW_API_KEY}}
Body: {
  "slug": "barkley-marathons",
  "name": "Barkley Marathons",
  "distance": "130 miles",
  "distance_miles": 130,
  "elevation_gain": "63,000 ft",
  "elevation_gain_ft": 63000,
  "location": "Frozen Head State Park, Tennessee",
  "state": "TN",
  "country": "USA",
  "description": "The race that breaks everyone. Five unmarked loops through Tennessee briars.",
  "month": "March",
  "cutoff_time": "60 hours",
  "difficulty": "Extreme"
}
```

Then populate its content with the race-content endpoint above.

---

## Skill 2: Premium Personalized Race Report

### Purpose

Fires after a user purchases a plan. Generates a personalized report based on the runner's goal time, training city, and the specific course. This data replaces the blurred teasers on the race page with real personalized content.

### Input Variables

From the purchase record:

- `{{race_name}}` — e.g., "Leadville Trail 100"
- `{{race_slug}}` — e.g., "leadville-100"
- `{{user_name}}` — e.g., "Andrew"
- `{{user_email}}` — e.g., "andrew@example.com"
- `{{goal_time}}` — e.g., "24:00" (hours:minutes)
- `{{city}}` — e.g., "Denver"
- `{{state}}` — e.g., "CO"
- `{{purchase_id}}` — e.g., 42

### Prompt

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

### Delivery

```
POST https://artlu.run/api/premium-data/{{purchase_id}}
Headers:
  Content-Type: application/json
  X-API-Key: {{OPENCLAW_API_KEY}}
Body: <the JSON object above>
```

Returns `{"success": true}`.

### User Experience

The user's browser is polling every 5 seconds after purchase, showing a building animation with rotating status messages ("Analyzing course segments...", "Matching Strava segments near your city...", "Building gear recommendations..."). When the data arrives, it triggers a cascade reveal animation — each premium teaser unblurs in sequence with a 300ms stagger.

---

## Environment

Set `OPENCLAW_API_KEY` on Railway (artlu.run) to match the key both skills send in `X-API-Key`.

## API Summary

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/races` | GET | List all races + content status |
| `/api/race` | POST | Create or update a race |
| `/api/race-content/<slug>` | POST | Populate free page content |
| `/api/premium-data/<purchase_id>` | POST | Deliver personalized premium report |
| `/api/my-premium/<slug>` | GET | Frontend polling (no API key needed) |
