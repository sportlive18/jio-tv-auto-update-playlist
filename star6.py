#!/usr/bin/env python3
import re
import json
import requests
from datetime import datetime, timedelta, timezone

# Timezone for IST
IST = timezone(timedelta(hours=5, minutes=30))

# M3U source
M3U_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/jtv5.m3u"

# Allowed JioTV domains
ALLOWED_DOMAINS = ["jiotvpllive.cdn.jio.com", "jiotvmblive.cdn.jio.com"]

def format_expiry(exp_ts: str) -> str:
    """Convert a unix timestamp string to 'D/M/YYYY H:MM:SS AM/PM IST'."""
    try:
        dt = datetime.fromtimestamp(int(exp_ts), tz=IST)
    except (ValueError, OSError, TypeError):
        return ""
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.day}/{dt.month}/{dt.year} {hour12}:{dt.minute:02d}:{dt.second:02d} {ampm} IST"

def get_cookie_expiry(cookie: str) -> str:
    """Extract exp=<unix_ts> from a __hdnea__ cookie string."""
    if not cookie:
        return ""
    exp_match = re.search(r"exp=(\d+)", cookie)
    return format_expiry(exp_match.group(1)) if exp_match else ""

def parse_m3u(content: str):
    """Yield blocks of lines, each block corresponding to one channel entry."""
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            block = [lines[i]]
            i += 1
            while i < len(lines) and (lines[i].startswith('#') or lines[i].strip() == ''):
                if lines[i].strip() != '':
                    block.append(lines[i].strip())
                i += 1
            if i < len(lines) and not lines[i].startswith('#'):
                block.append(lines[i].strip())
                i += 1
            yield block
        else:
            i += 1

def extract_from_block(block):
    """
    Parse a block and return a dict if it's a Star Sports channel from JioTV.
    Returns None if it doesn't match the criteria.
    """
    extinf = None
    tvg_id = None
    tvg_name = None
    tvg_logo = None
    display_name = None
    license_key = None
    stream_url = None
    cookie = None

    for line in block:
        if line.startswith('#EXTINF'):
            extinf = line
            tvg_id = re.search(r'tvg-id="([^"]+)"', line)
            tvg_id = tvg_id.group(1) if tvg_id else None
            tvg_name = re.search(r'tvg-name="([^"]+)"', line)
            tvg_name = tvg_name.group(1) if tvg_name else None
            tvg_logo = re.search(r'tvg-logo="([^"]+)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else None
            name_match = re.search(r',([^,]+)$', line)
            display_name = name_match.group(1).strip() if name_match else None
        elif line.startswith('#KODIPROP:inputstream.adaptive.license_key'):
            val = line.split('=', 1)[1] if '=' in line else ''
            if ':' in val:
                key_id, key = val.split(':', 1)
                license_key = (key_id.strip(), key.strip())
        elif not line.startswith('#'):
            stream_url = line.strip()
            token_match = re.search(r'__hdnea__=([^&]+)', stream_url)
            if token_match:
                cookie = token_match.group(1)
                base_url = re.sub(r'\?.*', '', stream_url)
            else:
                base_url = stream_url
            stream_url = base_url

    # --- Filtering ---
    # 1. Must be a Star Sports channel
    name_to_check = display_name or tvg_name or ''
    if 'star sports' not in name_to_check.lower():
        return None

    # 2. Must be from JioTV (allowed domains)
    if not any(domain in stream_url for domain in ALLOWED_DOMAINS):
        return None

    # 3. Exclude digital-only streams (if "Digital" appears in the name)
    if 'digital' in name_to_check.lower():
        return None

    # Build JSON object
    obj = {
        "id": tvg_id,
        "name": display_name or tvg_name,
        "stream_url": stream_url,
        "cookie": cookie,
        "cookie_expires": get_cookie_expiry(cookie) if cookie else "",
        "key_id": license_key[0] if license_key else None,
        "key": license_key[1] if license_key else None,
        "logo": tvg_logo
    }
    return obj

def main():
    print(f"Fetching M3U from {M3U_URL} ...")
    try:
        resp = requests.get(M3U_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to download M3U: {e}")
        return

    content = resp.text
    star_channels = []

    for block in parse_m3u(content):
        obj = extract_from_block(block)
        if obj:
            star_channels.append(obj)

    # Write to star2.json
    with open("star2.json", "w", encoding="utf-8") as f:
        json.dump(star_channels, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(star_channels)} Star Sports channel(s) (JioTV only) to star2.json")

if __name__ == "__main__":
    main()
