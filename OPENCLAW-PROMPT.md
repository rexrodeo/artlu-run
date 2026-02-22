# OpenClaw Integration — ARTLU.RUN

Two skills power the site. Skill 1 populates the free race pages (including GPX data). Skill 2 generates personalized premium reports after purchase (including real Strava segment matches).

Both skills have access to **Brave Search API** for web research. Use it to find real GPX files, real Strava segments, and verified course data.

---

## Skill 1: Free Race Content Populator

### Purpose

Populate each race page with rich, detailed free content — GPX elevation profile, course breakdowns, strategy, weather, essentials. This content includes **blurred premium teasers** within each segment that act as CTAs for the paid plan.

### Workflow

For each race with `has_content: false`:

1. **Research the race** using Brave Search — find the official course, aid station list, elevation profile, cutoffs, weather data, finisher reports
2. **Find the GPX file** — search for `"{{race_name}}" GPX download filetype:gpx` or look on the race website, CalTopo, Strava routes, or UltraSignup. Many races publish their GPX publicly
3. **Upload the GPX** to auto-generate the elevation chart and compute stats
4. **Generate the free content JSON** with detailed segments and premium teasers
5. **POST the content** to populate the page

### Step 1: Discovery — Which Races Need Content

```
GET https://artlu.run/api/races
Headers:
  X-API-Key: {{OPENCLAW_API_KEY}}
```

Returns:
```json
[
  {"slug": "hardrock-100", "name": "Hardrock 100", "distance": "100 miles", "location": "Silverton, Colorado", "has_content": false},
  {"slug": "leadville-100", "name": "Leadville Trail 100", "has_content": true}
]
```

### Step 2: Upload GPX (if found)

Search Brave for the race's GPX file. Good search queries:
- `"{{race_name}}" GPX download`
- `"{{race_name}}" course GPX site:strava.com`
- `"{{race_name}}" GPX site:caltopo.com`
- `"{{race_name}}" course map filetype:gpx`

If you find a GPX file, POST it:

```
POST https://artlu.run/api/race-gpx/{{slug}}
Headers:
  Content-Type: application/json
  X-API-Key: {{OPENCLAW_API_KEY}}
Body: {"gpx": "<the raw GPX XML content>"}
```

Returns stats computed from the GPX:
```json
{
  "success": true,
  "slug": "hardrock-100",
  "stored": true,
  "profile_generated": true,
  "profile_points": 200,
  "distance_miles": 100.5,
  "elevation_gain_ft": 33992,
  "elevation_loss_ft": 33992,
  "min_elevation_ft": 7680,
  "max_elevation_ft": 14048
}
```

This auto-generates the elevation chart on the race page and updates the race's distance/elevation stats from real data. If no GPX is found, skip this step — the page still works without it.

### Step 3: Generate and POST Free Content

**Prompt:**

```
You are an expert ultramarathon course analyst. Research {{race_name}} ({{distance}}, {{location}}) thoroughly and generate a detailed race page as a JSON object.

Use Brave Search to research:
1. The full course — every major climb, descent, technical section, and aid station (search: "{{race_name}}" course description, aid stations, race report)
2. Typical race-day weather by time of day and altitude (search: "{{race_name}}" weather conditions race day)
3. Proven strategies from veteran finishers (search: "{{race_name}}" race report finisher advice)
4. Required and recommended gear (search: "{{race_name}}" required gear mandatory equipment)
5. Training benchmarks for peak training phase (search: "{{race_name}}" training plan peak week)

Break the course into 4-8 logical segments. Each segment gets:
- Free content: full description, aid stations, strategy tips (3 per segment)
- Premium teasers: placeholder text showing what the paid plan includes. These appear blurred on the page as purchase motivation.

**Output a single JSON object** with this exact structure:

{
  "callout": {
    "icon": "⛰️",
    "title": "Short punchy title about this race's defining challenge",
    "text": "2-3 sentences about what makes this race uniquely hard. Be specific — reference actual course features, verified via your research."
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
      "description": "2-4 sentences describing the terrain, footing, and character. Be vivid and specific — mention actual trail names, landmarks, features you found in race reports.",
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
    "Include 6-10 items, sourced from the race's actual mandatory gear list"
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
    "Hard-won insight #1 from actual finishers found in race reports",
    "Hard-won insight #2",
    "Include 4-6 tips sourced from real finisher accounts"
  ]
}

**Critical requirements:**
- Every segment MUST include `premium_preview`. This creates the blurred premium teasers that drive purchases.
- `is_crux: true` on the 1-2 hardest/most decisive segments
- Strategy tips must be specific to THIS course — no generic ultramarathon advice
- Weather data should reflect actual race-month conditions verified via search
- All content should be backed by your Brave Search research — no guessing
```

**Delivery:**

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

Then upload GPX and populate content with the endpoints above.

---

## Skill 2: Premium Personalized Race Report

### Purpose

