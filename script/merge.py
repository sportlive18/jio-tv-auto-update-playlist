#!/usr/bin/env python3
import requests
import re
import os
from datetime import datetime

# ------------------ CONFIGURATION ------------------
PLAYLISTS = [
    {"name": "FANCODE", "icon": "🏏", "url": "https://raw.githubusercontent.com/drmlive/fancode-live-events/refs/heads/main/fancode.m3u"},
    {"name": "SONYLIV", "icon": "📺", "url": "https://raw.githubusercontent.com/drmlive/sliv-live-events/refs/heads/main/sonyliv.m3u"},
    {"name": "WILLOW", "icon": "🏏", "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/live_sports.m3u"},
    {"name": "PRIMEVIDEO", "icon": "📺", "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/primevideo_sports.m3u"},
    {"name": "JIO-TV", "icon": "📡", "url": "https://raw.githubusercontent.com/sportlink-10/playlist/refs/heads/main/jtvplus7.m3u"},
    {"name": "ZEE", "icon": "📺", "url": "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/zee.m3u"},
    {"name": "SONY", "icon": "📺", "url": "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/sony.m3u"},
    {"name": "SUN", "icon": "☀️", "url": "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/sun.m3u"},
    {"name": "Jio Hotstar", "icon": "⭐", "url": "https://raw.githubusercontent.com/sportlink-10/playlist/refs/heads/main/hotstar.m3u"},
]

OUTPUT_FILE = "Combined.m3u"
EPG_URL = "https://www.tsepg.cf/epg.xml.gz"

# ------------------ BRANDING SUFFIXES ------------------
SPORTLINK_SUFFIX = " | Sportlink"
VIRAT10_SUFFIX = " @virat10"

# ============================================================
# ------------------ SPORTS FOLDER SETUP --------------------
# ============================================================
SPORTS_CATEGORY = "Sports"

# If True, every sports channel is ALSO duplicated into its
# respective source folder (e.g. Sony Sports Ten 1 appears in
# both "Sports | Sportlink" AND "Sony | Sportlink").
DUPLICATE_SPORTS_IN_SOURCE = True

# Any channel whose title contains one of these goes to "Sports | Sportlink"
SPORTS_KEYWORDS = [
    # --- Generic ---
    "sport", "sports", "sports channel", "sportschannel",

    # --- Sports broadcasters / networks ---
    "star sports", "sony sports", "sony ten", "sony six", "sony espn",
    "ten sports", "ten 1", "ten 2", "ten 3", "ten 4", "ten 5",
    "espn", "eurosport", "sky sports", "fox sports", "bein sports",
    "dazn", "supersport", "astro supersport", "premier sports",
    "free sports", "ziggo sport", "sportv", "canal sport", "tsn",
    "willow", "willow cricket", "dd sports", "sports18",
    "star sports 1", "star sports 2", "star sports 3",
    "star sports select", "star sports first",
    "star sports hindi", "star sports tamil", "star sports telugu",

    # --- Sports by discipline ---
    "cricket", "football", "soccer", "boxing", "baseball", "basketball",
    "tennis", "badminton", "hockey", "kabaddi", "golf", "racing",
    "motogp", "formula 1", "formula one", "olympics", "wwe", "ufc",
    "wrestling", "athletics", "swimming", "volleyball", "handball",
    "rugby", "cycling", "snooker", "table tennis", "esports", "darts",
    "skiing", "surfing", "mma",

    # --- Leagues / tournaments / events ---
    "ipl", "isl", "t20", "odi", "test match", "world cup",
    "premier league", "champions league", "europa league", "copa",
    "serie a", "bundesliga", "ligue 1", "mls", "nba", "nfl", "mlb",
    "nhl", "fifa", "icc", "grand slam", "wimbledon", "us open",
    "australian open", "french open", "super bowl", "playoffs",
]

