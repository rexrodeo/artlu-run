"""
ARTLU.RUN - Database Models and Operations
==========================================
SQLite-based data layer for races, purchases, and race requests.
All database access goes through this module.
"""

import sqlite3
import secrets
import os
import json
from datetime import datetime

DB_PATH = os.getenv('DATABASE_PATH', 'artlu.db')


def get_db():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initialize all database tables.
    Called once at app startup. Safe to call multiple times (uses IF NOT EXISTS).
    """
    conn = get_db()
    cursor = conn.cursor()

    # -------------------------------------------------------------------
    # RACES - Core race catalog
    # -------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS races (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            distance TEXT NOT NULL,
            distance_miles REAL,
            elevation_gain TEXT,
            elevation_gain_ft INTEGER,
            location TEXT,
            state TEXT,
            country TEXT DEFAULT 'USA',
            description TEXT,
            month TEXT,
            cutoff_time TEXT,
            difficulty TEXT DEFAULT 'Hard',
            gpx_available BOOLEAN DEFAULT 0,
            image_url TEXT,
            elevation_profile_json TEXT,
            race_content_json TEXT,
            training_location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -------------------------------------------------------------------
    # RACE_SECTIONS - Course breakdown for each race (free content)
    # -------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER NOT NULL,
            section_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            miles_start REAL,
            miles_end REAL,
            elevation_gain TEXT,
            description TEXT,
            strategy_tip TEXT,
            is_crux BOOLEAN DEFAULT 0,
            icon TEXT DEFAULT '🏃‍♂️',
            FOREIGN KEY (race_id) REFERENCES races(id)
        )
    ''')

    # -------------------------------------------------------------------
    # PURCHASES - Paid race plan orders
    # -------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT,
            race_id INTEGER,
            race_name TEXT NOT NULL,
            access_code TEXT UNIQUE NOT NULL,
            stripe_payment_id TEXT,
            stripe_session_id TEXT,
            goal_time TEXT,
            city TEXT,
            state TEXT,
            report_ready BOOLEAN DEFAULT 0,
            report_content TEXT,
            premium_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (race_id) REFERENCES races(id)
        )
    ''')

    # -------------------------------------------------------------------
    # RACE_REQUESTS - User-submitted requests for new races
    # -------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            race_name TEXT NOT NULL,
            race_url TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Handle adding new columns to existing tables (if upgrading)
    try:
        cursor.execute("ALTER TABLE races ADD COLUMN race_content_json TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE races ADD COLUMN training_location TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE purchases ADD COLUMN premium_data_json TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()


# ======================================================================
# RACE OPERATIONS
# ======================================================================

def get_all_races():
    """Return all races ordered by name."""
    conn = get_db()
    races = conn.execute('SELECT * FROM races ORDER BY name').fetchall()
    conn.close()
    return races


def get_race_by_slug(slug):
    """Return a single race by its URL slug."""
    conn = get_db()
    race = conn.execute('SELECT * FROM races WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    return race


def get_race_sections(race_id):
    """Return all course sections for a race, ordered by section number."""
    conn = get_db()
    sections = conn.execute(
        'SELECT * FROM race_sections WHERE race_id = ? ORDER BY section_number',
        (race_id,)
    ).fetchall()
    conn.close()
    return sections


def get_race_content(race_id):
    """Return parsed JSON content for a race, or None if not available."""
    conn = get_db()
    race = conn.execute('SELECT race_content_json FROM races WHERE id = ?', (race_id,)).fetchone()
    conn.close()
    if not race or not race['race_content_json']:
        return None
    try:
        return json.loads(race['race_content_json'])
    except (json.JSONDecodeError, TypeError):
        return None


def save_race_content(slug, content_json):
    """
    Save or update the race_content_json for a race by slug.
    content_json should be a dict (will be serialized to JSON).
    Returns True on success, False if race not found.
    """
    conn = get_db()
    result = conn.execute(
        'UPDATE races SET race_content_json = ? WHERE slug = ?',
        (json.dumps(content_json), slug)
    )
    conn.commit()
    updated = result.rowcount > 0
    conn.close()
    return updated


def create_or_update_race(race_data):
    """
    Create a new race or update an existing one by slug.
    race_data is a dict with keys matching the races table columns.
    Required: slug, name, distance.
    Optional: distance_miles, elevation_gain, elevation_gain_ft, location,
              state, country, description, month, cutoff_time, difficulty,
              price_cents, plan_price, elevation_profile, race_content_json,
              training_location.
    Returns the race id.
    """
    conn = get_db()
    slug = race_data['slug']

    existing = conn.execute('SELECT id FROM races WHERE slug = ?', (slug,)).fetchone()

    # Columns that actually exist in the races table
    RACE_COLUMNS = ['name', 'distance', 'distance_miles', 'elevation_gain',
                    'elevation_gain_ft', 'location', 'state', 'country',
                    'description', 'month', 'cutoff_time', 'difficulty',
                    'training_location']

    if existing:
        # Update existing race
        fields = []
        values = []
        for key in RACE_COLUMNS:
            if key in race_data:
                fields.append(f'{key} = ?')
                values.append(race_data[key])

        if 'race_content_json' in race_data:
            fields.append('race_content_json = ?')
            val = race_data['race_content_json']
            values.append(json.dumps(val) if isinstance(val, dict) else val)

        if 'elevation_profile_json' in race_data:
            fields.append('elevation_profile_json = ?')
            val = race_data['elevation_profile_json']
            values.append(json.dumps(val) if isinstance(val, (list, dict)) else val)

        if fields:
            values.append(slug)
            conn.execute(f'UPDATE races SET {", ".join(fields)} WHERE slug = ?', values)
            conn.commit()

        race_id = existing['id']
    else:
        # Insert new race
        content_json = race_data.get('race_content_json')
        if isinstance(content_json, dict):
            content_json = json.dumps(content_json)

        profile_json = race_data.get('elevation_profile_json')
        if isinstance(profile_json, (list, dict)):
            profile_json = json.dumps(profile_json)

        conn.execute('''
            INSERT INTO races (slug, name, distance, distance_miles, elevation_gain,
                             elevation_gain_ft, location, state, country, description,
                             month, cutoff_time, difficulty, elevation_profile_json,
                             race_content_json, training_location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            slug,
            race_data.get('name', slug),
            race_data.get('distance', '100 miles'),
            race_data.get('distance_miles'),
            race_data.get('elevation_gain'),
            race_data.get('elevation_gain_ft'),
            race_data.get('location'),
            race_data.get('state'),
            race_data.get('country', 'USA'),
            race_data.get('description'),
            race_data.get('month'),
            race_data.get('cutoff_time'),
            race_data.get('difficulty', 'Hard'),
            profile_json,
            content_json,
            race_data.get('training_location'),
        ))
        conn.commit()
        race_id = conn.execute('SELECT id FROM races WHERE slug = ?', (slug,)).fetchone()['id']

    conn.close()
    return race_id


# ======================================================================
# PURCHASE OPERATIONS
# ======================================================================

def create_purchase(email, name, race_id, race_name, goal_time, city, state,
                    stripe_payment_id=None, stripe_session_id=None):
    """
    Create a new purchase record with a unique access code.
    Returns the access code.
    """
    access_code = secrets.token_urlsafe(6).upper()
    conn = get_db()
    conn.execute('''
        INSERT INTO purchases
            (email, name, race_id, race_name, access_code, stripe_payment_id,
             stripe_session_id, goal_time, city, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (email, name, race_id, race_name, access_code, stripe_payment_id,
          stripe_session_id, goal_time, city, state))
    conn.commit()
    conn.close()
    return access_code


def get_purchase_by_code(email, access_code):
    """Look up a purchase by email + access code."""
    conn = get_db()
    purchase = conn.execute(
        'SELECT * FROM purchases WHERE email = ? AND access_code = ?',
        (email, access_code.upper())
    ).fetchone()
    conn.close()
    return purchase


def get_purchases_by_email(email):
    """Return all purchases for a given email address."""
    conn = get_db()
    purchases = conn.execute(
        'SELECT * FROM purchases WHERE email = ? ORDER BY created_at DESC',
        (email,)
    ).fetchall()
    conn.close()
    return purchases


def mark_report_ready(purchase_id, report_content=None):
    """Mark a purchased report as ready, optionally storing HTML content."""
    conn = get_db()
    conn.execute(
        'UPDATE purchases SET report_ready = 1, report_content = ? WHERE id = ?',
        (report_content, purchase_id)
    )
    conn.commit()
    conn.close()


def save_premium_data(purchase_id, data_json):
    """Save premium data (JSON string) for a purchase from OpenClaw."""
    conn = get_db()
    conn.execute(
        'UPDATE purchases SET premium_data_json = ? WHERE id = ?',
        (data_json, purchase_id)
    )
    conn.commit()
    conn.close()


def get_premium_data(purchase_id):
    """Return parsed premium JSON data for a purchase, or None if not available."""
    conn = get_db()
    purchase = conn.execute(
        'SELECT premium_data_json FROM purchases WHERE id = ?',
        (purchase_id,)
    ).fetchone()
    conn.close()
    if not purchase or not purchase['premium_data_json']:
        return None
    try:
        return json.loads(purchase['premium_data_json'])
    except (json.JSONDecodeError, TypeError):
        return None


def get_purchase_for_race(email, race_id):
    """Check if a user has purchased a specific race, return purchase or None."""
    conn = get_db()
    purchase = conn.execute(
        'SELECT * FROM purchases WHERE email = ? AND race_id = ? LIMIT 1',
        (email, race_id)
    ).fetchone()
    conn.close()
    return purchase


# ======================================================================
# RACE REQUEST OPERATIONS
# ======================================================================

def create_race_request(email, race_name, race_url=None, notes=None):
    """Save a user's request for a new race to be added."""
    conn = get_db()
    conn.execute(
        'INSERT INTO race_requests (email, race_name, race_url, notes) VALUES (?, ?, ?, ?)',
        (email, race_name, race_url, notes)
    )
    conn.commit()
    conn.close()