Fires after a user purchases a plan. Generates a personalized report using **real Strava segment research** based on the runner's training city. This data replaces the blurred teasers on the race page with verified, actionable content.

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
You are an expert ultramarathon coach. A runner has purchased a personalized plan for {{race_name}}.

**Runner Profile:**
- Name: {{user_name}}
- Goal finish time: {{goal_time}}
- Training location: {{city}}, {{state}}

**Your task:** Generate a personalized race strategy as JSON. This unlocks the premium sections on their race page.

**RESEARCH STEPS (use Brave Search for each):**

1. **Course research**: Search "{{race_name}} course description aid stations cutoffs" — find the full course breakdown, aid station locations and distances, cutoff times at each aid
2. **Race start time**: Search "{{race_name}} start time" — needed to calculate segment arrival times
3. **Strava segments near runner's city**: For each major course section, search:
   - "strava segment {{city}} {{state}} climb {{elevation_gain}} feet"
   - "strava segment {{city}} {{state}} trail running"
   - "best trail runs {{city}} {{state}} ultramarathon training"
   - "alltrails {{city}} {{state}} elevation gain"
   Then verify each Strava URL is real by searching for the specific segment name
4. **Weather**: Search "{{race_name}} race day weather typical conditions"
5. **Pacing data**: Search "{{race_name}} {{goal_time}} hour finish splits pacing"

**STRAVA SEGMENT MATCHING:**
For each course segment, find 1-2 training routes near {{city}}, {{state}} that match on:
- Grade (feet gained per mile)
- Terrain type (road, singletrack, rocky, technical)
- Elevation range (altitude training if applicable)
- Distance similarity

Calculate a match score (50-99) based on these factors. Include the real Strava URL in format: https://www.strava.com/segments/XXXXXXX

**Output a single JSON object:**

{
  "personalized_pacing": {
    "target_finish": "HH:MM:SS",
    "strategy_summary": "2-3 sentence pacing philosophy for this goal time at this race",
    "segments": [
      {
        "name": "Section Name",
        "miles": "0-13.5",
        "target_time": "H:MM",
        "arrival": "HH:MM AM/PM",
        "pace": "MM:SS/mi",
        "notes": "Pacing note specific to this section and goal time"
      }
    ]
  },
  "gear_recommendations": [
    {
      "segment": "Section or time range",
      "gear": "Specific gear items",
      "reason": "Why this matters here — reference altitude, weather, terrain"
    }
  ],
  "nutrition_plan": {
    "hourly_target": "XXX-XXX cal/hr",
    "hydration": "Hydration strategy accounting for altitude/heat",
    "segments": [
      {
        "segment": "Miles X-Y",
        "plan": "Specific nutrition plan for this section",
        "aid_station_plan": "What to grab/refill at each aid station"
      }
    ]
  },
  "training_segments": [
    {
      "name": "Actual Strava segment or trail name",
      "match": 92,
      "location": "{{city}}, {{state}}",
      "details": "1,200ft gain over 2.3mi, rocky singletrack — mimics the Hope Pass approach grade",
      "strava_url": "https://www.strava.com/segments/XXXXXXX",
      "trains_for": "Which race section this prepares you for and why"
    }
  ],
  "monthly_simulations": [
    {
      "month": "Month name",
      "weeks_out": 12,
      "weekend": {
        "saturday": "Specific workout using local trails by name",
        "sunday": "Specific workout using local trails by name"
      },
      "focus": "What this simulation targets"
    }
  ],
  "race_day_timeline": [
    {
      "time": "HH:MM AM/PM",
      "event": "What happens",
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
    "pacer_strategy": "When to pick up pacers and strategy for each pacer leg"
  }
}

**Critical requirements:**
- All arrival times calculated from actual race start time + {{goal_time}} pacing
- Training segments MUST be real trails near {{city}}, {{state}} found via Brave Search — include real Strava URLs where possible
- Match scores should be justified by comparing grade, terrain, and altitude
- Include at least 4-6 training segments matching different race sections
- Include at least 3 monthly simulation weekends using real local trail names
- Nutrition must account for race-specific factors (altitude, heat, etc.)
- Every recommendation must reference the actual course — no generic advice

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

The user's browser polls every 5 seconds after purchase, showing a building animation with rotating status messages ("Analyzing course segments...", "Searching Strava segments near your city...", "Building gear recommendations..."). When data arrives, each premium teaser unblurs in a cascade animation with 300ms stagger.

---

## Environment

Set `OPENCLAW_API_KEY` on Railway (artlu.run) to match the key both skills send in `X-API-Key`.

## API Summary

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/races` | GET | List all races + content status |
| `/api/race` | POST | Create or update a race |
| `/api/race-gpx/<slug>` | POST | Upload GPX → auto-generates elevation profile + stats |
| `/api/race-content/<slug>` | POST | Populate free page content with premium teasers |
| `/api/premium-data/<purchase_id>` | POST | Deliver personalized premium report |
| `/api/my-premium/<slug>` | GET | Frontend polling (no API key needed) |

All endpoints except `/api/my-premium` require `X-API-Key` header.