# ------------------ CATEGORY OVERRIDE PER SOURCE ------------------
SOURCE_CATEGORY_OVERRIDE = {
    "FANCODE":        "Fancode",
    "SONYLIV":        "SonyLIV",
    "Jio Hotstar":    "Jio Hotstar",
    "WILLOW":         "Willow",
    "PRIMEVIDEO":     "Prime Video",
    "HOTSTAR":        "Hotstar",
    "Sports Special": "Sports Special",
    "SONY":           "Sony",
    "ZEE":            "Zee",
    "SUN":            "Sun",
}

# ------------------ KEYWORD CATEGORY MAPPING ------------------
CATEGORY_MAP = {
    "Assamese":   ["assamese", "asomiya"],
    "Bengali":    ["bengali", "bangla", "bn"],
    "Bhojpuri":   ["bhojpuri", "bho"],
    "Gujarati":   ["gujarati", "guj"],
    "Haryanvi":   ["haryanvi"],
    "Kannada":    ["kannada", "kn"],
    "Malayalam":  ["malayalam", "ml"],
    "Marathi":    ["marathi", "mr"],
    "Odia":       ["odia", "oriya"],
    "Punjabi":    ["punjabi", "pa"],
    "Tamil":      ["tamil", "ta"],
    "Telugu":     ["telugu", "te"],
    "Urdu":       ["urdu"],
    "English":    ["english", "en"],
    "French":     ["french", "fr"],
    "Sun":        ["sun tv", "surya", "sun music", "sun news", "sun action", "sun life"],
    "Zee":        ["zee", "zee tv", "zee cinema", "zee news", "zee marathi", "zee bangla"],
    "Sony":       ["sony", "set", "sab", "sony liv", "sony max"],
    "Star":       ["star", "star plus", "star movies", "star gold"],
    "Colors":     ["colors", "viacom", "mtv"],
    "Discovery":  ["discovery", "dci"],
    "Nat Geo":    ["nat geo", "national geographic"],
    "Cartoon":    ["cartoon", "cn", "pogo", "nick"],
    "News":       ["news", "ndtv", "republic", "times now", "cnn", "bbc"],
    "Business":   ["business", "finance", "cnbc", "bloomberg"],
    "Devotional": ["devotional", "bhakti", "god"],
    "Entertainment": ["entertainment", "ent", "tv", "movies", "series"],
    "Infotainment":  ["infotainment", "documentary", "history", "discovery", "national geographic"],
    "Knowledge":     ["knowledge", "learning", "education"],
}
DEFAULT_CATEGORY = "Other"

# ------------------ CATEGORY ORDER (first = top) ------------------
CATEGORY_ORDER = [
    "Sports | Sportlink",
    "Sports Special | Sportlink",
    "Live Events | Sportlink",
    "Fancode | Sportlink",
    "SonyLIV | Sportlink",
    "Willow | Sportlink",
    "Prime Video | Sportlink",
    "Hotstar | Sportlink",
    "Jio Hotstar | Sportlink",
    "Sony | Sportlink",
    "Zee | Sportlink",
    "Sun | Sportlink",
]

# ------------------ HELPER FUNCTIONS ------------------
def fetch_playlist(url):
    try:
        print(f"  📥 Fetching: {url}")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        lines = resp.text.replace('\r\n', '\n').split('\n')
        print(f"  ✅ Fetched {len(lines)} lines")
        return lines
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return []

def clean_line(line):
    return line.strip()

def extract_channel_blocks(lines):
    block = []
    for line in lines:
        line = clean_line(line)
        if not line:
            continue
        if line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF') and block:
            yield block
            block = []
        block.append(line)
    if block:
        yield block

def get_channel_title(block):
    for line in block:
        if line.startswith('#EXTINF'):
            parts = line.rsplit(',', 1)
            if len(parts) > 1:
                return parts[1].strip()
    return None

def is_sports_channel(title):
    if not title:
        return False
    title_lower = title.lower()
    for kw in SPORTS_KEYWORDS:
        if kw in title_lower:
            return True
    return False

def categorize_channel(title):
    if not title:
        return DEFAULT_CATEGORY
    title_lower = title.lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return DEFAULT_CATEGORY