# ======================================================================
# SEED DATA
# ======================================================================

def seed_races():
    """
    Populate the races table with initial data if empty.
    Called at startup after init_db().
    """
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM races').fetchone()[0]
    if count > 0:
        conn.close()
        return

    # Rich content for Leadville
    leadville_content = {
        "callout": {
            "icon": "⛰️",
            "title": "Altitude is Everything",
            "text": "Starting at 10,152 ft with sustained climbing above 10,000 ft, you'll spend most of this race in the thin air of the Colorado high country. Hope Pass at 12,620 ft twice tests your acclimatization, pacing strategy, and mental resilience. This is the most altitude-dependent race on the ultra circuit."
        },
        "weather": [
            {"label": "START (6 AM)", "value": "40-50°F"},
            {"label": "MIDDAY", "value": "60-75°F"},
            {"label": "LATE CLIMB", "value": "40-55°F"},
            {"label": "NIGHT", "value": "30-40°F"}
        ],
        "segments": [
            {
                "number": 1,
                "name": "Start to May Queen",
                "miles_start": 0,
                "miles_end": 13.5,
                "tags": ["+800 ft", "Forest Roads", "Dawn"],
                "is_crux": False,
                "description": "The race begins conservatively on dirt forest roads and singletrack around Turquoise Lake. This section is runnable and feels almost easy, which is exactly the trap. Many runners blow themselves up here by going too fast too early, draining glycogen they'll desperately need later. The terrain rolls gently, giving false confidence.",
                "aid_stations": "Turquoise Lake Aid Station (mile 13)",
                "strategy": ["Start 30 seconds slower than feels natural—you can't make up an early mistake at this altitude", "Drink constantly from the start: aim for 6-8 oz every 15 minutes", "Run the flats and descents, walk any climb >5%, even if it's small"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~1:45-2:00am based on 10-min/mile goal pace",
                    "gear": "Long-sleeve base layer, hydration pack (2L), energy gels",
                    "nutrition": "60-80 calories per 15 min; alternate gels and sports drink",
                    "training_segments": [
                        {"name": "Forest to Fire Trail", "match": 92, "details": "3.1 mi • 380 ft gain • rolling forest trail"}
                    ]
                }
            },
            {
                "number": 2,
                "name": "May Queen to Outward Bound",
                "miles_start": 13.5,
                "miles_end": 24,
                "tags": ["+2,400 ft", "Consistent Climb", "Morning"],
                "is_crux": False,
                "description": "The relentless Hagerman Pass Road section. This is a long, steady climb without technical terrain—just switchbacks on an old mining road. The grade is manageable (5-8%) but unrelenting. You'll spend 2-3 hours grinding here. Altitude is becoming noticeable. Your quads start to feel the day's climbing.",
                "aid_stations": "May Queen Aid Station (start), Halfmoon Creek Aid (mile 20)",
                "strategy": ["Lock into a power hiking rhythm; you'll be faster than walking but you won't bonk", "Use trekking poles to take load off quads and engage your upper body", "Eat and drink at every aid station; don't skip meals because you feel full"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~4:00-4:30am depending on goal pace",
                    "gear": "Trekking poles essential, warm layer, sunglasses, cap",
                    "nutrition": "80-100 calories per 15 min; solid food (pretzels, PB&J) recommended here",
                    "training_segments": [
                        {"name": "Vail Pass Road Climb", "match": 88, "details": "2.4 mi • 1,200 ft gain • steady road climb"}
                    ]
                }
            },
            {
                "number": 3,
                "name": "Outward Bound to Hope Pass",
                "miles_start": 24,
                "miles_end": 44,
                "tags": ["+3,000 ft", "Crux Section", "The Climb"],
                "is_crux": True,
                "description": "The race-defining section. You ascend to Hope Pass (12,620 ft) then descend to Winfield. The climbing gets steeper as you go higher. This is where DNFs happen. Altitude sickness, blown quads, shattered morale—take your pick. The descent from Hope is treacherous: loose, steep, and leg-destroying. Your race is often won or lost here.",
                "aid_stations": "Outward Bound Aid, Hope Pass (mile 36, no aid), Winfield (mile 44)",
                "strategy": ["Start the climb conservatively and settle into power hiking early, before fatigue compounds", "Heart rate zones don't apply at altitude: go by feel and effort, not metrics", "On the descent, shorten your stride and lean slightly back; walk if needed; quads matter more tomorrow than today", "Get to Winfield, eat real food, and prepare mentally for Hope Pass again"],
                "premium_preview": {
                    "arrival_time": "Hope Pass: ~9:00-11:00am; Winfield: ~1:00-2:00pm depending on goal",
                    "gear": "Lightweight shell jacket, emergency blanket, hand warmers, trekking poles",
                    "nutrition": "150-200 calories per 30 min; real food essential (soup, sandwiches at aid stations)",
                    "training_segments": [
                        {"name": "Mosquito Pass Training Loop", "match": 96, "details": "4.2 mi • 2,100 ft gain • alpine climb at altitude"}
                    ]
                }
            },
            {
                "number": 4,
                "name": "Winfield Return to Twin Lakes",
                "miles_start": 44,
                "miles_end": 60.5,
                "tags": ["+3,000 ft", "Hope Again", "Afternoon Heat"],
                "is_crux": True,
                "description": "You must climb Hope Pass a second time. Your legs are already tired from the descent, your feet are blistered, and the afternoon heat is setting in. Yet you face the same steep ascent again. This is where mental strength separates finishers from DNFs. The positive: you know the terrain now, and finishing is finally within reach.",
                "aid_stations": "Winfield Aid (start), Hope Pass (mile 52, no aid), Twin Lakes Aid (mile 60.5)",
                "strategy": ["Treat this as a separate race; forget the morning climb happened", "Break the climb into 1-mile chunks and don't look at the full distance", "Use the descent to recover; walking is not quitting", "Eat and drink aggressively at Twin Lakes—you have 20 miles left and only 8 hours to finish"],
                "premium_preview": {
                    "arrival_time": "Hope Pass: ~4:00-5:30pm; Twin Lakes: ~7:00-8:00pm depending on goal",
                    "gear": "Sunscreen, chafe cream, foot care supplies, cap, sunglasses",
                    "nutrition": "150-200 calories per 30 min; salty foods recommended; electrolytes critical",
                    "training_segments": [
                        {"name": "Chalk Creek Trail", "match": 84, "details": "2.8 mi • 1,800 ft gain • steep alpine climb"}
                    ]
                }
            },
            {
                "number": 5,
                "name": "Twin Lakes to Halfmoon",
                "miles_start": 60.5,
                "miles_end": 76.5,
                "tags": ["-2,400 ft", "Recovery Section", "Evening"],
                "is_crux": False,
                "description": "A blessed downhill and rolling section. Your legs are trashed from Hope Pass twice, but gravity helps. Night is approaching. This is the 'easy' part, relatively speaking. You'll move faster here if you can manage the pain in your quads.",
                "aid_stations": "Twin Lakes (start), Halfmoon Creek Aid (mile 76.5)",
                "strategy": ["Take small controlled steps on the descent; bigger strides destroy knees", "Keep moving steady; this section feels long but goes faster than you'd think", "Get night gear ready at the aid station before it's dark", "Eat real food: soup, sandwiches, potato; this is your last major aid before the push"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~8:30-9:30pm depending on goal",
                    "gear": "Warm layers, lights, extra socks, blister kit",
                    "nutrition": "80-100 calories per 15 min; real food important for mental stamina",
                    "training_segments": [
                        {"name": "Highway 24 Trail", "match": 79, "details": "3.2 mi • descent over 1,100 ft • loose trail"}
                    ]
                }
            },
            {
                "number": 6,
                "name": "Halfmoon to Finish",
                "miles_start": 76.5,
                "miles_end": 100,
                "tags": ["Rolling", "Night Running", "Final Push"],
                "is_crux": False,
                "description": "The final 23.5 miles through the night, mostly on familiar terrain. Fatigue has peaked. Your legs don't work properly. Your brain is fried. But you're close. This section is about mental toughness and discipline: take walk breaks, eat calories, keep moving forward. The finish line is never as far as it feels.",
                "aid_stations": "Halfmoon Creek (start), Fish Hatchery (mile 83), Tabor Boat Ramp (mile 89), Downtown Leadville finish",
                "strategy": ["Don't sit down at any aid station; standing is hard to recover from", "Calculate your pace vs. cutoff at every aid: know your exact pace needed to finish", "Walk the hills, run the flats, walk if you're struggling to run", "Use a pacer or crew here if possible; isolation leads to mistakes in the final miles"],
                "premium_preview": {
                    "arrival_time": "Fish Hatchery: ~10:30-11:30pm; Finish: ~10:00-11:00pm+1 depending on goal",
                    "gear": "Double-check lights, batteries, warm layers for post-midnight chill",
                    "nutrition": "60-80 calories per 15 min, focusing on salty, real foods for mental stamina",
                    "training_segments": [
                        {"name": "Leadville Downtown Loop", "match": 94, "details": "1.6 mi • minimal gain • final effort simulator"}
                    ]
                }
            }
        ],
        "race_essentials": [
            "Trekking poles (critical for Hope Pass twice)",
            "Hydration pack or bottles (start with 2L capacity)",
            "Headlamp with extra batteries",
            "Warm layers (fleece, jacket, base layer)",
            "Hat and sunglasses",
            "Sunscreen and chafe cream",
            "Blister care supplies and extra socks",
            "Hand warmers for high-altitude sections",
            "Emergency blanket or space blanket",
            "Energy gels and electrolyte drink mix",
            "Real food: nuts, nut butter, sandwiches, pretzels",
            "Watch or timing device for pace tracking"
        ],
        "weekly_targets": {
            "volume": "70-100 miles per week at peak",
            "vertical": "12,000-18,000 ft gain per week",
            "components": [
                "Back-to-back long runs every weekend (20+ miles total)",
                "One high-altitude training week (if possible: above 8,000 ft)",
                "Monthly night run (20+ miles) to practice headlamp running",
                "Strength training 2x per week (focus on quads, glutes, core)",
                "At least one 30+ mile run within 8 weeks of race"
            ]
        },
        "finisher_tips": [
            "Leadville is won on the climbs but lost on the descents—practice downhill running and protect your knees",
            "Altitude acclimatization is crucial: arrive 1-2 weeks early if possible, or at least 3-5 days before race",
            "Hope Pass will humble you twice; accept that it's hard and maintain forward progress",
            "Mental toughness beats fitness at Leadville—prepare for the emotional valleys in the last 30 miles",
            "Have a pacer for miles 60+; the final push is exponentially harder alone",
            "Practice your nutrition plan relentlessly; GI issues here can end your race",
            "Sleep the night before is irrelevant; focus on sleep 2-3 nights before the race"
        ]
    }

    # Rich content for Western States
    western_content = {
        "callout": {
            "icon": "🔥",
            "title": "Heat and Descents Will Destroy You",
            "text": "Western States drops 6,000+ feet from high Sierra snowpack into valley canyons that routinely exceed 100°F. The relentless downhill terrain hammers your quads worse than any 100-miler. Expect river crossings in cold snowmelt. By mile 62, many runners' quads shut down entirely. Heat management and quad preservation are everything."
        },
        "weather": [
            {"label": "START (5 AM)", "value": "35-45°F, Snowy"},
            {"label": "MID-MORNING", "value": "50-70°F, Warming"},
            {"label": "MIDDAY", "value": "100-110°F+, Peak Heat"},
            {"label": "EVENING", "value": "80-95°F, Still Hot"}
        ],
        "segments": [
            {
                "number": 1,
                "name": "Squaw Valley to Five Lakes",
                "miles_start": 0,
                "miles_end": 10.5,
                "tags": ["+2,300 ft", "Alpine Start", "Dawn", "Possible Snow"],
                "is_crux": False,
                "description": "The race begins in darkness at Squaw Valley at 6,200 ft and climbs steeply through Alpine meadows. You'll likely see snow on the ground. Cold, steep, technical singletrack. Your legs are fresh but the altitude and steepness hurt immediately. This section sorts runners by fitness; don't get caught trying to keep up with the fast start.",
                "aid_stations": "Squaw Valley Start, Five Lakes Aid (mile 10.5)",
                "strategy": ["Start conservatively despite the adrenaline and cold; you have 24+ hours ahead", "Use trekking poles; they're critical on steep snow/icy terrain here", "Settle into a hard hiking pace; running is tempting but unsustainable", "Eat something at the first aid; your stomach might not want food but force it"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~1:30-2:00am depending on goal pace",
                    "gear": "Warm base layer, insulated jacket, trekking poles, gaiters if snowy",
                    "nutrition": "60-80 calories per 15 min; sports drink for hydration",
                    "training_segments": [
                        {"name": "Squaw Peak Training Climb", "match": 94, "details": "2.1 mi • 1,600 ft gain • alpine singletrack"}
                    ]
                }
            },
            {
                "number": 2,
                "name": "Five Lakes to Swede Camp",
                "miles_start": 10.5,
                "miles_end": 20.5,
                "tags": ["+3,000 ft", "High Elevation", "Technical", "Morning"],
                "is_crux": False,
                "description": "Continued climbing through rocky alpine terrain above 8,000 ft. This section is high, exposed, and technical. Views are stunning. Your legs are starting to tire from the early climbing. The terrain is boulder-strewn and demands attention. You're still in the cool of morning, which is a mercy.",
                "aid_stations": "Five Lakes (start), Swede Camp Aid (mile 20.5)",
                "strategy": ["Keep hiking steadily; don't burn matches on this sustained climb", "Watch your footing carefully; a twisted ankle ends your race here", "Start eating real calories; the first 20 miles go by slower than you'd think", "Hydrate aggressively; you're not in heat yet but dehydration compounds later"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~3:45-4:30am depending on goal",
                    "gear": "Warm layer, cap, sunglasses, gaiters, trekking poles",
                    "nutrition": "80-100 calories per 15 min; solid food (granola, nuts) for staying power",
                    "training_segments": [
                        {"name": "Sierra Buttes High Trail", "match": 89, "details": "3.4 mi • 2,200 ft gain • alpine rock scramble"}
                    ]
                }
            },
            {
                "number": 3,
                "name": "Swede Camp to El Dorado Creek",
                "miles_start": 20.5,
                "miles_end": 30,
                "tags": ["+1,500 ft", "-2,500 ft", "Transition to Descent", "Warming"],
                "is_crux": False,
                "description": "You reach the high point of the course and begin the long descent into the canyons. The terrain shifts from high alpine to forested descent. It's still cool but warming up. The miles flow faster now; you'll be tempted to run more. Your quads start taking load from the constant downhill.",
                "aid_stations": "Swede Camp (start), Miller's Meadow (mile 26), El Dorado Creek (mile 30)",
                "strategy": ["Short strides on descents; protect your quads for the long canyons ahead", "You'll feel good here and want to push; resist the urge—pace yourself", "Eat and drink at every aid; you're entering the heat zone", "Apply sunscreen now; you'll regret not protecting your skin"],
                "premium_preview": {
                    "arrival_time": "Target arrival: ~6:30-7:30am depending on goal",
                    "gear": "Sunscreen, hat, sunglasses, warmer layer optional",
                    "nutrition": "80-100 calories per 15 min; starting to focus on heat tolerance",
                    "training_segments": [
                        {"name": "Downieville Trail Descent", "match": 85, "details": "3.2 mi • 2,000 ft loss • steep rocky descent"}
                    ]
                }
            },
            {
                "number": 4,
                "name": "El Dorado Creek to Michigan Bluff",
                "miles_start": 30,
                "miles_end": 62,
                "tags": ["-4,000 ft", "Heat Canyon", "Crux Section"],
                "is_crux": True,
                "description": "The infamous 32-mile canyon section where heat is the enemy. You descend through rocky canyons, crossing streams in cold snowmelt, then climbing back up—over and over. Temperatures exceed 100°F in the canyon bottoms. Your quads are destroyed by constant downhill. Runners bonk mentally and physically here. Many ultra runners say this is the hardest 32 miles of running they've ever done.",
                "aid_stations": "El Dorado Creek (start), Deadwood Creek (mile 35), Foresthill (mile 62, major aid)",
                "strategy": ["Accept that your quads will hurt; everyone's do", "Focus on not hiking when running hurts; many runners hike here and still have quads fail", "Cold stream crossings are a blessing; soak your feet, cool your core", "Eat aggressively despite heat-driven nausea; calories prevent breakdown", "Calculate your pace vs. cutoff; many runners drop here when they realize they won't make it"],
                "premium_preview": {
                    "arrival_time": "Deadwood: ~1:00-2:30pm; Foresthill: ~6:00-8:00pm depending on goal",
                    "gear": "Minimal layers, extreme sunscreen, wide-brimmed hat, cooling towel, gaiters for stream crossings",
                    "nutrition": "100-150 calories per 15 min, emphasizing salt and electrolytes; real food tolerable in canyon (sandwiches, boiled potatoes)",
                    "training_segments": [
                        {"name": "Cataract Creek Trail Network", "match": 92, "details": "5.1 mi • 2,800 ft loss • steep rocky canyon descent"}
                    ]
                }
            },
            {
                "number": 5,
                "name": "Foresthill to Auburn",
                "miles_start": 62,
                "miles_end": 100,
                "tags": ["+2,000 ft", "Finish", "Night Run", "Final 38 Miles"],
                "is_crux": False,
                "description": "The final 38 miles from Foresthill to Auburn. At mile 62, many runners' quads have shut down—they can barely walk, let alone run. But you're close and the finish is guaranteed if you keep moving. Foresthill is your last major aid; refuel completely. The final sections roll through cooler terrain as evening comes.",
                "aid_stations": "Foresthill (mile 62, major), Green Gate (mile 73), Robie Point (mile 79), Placer High School (mile 87), Auburn finish",
                "strategy": ["Eat everything at Foresthill; your stomach might be rebels but force real food", "Walk if running hurts; quads often recover with walking breaks", "The final miles are a grind; focus on mental wins (next aid, next mile)", "You're close enough to smell the finish; embrace the pain and push"],
                "premium_preview": {
                    "arrival_time": "Green Gate: ~10:00-11:00pm; Auburn: ~10:00-11:00pm+1 depending on goal",
                    "gear": "Headlamp, warm layer (evening cooling), minimal gear",
                    "nutrition": "60-80 calories per 15 min; mostly fluids now as GI system shuts down",
                    "training_segments": [
                        {"name": "Auburn Valley Regional Park Loop", "match": 81, "details": "2.4 mi • 600 ft rolling • final effort simulator"}
                    ]
                }
            }
        ],
        "race_essentials": [
            "Trekking poles (critical for steep descents, especially first 30 miles)",
            "Hydration pack or bottles (start with 2L capacity, refill aggressively)",
            "Headlamp with extra batteries",
            "Warm layers for high altitude start (fleece, jacket, base layer)",
            "Sun protection: wide-brimmed hat, sunglasses, high-SPF sunscreen",
            "Cooling towel for canyon heat management",
            "Gaiters for stream crossings and rocky terrain",
            "Blister care supplies and extra socks",
            "Electrolyte-heavy drink mix for canyon heat",
            "Energy gels, bars, and real food: nuts, nut butter, sandwiches",
            "Watch for pace tracking vs. cutoff",
            "Minimal warm layer for evening cooling"
        ],
        "weekly_targets": {
            "volume": "80-120 miles per week at peak",
            "vertical": "10,000-16,000 ft gain per week",
            "components": [
                "Long descent training every week (15+ miles with 5,000+ ft loss)",
                "Back-to-back long runs on consecutive days (30+ miles total)",
                "Heat acclimation runs: 2-3 runs per week in peak heat (afternoon)",
                "One 40+ mile run within 4 weeks of race",
                "Strength training 2x per week (focus on quads, glutes, eccentric loading)",
                "Quad-focused eccentric training (downhill running, step-downs) critical"
            ]
        },
        "finisher_tips": [
            "Western States is 'downhill' but the repeated up-and-down canyon climbing takes quads to failure—quad training is non-negotiable",
            "Heat acclimation is as important as any training; spend time running in 85°F+ temperatures regularly",
            "Foresthill aid station is your mental reset; go in broken, come out whole with 38 miles left",
            "Many runners finish despite believing they'll quit at mile 62; the mind is stronger than the body suggests",
            "Arrive early to acclimate to the heat and terrain; a pre-race shakeout run on course sections is invaluable",
            "Find a pacer for the final 38 miles if possible; psychological support is as important as physical pacing",
            "Practice eating while hot; GI shutdown in the canyon often comes from training the wrong fueling strategy"
        ]
    }

    races = [
        {
            'slug': 'leadville-100',
            'name': 'Leadville Trail 100',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '15,600 ft',
            'elevation_gain_ft': 15600,
            'location': 'Leadville, Colorado',
            'state': 'CO',
            'country': 'USA',
            'description': "America's highest altitude 100-mile trail race. Starting and finishing in Leadville at 10,152 ft, the out-and-back course crosses Hope Pass at 12,620 ft — twice. Runners face thin air, steep climbs, and dramatic temperature swings across the Colorado Rockies. The 30-hour cutoff makes finishing a serious achievement.",
            'month': 'August',
            'cutoff_time': '30 hours',
            'difficulty': 'Expert',
            'gpx_available': 1,
            'elevation_profile_json': '[10152,10200,10350,10500,10800,10600,10400,10200,9800,9600,9400,9200,9400,9600,10000,10400,10800,11200,11600,12000,12400,12620,12200,11600,11000,10400,9800,9600,9800,10000,10400,10800,11200,11600,12000,12400,12620,12200,11600,11000,10400,10200,10000,9800,9600,9400,9600,9800,10000,10152]',
            'race_content_json': json.dumps(leadville_content),
            'training_location': 'Denver/Boulder metro area'
        },
        {
            'slug': 'western-states-100',
            'name': 'Western States 100',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '18,090 ft',
            'elevation_gain_ft': 18090,
            'location': 'Olympic Valley to Auburn, California',
            'state': 'CA',
            'country': 'USA',
            'description': "The world's oldest 100-mile trail race, running point-to-point from Squaw Valley to Auburn through the Sierra Nevada. Features extreme heat in the canyons (often 100°F+), icy river crossings, and relentless descents that destroy quads. The lottery entry and storied history make it the most coveted ultra finish in North America.",
            'month': 'June',
            'cutoff_time': '30 hours',
            'difficulty': 'Expert',
            'gpx_available': 1,
            'elevation_profile_json': '[6200,7800,8750,8500,7200,6800,6200,5400,4800,4200,3600,3000,2800,3200,3800,4200,3600,3000,2400,2200,2600,3000,2400,1800,1400,1200,1400,1800,2200,2600,2200,1800,1400,1200,1000,1200,1400,1000,800,600,500,400,350,320,300,350,400,380,360,340]',
            'race_content_json': json.dumps(western_content),
            'training_location': 'San Francisco Bay Area'
        },
        {
            'slug': 'utmb',
            'name': 'Ultra-Trail du Mont-Blanc',
            'distance': '106 miles',
            'distance_miles': 106.0,
            'elevation_gain': '32,800 ft',
            'elevation_gain_ft': 32800,
            'location': 'Chamonix, France',
            'state': None,
            'country': 'France',
            'description': "The most prestigious ultra trail race in the world. A full circumnavigation of Mont Blanc through France, Italy, and Switzerland with 32,800 ft of climbing. Technical alpine terrain, unpredictable mountain weather, and a 46.5-hour cutoff make this the ultimate test of mountain running.",
            'month': 'August',
            'cutoff_time': '46 hours 30 min',
            'difficulty': 'Expert',
            'gpx_available': 1,
            'elevation_profile_json': '[1035,1200,1600,2100,2537,2100,1600,1200,800,1000,1400,1800,2200,2537,2200,1800,1400,1000,800,1000,1400,1800,2200,2665,2200,1800,1400,1000,1200,1600,2000,2400,2537,2100,1600,1200,800,1000,1400,1800,2200,2400,2000,1600,1200,1035]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'hardrock-100',
            'name': 'Hardrock 100',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '33,050 ft',
            'elevation_gain_ft': 33050,
            'location': 'Silverton, Colorado',
            'state': 'CO',
            'country': 'USA',
            'description': "A brutal high-altitude loop through Colorado's San Juan Mountains. The course averages 11,186 ft and tops out at 14,048 ft on Handies Peak. With 33,050 ft of climbing, treacherous alpine terrain, and a 48-hour cutoff, Hardrock is often called the hardest 100-miler in America. Entry is by lottery with strict qualifying requirements.",
            'month': 'July',
            'cutoff_time': '48 hours',
            'difficulty': 'Extreme',
            'gpx_available': 0,
            'elevation_profile_json': '[9318,10000,10800,11600,12400,13000,12400,11600,10800,10000,9600,10200,11000,11800,12600,13400,14048,13400,12600,11800,11000,10200,9800,10400,11200,12000,12800,13200,12400,11600,10800,10000,9600,10200,11000,11800,12600,12800,12000,11200,10400,9800,9600,10000,10400,10000,9600,9400,9318]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'badwater-135',
            'name': 'Badwater 135',
            'distance': '135 miles',
            'distance_miles': 135.0,
            'elevation_gain': '14,600 ft',
            'elevation_gain_ft': 14600,
            'location': 'Death Valley to Mt. Whitney, California',
            'state': 'CA',
            'country': 'USA',
            'description': "Billed as the world's toughest foot race. Starting 282 ft below sea level in Death Valley's Badwater Basin and climbing to 8,360 ft at the Mt. Whitney Portal, runners face 135 miles of scorching desert heat often exceeding 130°F. A road race unlike any other, requiring a full crew and extraordinary heat tolerance.",
            'month': 'July',
            'cutoff_time': '48 hours',
            'difficulty': 'Extreme',
            'gpx_available': 0,
            'elevation_profile_json': '[-282,-200,0,200,400,600,800,600,400,200,0,400,800,1200,1600,2000,2400,2800,3200,2800,2400,2000,2400,2800,3200,3600,4000,3600,4000,4400,4800,5200,5600,6000,6400,6800,7200,7600,8000,8360]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'bear-100',
            'name': 'Bear 100',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '22,000 ft',
            'elevation_gain_ft': 22000,
            'location': 'Logan, Utah to Fish Haven, Idaho',
            'state': 'UT',
            'country': 'USA',
            'description': "A classic mountain 100-miler through the Wasatch and Bear River ranges. Point-to-point from Logan, Utah to Fish Haven, Idaho with 22,000 ft of climbing through gorgeous fall foliage. Known for its well-organized aid stations, strong community, and as a great first 100-miler for experienced ultra runners.",
            'month': 'September',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[4800,5400,6200,7000,7800,8600,9200,8600,7800,7000,7600,8200,8800,9200,8600,8000,7400,7000,7600,8200,8800,8200,7600,7000,6400,7000,7600,8200,8800,8200,7600,7000,6400,5800,6400,7000,7600,7000,6400,5800,5400,5600,6000,5800,5600,5800,6000,5800,5600,5400]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'javelina-jundred',
            'name': 'Javelina Jundred',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '5,500 ft',
            'elevation_gain_ft': 5500,
            'location': 'Fountain Hills, Arizona',
            'state': 'AZ',
            'country': 'USA',
            'description': "A fast, festive desert 100 on looped trails in McDowell Mountain Regional Park near Scottsdale. With only 5,500 ft of climbing, this is one of the fastest 100-mile courses in the US. Famous for its costume-wearing runners, raucous aid stations, and the iconic javelina (desert peccary) that roam the course.",
            'month': 'October',
            'cutoff_time': '30 hours',
            'difficulty': 'Moderate',
            'gpx_available': 0,
            'elevation_profile_json': '[1800,1900,2000,2100,2200,2100,2000,1900,1800,1900,2000,2100,2200,2100,2000,1900,1800,1900,2000,2100,2200,2100,2000,1900,1800,1900,2000,2100,2200,2100,2000,1900,1800,1900,2000,2100,2200,2100,2000,1900,1800,1900,2000,2100,2200,2100,2000,1900,1800,1800]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'run-rabid-raccoon-50',
            'name': 'Run Rabid Raccoon 50',
            'distance': '50 miles',
            'distance_miles': 50.0,
            'elevation_gain': '4,200 ft',
            'elevation_gain_ft': 4200,
            'location': 'Amarillo, Texas',
            'state': 'TX',
            'country': 'USA',
            'description': "A quirky Texas panhandle ultra on mixed terrain around Lake Meredith and Palo Duro Canyon. The 50-mile course features rocky trails, open prairie, and surprising canyon views. Known for its laid-back vibe, generous aid stations, and the ever-present threat of actual raccoons on the course.",
            'month': 'March',
            'cutoff_time': '14 hours',
            'difficulty': 'Moderate',
            'gpx_available': 0,
            'elevation_profile_json': '[3500,3600,3700,3800,3700,3600,3500,3400,3300,3400,3500,3600,3700,3800,3700,3600,3500,3400,3500,3600,3700,3600,3500,3400,3500,3600,3700,3800,3700,3600,3500,3400,3300,3400,3500,3600,3700,3600,3500,3400,3500,3600,3700,3600,3500,3400,3500,3600,3500,3500]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'mogollon-monster-100',
            'name': 'Mogollon Monster 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '19,000 ft',
            'elevation_gain_ft': 19000,
            'location': 'Show Low, Arizona',
            'state': 'AZ',
            'country': 'USA',
            'description': "A high-elevation Arizona mountain race starting at 7,300 ft in the Mogollon Rim country. The course features extensive climbing, technical terrain, and pine forest scenery. Known for its early September timing, it serves as an excellent qualifier for Hardrock 100 with significant elevation gain and rugged mountain terrain.",
            'month': 'September',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[7300,7800,8200,8600,9000,8600,8200,7800,7400,7800,8200,8600,9000,8600,8200,7800,8200,8600,9000,9400,9000,8600,8200,7800,8200,8600,9000,8600,8200,7800,7400,7800,8200,8600,9000,8600,8200,7800,7300,7500,7700,7900,8100,7900,7700,7500,7400,7300,7300,7300]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'grindstone-100',
            'name': 'Grindstone 100',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '17,500 ft',
            'elevation_gain_ft': 17500,
            'location': 'Lake Mayer, Virginia',
            'state': 'VA',
            'country': 'USA',
            'description': "An East Coast classic ultramarathon featuring rolling terrain through the Blue Ridge Mountains. Tough but runnable, it attracts elite ultrarunners and is known for qualifying runners for both Western States and Hardrock. The fall conditions and well-supported course make it an attractive East Coast option.",
            'month': 'October',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[2400,2800,3200,3600,4000,3600,3200,2800,2400,2800,3200,3600,4000,3600,3200,2800,2400,2800,3200,3600,4000,3600,3200,2800,2400,2800,3200,3600,4000,3600,3200,2800,2400,2800,3200,3600,4000,3600,3200,2800,2400,2800,3200,3600,4000,3600,3200,2800,2400,2400]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'cascade-crest-100',
            'name': 'Cascade Crest 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '28,000 ft',
            'elevation_gain_ft': 28000,
            'location': 'Snoqualmie Pass, Washington',
            'state': 'WA',
            'country': 'USA',
            'description': "One of the most challenging mountain ultras in the Pacific Northwest. A loop around the Central Cascades with relentless climbing, technical alpine terrain, and serious elevation gain. Often called one of the hardest 100-milers in the US, it qualifies runners for both Western States and Hardrock with its dramatic alpine scenery.",
            'month': 'August',
            'cutoff_time': '36 hours',
            'difficulty': 'Expert',
            'gpx_available': 0,
            'elevation_profile_json': '[3000,4000,5000,6000,6500,6000,5000,4000,5000,6000,7000,7500,7000,6000,5000,6000,7000,7500,7000,6000,5500,6000,7000,7500,7000,6000,5000,4500,5000,6000,7000,6500,6000,5000,4000,5000,6000,7000,6500,6000,5000,4000,3500,4000,5000,4500,4000,3500,3000,3000]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'rocky-raccoon-100',
            'name': 'Rocky Raccoon 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '5,000 ft',
            'elevation_gain_ft': 5000,
            'location': 'Huntsville, Texas',
            'state': 'TX',
            'country': 'USA',
            'description': "A relatively flat, fast 100-miler in southeast Texas featuring forest trails and creek running. One of the more runnable 100s, it attracts top competitors and serves as a stepping stone to major races. The January timing and fast course make it a popular early-season Hardrock qualifier.",
            'month': 'January',
            'cutoff_time': '30 hours',
            'difficulty': 'Moderate',
            'gpx_available': 0,
            'elevation_profile_json': '[250,300,350,400,450,400,350,300,250,300,350,400,450,400,350,300,250,300,350,400,450,400,350,300,250,300,350,400,450,400,350,300,250,300,350,400,450,400,350,300,250,300,350,400,450,400,350,300,250,250]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'tahoe-rim-trail-100',
            'name': 'Tahoe Rim Trail 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '20,000 ft',
            'elevation_gain_ft': 20000,
            'location': 'Lake Tahoe, California/Nevada',
            'state': 'CA',
            'country': 'USA',
            'description': "A stunning high-elevation circumnavigation of Lake Tahoe at 7,000-10,000 ft. Features beautiful alpine terrain, multiple summits, and the famous 'climb from hell' section. Technical mountain running with significant altitude, it's an excellent qualifier for both Hardrock and Western States.",
            'month': 'July',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[7000,8000,9000,10000,9500,9000,8000,7500,8000,9000,9500,10000,9500,9000,8000,8500,9000,9500,10000,9500,9000,8500,8000,7500,7000,7500,8000,8500,9000,8500,8000,7500,7000,7500,8000,8500,9000,8500,8000,7500,7000,7500,8000,8500,9000,8500,8000,7500,7000,7000]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'wasatch-front-100',
            'name': 'Wasatch Front 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '27,000 ft',
            'elevation_gain_ft': 27000,
            'location': 'Salt Lake City to Antelope Island, Utah',
            'state': 'UT',
            'country': 'USA',
            'description': "One of the toughest 100-milers in the Rocky Mountain region with brutal climbing through the Wasatch Range. Starting and ending in Salt Lake City, the course includes multiple summits above 11,000 ft and relentless elevation changes. September timing and extreme difficulty make it a premier Hardrock qualifier.",
            'month': 'September',
            'cutoff_time': '36 hours',
            'difficulty': 'Expert',
            'gpx_available': 0,
            'elevation_profile_json': '[4200,6000,8000,9500,10500,11000,10500,9000,8000,7000,8000,9000,10000,11000,10500,9500,8500,7500,8000,9000,10000,10500,10000,9000,8000,7000,6500,7000,8000,9000,10000,10500,9500,8500,7500,6500,5500,5000,4500,5000,6000,7000,8000,7000,6000,5000,4500,4300,4200,4200]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'bighorn-100',
            'name': 'Bighorn Trail 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '26,000 ft',
            'elevation_gain_ft': 26000,
            'location': 'Sheridan, Wyoming',
            'state': 'WY',
            'country': 'USA',
            'description': "A high-altitude mountain loop through the Bighorn Mountains of Wyoming starting at 9,600 ft. Features significant alpine climbing, exposed ridges, and variable weather. Part of the Rocky Mountain Slam, it's a respected Hardrock qualifier known for its rugged terrain and mountain testing.",
            'month': 'June',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[9600,10400,11000,11600,11200,10600,10000,9600,10000,10600,11200,11800,11400,10800,10200,9800,9600,10000,10600,11200,11800,11400,10800,10200,9800,9400,9600,10200,10800,11200,10800,10200,9800,9400,9600,10000,10600,11000,10600,10000,9600,9400,9600,9800,10000,10200,10000,9800,9600,9600]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'san-juan-solstice-50',
            'name': 'San Juan Solstice 50 Mile',
            'distance': '50 miles',
            'distance_miles': 50.0,
            'elevation_gain': '11,000 ft',
            'elevation_gain_ft': 11000,
            'location': 'Telluride, Colorado',
            'state': 'CO',
            'country': 'USA',
            'description': "A challenging high-altitude mountain race in the San Juan Mountains near Telluride. Starting at elevation with significant vertical gain and technical alpine terrain, it provides Hardrock-specific training with similar geology and elevation profiles. An ideal qualifier for those seeking Colorado mountain experience.",
            'month': 'June',
            'cutoff_time': '14 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[9400,10200,10800,11200,11600,11400,10800,10200,9800,10200,10800,11200,11600,11400,10800,10200,9800,10000,10600,11000,11400,11000,10600,10200,9800,10000,10600,11000,11400,11000,10600,10200,9800,10000,10400,10600,10400,10200,10000,9800,9600,9500,9400,9500,9600,9700,9800,9700,9600,9400]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'high-lonesome-100',
            'name': 'High Lonesome 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '26,000 ft',
            'elevation_gain_ft': 26000,
            'location': 'Walden, Colorado',
            'state': 'CO',
            'country': 'USA',
            'description': "A loop race through the high country of northwest Colorado starting at 9,400 ft. Features consistent high altitude, rolling terrain, and 26,000 ft of climbing. Part of the Rocky Mountain Slam series, it's a recent addition to the Hardrock qualifier list and tests runners' ability to handle extended high-altitude exposure.",
            'month': 'July',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[9400,10000,10600,11000,11200,10600,10000,9600,9800,10400,11000,11400,11200,10600,10000,9600,9400,10000,10600,11000,11200,10600,10000,9600,9800,10400,11000,11400,11200,10600,10000,9600,9400,9800,10400,10800,10400,10000,9600,9400,9200,9400,9600,9800,9800,9700,9600,9500,9400,9400]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'ouray-100',
            'name': 'Ouray 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '28,000 ft',
            'elevation_gain_ft': 28000,
            'location': 'Ouray, Colorado',
            'state': 'CO',
            'country': 'USA',
            'description': "One of the toughest mountain races in Colorado, featuring extreme elevation gain and technical alpine terrain in the San Juan Mountains. The route includes multiple 13,000+ ft passes and is known for its brutal climbing. A serious Hardrock training race for experienced mountain runners.",
            'month': 'July',
            'cutoff_time': '40 hours',
            'difficulty': 'Extreme',
            'gpx_available': 0,
            'elevation_profile_json': '[9680,10400,11000,11600,12200,12600,12200,11400,10600,10000,10600,11200,11800,12400,13000,12600,11800,11000,10400,9800,10400,11000,11600,12200,12800,13200,12800,12200,11400,10600,10000,9800,10200,10800,11200,11600,12000,11400,10800,10200,9800,10000,10200,10400,10400,10200,10000,9800,9680,9680]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'wyoming-range-100',
            'name': 'Wyoming Range 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '20,000 ft',
            'elevation_gain_ft': 20000,
            'location': 'Big Piney, Wyoming',
            'state': 'WY',
            'country': 'USA',
            'description': "A loop through the Wyoming Range with mixed terrain ranging from river valleys to high ridges. Features significant climbing, remote wilderness sections, and variable conditions. Part of the Rocky Mountain Slam, it attracts serious mountain runners seeking Hardrock qualification.",
            'month': 'August',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[8200,8800,9400,10000,10600,10000,9400,8800,9000,9600,10200,10800,11000,10600,10000,9400,8800,9200,9800,10400,10800,10400,9800,9200,8800,9200,9800,10400,10800,10400,9800,9200,8800,8400,8800,9200,9600,9200,8800,8400,8200,8200,8400,8600,8800,8600,8400,8200,8200,8200]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'scout-mountain-100',
            'name': 'Scout Mountain 100 Mile',
            'distance': '100 miles',
            'distance_miles': 100.0,
            'elevation_gain': '22,000 ft',
            'elevation_gain_ft': 22000,
            'location': 'Manila, Utah',
            'state': 'UT',
            'country': 'USA',
            'description': "A mountain loop race through the high plateaus and mountain terrain of northeast Utah. Starting at elevation with consistent climbing throughout, it features beautiful high-country scenery. Part of the Rocky Mountain Slam series and offers Hardrock-style mountain training in a less crowded environment.",
            'month': 'June',
            'cutoff_time': '36 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[8400,9000,9600,10200,10600,10200,9600,9000,9200,9800,10400,10800,10600,10000,9400,8800,9000,9600,10200,10600,10200,9600,9000,8600,8800,9400,10000,10400,10000,9400,8800,8400,8600,9000,9400,9600,9400,9000,8600,8400,8200,8200,8400,8600,8800,8600,8400,8200,8200,8400]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'lake-biwa-ultra-japan',
            'name': 'Lake Biwa Ultra Trail 100 km',
            'distance': '62.1 miles',
            'distance_miles': 62.1,
            'elevation_gain': '7,500 ft',
            'elevation_gain_ft': 7500,
            'location': 'Shiga Prefecture, Japan',
            'state': None,
            'country': 'Japan',
            'description': "An international qualifier featuring a loop around Lake Biwa, Japan's largest lake. Well-organized Japanese-style ultramarathon with excellent aid stations and a challenging trail profile. Noted as an official Hardrock qualifier, it attracts international competitors seeking to qualify for the prestigious Colorado race.",
            'month': 'April',
            'cutoff_time': '24 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[200,400,600,800,1000,1200,1400,1600,1600,1500,1400,1300,1200,1100,1000,900,800,700,600,500,400,300,400,500,600,700,800,900,1000,1100,1200,1300,1400,1500,1600,1500,1400,1300,1200,1100,1000,900,800,700,600,500,400,300,200,200,200,200]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'diagonale-des-fous-reunion',
            'name': 'Diagonale des Fous Trail',
            'distance': '105 miles',
            'distance_miles': 105.0,
            'elevation_gain': '27,000 ft',
            'elevation_gain_ft': 27000,
            'location': "Reunion Island, France",
            'state': None,
            'country': 'France',
            'description': "An extreme island ultramarathon crossing the volcanic island of Reunion from coast to coast through challenging terrain and unpredictable weather. With significant elevation gain over tropical rainforest and lava fields, it's one of the world's toughest 100+ milers. An official Hardrock qualifier attracting elite international runners.",
            'month': 'October',
            'cutoff_time': '36 hours',
            'difficulty': 'Expert',
            'gpx_available': 0,
            'elevation_profile_json': '[0,1000,2000,2500,3000,2500,2000,1500,1000,1500,2000,2500,3000,3500,3000,2500,2000,1500,1000,1500,2000,2500,3000,3500,3000,2500,2000,1500,1000,1500,2000,2500,3000,2500,2000,1500,1000,500,0,500,1000,1500,2000,1500,1000,500,0,100,100]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'transvulcania-spain',
            'name': 'Transvulcania Trail',
            'distance': '74 miles',
            'distance_miles': 74.0,
            'elevation_gain': '14,100 ft',
            'elevation_gain_ft': 14100,
            'location': 'La Palma, Canary Islands, Spain',
            'state': None,
            'country': 'Spain',
            'description': "A challenging island ultramarathon across the volcanic terrain of La Palma, Canary Islands. The course features steep volcanic climbs, technical descents, and stunning island scenery. An established international Hardrock qualifier known for attracting elite runners and testing mountain abilities in a unique environment.",
            'month': 'May',
            'cutoff_time': '32 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[500,1500,2500,3000,3200,2800,2000,1500,1000,1500,2000,2500,3000,3200,3000,2500,2000,1500,1000,1500,2000,2500,3000,3200,3000,2500,2000,1500,1000,1500,2000,2500,3000,2500,2000,1500,1000,800,600,400,200,300,400,500,600,500,400,300,500,500]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'ultra-trail-cape-town-south-africa',
            'name': 'Ultra-Trail Cape Town',
            'distance': '100 km',
            'distance_miles': 62.1,
            'elevation_gain': '9,840 ft',
            'elevation_gain_ft': 9840,
            'location': 'Cape Town, South Africa',
            'state': None,
            'country': 'South Africa',
            'description': "A trail race through the Table Mountain region featuring incredible scenic variety and technical terrain. The course includes steep climbs with iconic South African mountain landscape. Listed as an official Hardrock 100 qualifier, allowing international runners from the Southern Hemisphere to qualify.",
            'month': 'November',
            'cutoff_time': '24 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[150,1000,2000,2500,2800,2500,2000,1500,1000,1500,2000,2500,3000,2500,2000,1500,1000,1200,1400,1600,1800,1600,1400,1200,1000,800,1000,1200,1400,1200,1000,800,600,400,200,400,600,800,1000,800,600,400,200,100,100,150,150,150,150]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'grampian-peaks-scotland',
            'name': 'Grampian Peaks 100 km',
            'distance': '62.1 miles',
            'distance_miles': 62.1,
            'elevation_gain': '16,400 ft',
            'elevation_gain_ft': 16400,
            'location': 'Grampian Mountains, Scotland',
            'state': None,
            'country': 'Scotland',
            'description': "A challenging ultra through Scotland's Grampian Mountains featuring high-altitude alpine terrain and Scottish Highlands scenery. Known for variable weather and technical mountain terrain, it's been confirmed as an official Hardrock 100 qualifier for recent years, providing European mountain training.",
            'month': 'October',
            'cutoff_time': '18 hours',
            'difficulty': 'Hard',
            'gpx_available': 0,
            'elevation_profile_json': '[600,1200,2000,2500,2800,2600,2200,1800,1400,1600,2000,2400,2800,3000,2600,2200,1800,1400,1000,1200,1400,1600,1800,1600,1400,1200,1000,800,600,800,1000,1200,1400,1200,1000,800,600,400,200,400,600,800,1000,800,600,400,200,600,600]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'lavaredo-ultra-trail-italy',
            'name': 'Lavaredo Ultra Trail',
            'distance': '79 miles',
            'distance_miles': 79.0,
            'elevation_gain': '19,685 ft',
            'elevation_gain_ft': 19685,
            'location': 'Dolomites, Italy',
            'state': None,
            'country': 'Italy',
            'description': "An Alpine ultra trail through the stunning Dolomite Mountains of northern Italy. Features technical mountain terrain, high passes, and dramatic scenery of UNESCO-protected peaks. A prestigious international Hardrock qualifier showcasing European alpine running at its finest, requiring ITRA points for entry.",
            'month': 'September',
            'cutoff_time': '32 hours',
            'difficulty': 'Expert',
            'gpx_available': 0,
            'elevation_profile_json': '[1200,2000,2800,3200,3500,3200,2800,2400,2000,2200,2600,3000,3400,3600,3400,3000,2600,2200,2000,2200,2600,3000,3400,3600,3400,3000,2600,2200,1800,2000,2400,2800,3200,3000,2800,2400,2000,1600,1400,1200,1200,1200,1300,1400,1500,1400,1300,1200,1200]',
            'race_content_json': None,
            'training_location': None
        },
        {
            'slug': 'eiger-ultra-trail-switzerland',
            'name': 'Eiger Ultra Trail 101 km',
            'distance': '62.8 miles',
            'distance_miles': 62.8,
            'elevation_gain': '17,400 ft',
            'elevation_gain_ft': 17400,
            'location': 'Bernese Oberland, Switzerland',
            'state': None,
            'country': 'Switzerland',
            'description': "A breathtaking alpine trail race through the Bernese Oberland featuring iconic Swiss peaks including the Eiger. High-elevation technical terrain with stunning mountain scenery and challenging weather. An official Hardrock qualifier attracting experienced mountain runners from Europe seeking to qualify for Colorado.",
            'month': 'June',
            'cutoff_time': '20 hours',
            'difficulty': 'Expert',
            'gpx_available': 0,
            'elevation_profile_json': '[1400,2200,3000,3400,3600,3400,3000,2600,2200,2400,2800,3200,3600,3800,3600,3200,2800,2400,2000,2200,2600,3000,3400,3600,3400,3000,2600,2200,1800,2000,2400,2800,3200,3000,2800,2400,2000,1600,1400,1200,1400,1600,1800,1600,1400,1200,1400,1400]',
            'race_content_json': None,
            'training_location': None
        }
    ]

    for race in races:
        conn.execute('''
            INSERT INTO races (slug, name, distance, distance_miles, elevation_gain,
                elevation_gain_ft, location, state, country, description, month,
                cutoff_time, difficulty, gpx_available, elevation_profile_json,
                race_content_json, training_location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            race['slug'], race['name'], race['distance'], race['distance_miles'],
            race['elevation_gain'], race['elevation_gain_ft'], race['location'],
            race['state'], race['country'], race['description'], race['month'],
            race['cutoff_time'], race['difficulty'], race['gpx_available'],
            race['elevation_profile_json'], race.get('race_content_json'),
            race.get('training_location')
        ))

    # Seed Leadville sections as example
    leadville = conn.execute("SELECT id FROM races WHERE slug = 'leadville-100'").fetchone()
    if leadville:
        sections = [
            (leadville['id'], 1, 'Start to May Queen', 0, 13.5, '+800 ft',
             'Flat, runnable start on dirt roads and singletrack around Turquoise Lake. Deceptively easy terrain that tempts fast starts.',
             'Go out conservatively. Aim for 10-11 min/mile pace. Many runners blow up later from starting too fast here.',
             0, '🏃‍♂️'),
            (leadville['id'], 2, 'May Queen to Outward Bound', 13.5, 24, '+2,400 ft',
             'Steady climb through forests on Hagerman Pass Road. The grade is manageable but relentless.',
             'Settle into power hiking rhythm on the climbs. Eat and drink consistently — you need fuel for what comes next.',
             0, '⛰️'),
            (leadville['id'], 3, 'Outward Bound to Hope Pass', 24, 44, '+3,000 ft to 12,600 ft',
             'The race-defining climb. Steep ascent to Hope Pass at 12,620 ft, then brutal descent to Winfield. Most DNFs happen in this section due to altitude and pacing mistakes.',
             'Practice power hiking at target HR zones before race day. Start the climb conservatively — you can make up time on the descent. Watch for altitude sickness symptoms.',
             1, '🏔️'),
            (leadville['id'], 4, 'Winfield Turnaround to Twin Lakes', 44, 60.5, '+3,000 ft (return over Hope Pass)',
             'Back over Hope Pass in the heat of the day. Tired legs meet the hardest climb of the race for the second time.',
             'This is where mental toughness matters most. Break it into small goals: next tree, next switchback. Get in and out of Twin Lakes quickly.',
             1, '🔥'),
            (leadville['id'], 5, 'Twin Lakes to Halfmoon', 60.5, 76.5, '-2,400 ft',
             'Recovery section on the return trip. Downhill but legs are damaged from Hope Pass descent. Night is approaching.',
             'Keep moving, even slowly. Get your night gear ready at the aid station. Eat real food — pizza, soup, whatever you can stomach.',
             0, '🌅'),
            (leadville['id'], 6, 'Halfmoon to Finish', 76.5, 100, 'Rolling',
             'Final push through the night on familiar terrain. Mental game is everything as fatigue peaks.',
             'Run the flats, walk the hills, never sit down. Calculate your pace vs. cutoff at every aid station. Headlamp and extra batteries are critical.',
             0, '🌙'),
        ]
        for s in sections:
            conn.execute('''
                INSERT INTO race_sections
                    (race_id, section_number, name, miles_start, miles_end,
                     elevation_gain, description, strategy_tip, is_crux, icon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', s)

    # Seed test purchase
    conn.execute('''
        INSERT OR IGNORE INTO purchases
            (email, name, race_name, access_code, report_ready, report_content)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        'test@example.com', 'Test Runner', 'Leadville Trail 100', 'TEST-123', 1,
        '<h2>Your Personalized Leadville Trail 100 Plan</h2><p>This is a sample report.</p>'
    ))

    conn.commit()
    conn.close()
