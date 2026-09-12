#!/usr/bin/env python3
"""
Merge JioTV __hdnea__ cookies from M3U playlist into the JSON channel list.
Outputs the transformed schema with cookie_expires in IST.
"""

import json
import re
import requests
from datetime import datetime, timezone, timedelta

M3U_URL  = "https://raw.githubusercontent.com/Sflex0719/STBPLUS/refs/heads/main/Zio.m3u"
JSON_URL = "https://sportlink18.pages.dev/Star.json"
OUT_FILE = "star2.json"

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------- helpers
def fetch(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def parse_m3u_cookies(m3u_text: str) -> dict:
    """Return {tvg_id: cookie_string} from the M3U playlist."""
    cookies = {}
    current_id = None

    for line in m3u_text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            m = re.search(r'tvg-id="([^"]*)"', line)
            current_id = m.group(1) if m else None
        elif line.startswith("#EXTHTTP:") and current_id:
            payload = line[len("#EXTHTTP:"):].strip()
            try:
                data = json.loads(payload)
                cookie = data.get("cookie", "")
                if cookie:
                    cookies[current_id] = cookie
            except json.JSONDecodeError:
                pass
            current_id = None

    return cookies

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
    """Extract exp=<unix_ts> from a __hdnea__ cookie and format it in IST."""
    if not cookie:
        return ""
    exp_match = re.search(r"exp=(\d+)", cookie)
    if not exp_match:
        return ""
    return format_expiry(exp_match.group(1))

def transform(ch: dict, cookie: str) -> dict:
    """Convert source JSON object to the target output schema."""
    return {
        "id":          str(ch.get("id", "")),
        "name":        ch.get("name", ""),
        "stream_url":  ch.get("url", ""),
        "cookie":      cookie,
        "cookie_expires": get_cookie_expiry(cookie),
        "key_id":      ch.get("keyId", ""),
        "key":         ch.get("key", ""),
        "logo":        ch.get("logo", ""),
    }

# ---------------------------------------------------------------- main
def merge_all(json_url: str, cookie_map: dict) -> list:
    """Merge cookies into every channel without filtering."""
    channels = json.loads(fetch(json_url))
    merged = 0
    result = []

    for ch in channels:
        cid = str(ch.get("id", ""))
        cookie = cookie_map.get(cid, "")
        if cookie:
            merged += 1
        result.append(transform(ch, cookie))

    print(f"[+] Processed {len(result)} channels")
    print(f"[+] Cookies merged for {merged}/{len(result)} channels")
    return result

if __name__ == "__main__":
    print("[*] Fetching M3U...")
    m3u = fetch(M3U_URL)
    print(f"[+] {len(m3u):,} bytes")

    print("[*] Parsing cookies...")
    cookie_map = parse_m3u_cookies(m3u)
    print(f"[+] Found {len(cookie_map)} cookie entries")

    print("[*] Fetching JSON and merging...")
    result = merge_all(JSON_URL, cookie_map)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[+] Written -> {OUT_FILE}")