def fix_channel_block(block, category):
    """Apply @virat10 suffix to tvg-name and set group-title to category."""
    new_block = []
    for line in block:
        if line.startswith('#EXTINF'):
            if 'tvg-name=' in line:
                line = re.sub(
                    r'tvg-name="([^"]*)"',
                    lambda m: f'tvg-name="{m.group(1).strip()}{VIRAT10_SUFFIX}"',
                    line
                )
            else:
                parts = line.rsplit(',', 1)
                if len(parts) > 1:
                    title = parts[1].strip()
                    if line.startswith('#EXTINF:-1 '):
                        line = line.replace(
                            '#EXTINF:-1 ',
                            f'#EXTINF:-1 tvg-name="{title}{VIRAT10_SUFFIX}" ',
                            1
                        )

            if 'group-title=' in line:
                line = re.sub(r'group-title="[^"]*"', f'group-title="{category}"', line)
            else:
                line = re.sub(r'(#EXTINF:[^,]+)', r'\1 group-title="' + category + '"', line)

            new_block.append(line)
        else:
            new_block.append(line)
    return new_block

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting playlist merge with category grouping...")
    print("=" * 50)

    all_channels = []
    sports_count = 0
    duplicate_count = 0

    for playlist in PLAYLISTS:
        name = playlist["name"]
        icon = playlist["icon"]
        url = playlist["url"]
        print(f"\n📺 Processing: {icon} {name}")
        lines = fetch_playlist(url)
        if not lines:
            continue

        override_cat = SOURCE_CATEGORY_OVERRIDE.get(name)

        for block in extract_channel_blocks(lines):
            title = get_channel_title(block)
            sport = is_sports_channel(title)

            # ---------- Determine the SOURCE / KEYWORD category ----------
            # This is where the channel would normally live if we ignore sports.
            if override_cat:
                source_category = override_cat
            else:
                source_category = categorize_channel(title)
                if name == "JIO-TV":
                    source_category = f"Jiotv {source_category}"

            # ---------- Channel routing ----------
            if sport:
                # 1. Always add to the Sports folder
                all_channels.append((f"{SPORTS_CATEGORY}{SPORTLINK_SUFFIX}", block))
                sports_count += 1

                # 2. Also duplicate into its source folder
                if DUPLICATE_SPORTS_IN_SOURCE:
                    all_channels.append((f"{source_category}{SPORTLINK_SUFFIX}", block))
                    duplicate_count += 1

            else:
                # Non-sports channel -> only its source / keyword folder
                all_channels.append((f"{source_category}{SPORTLINK_SUFFIX}", block))

    # Group by category
    groups = {}
    for cat, block in all_channels:
        groups.setdefault(cat, []).append(block)

    # Order categories
    ordered_cats = []
    for cat in CATEGORY_ORDER:
        if cat in groups:
            ordered_cats.append(cat)
    remaining = sorted([cat for cat in groups.keys() if cat not in CATEGORY_ORDER])
    ordered_cats.extend(remaining)

    # Build output
    out_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

    total = 0
    for cat in ordered_cats:
        blocks = groups[cat]
        count = len(blocks)
        total += count
        out_lines.append(f'#===== {cat} ({count} channels) =====')
        for block in blocks:
            fixed = fix_channel_block(block, cat)
            out_lines.extend(fixed)
            out_lines.append('')

    # Remove trailing blank lines
    while out_lines and out_lines[-1] == '':
        out_lines.pop()

    # Write file
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))
            f.write('\n')
        print("\n" + "=" * 50)
        print(f"✅ Successfully created {OUTPUT_FILE}")
        print(f"📊 Total channels (with duplicates): {total}")
        print(f"🏆 Sports channels in Sports folder: {sports_count}")
        print(f"🔁 Sports channels duplicated to source folder: {duplicate_count}")
        print(f"📅 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"📁 File size: {os.path.getsize(OUTPUT_FILE)} bytes")
        print(f"\n📂 Categories (in order): {', '.join(ordered_cats)}")
    except Exception as e:
        print(f"❌ Error writing file: {e}")

if __name__ == "__main__":
    main()
