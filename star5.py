import json
import re
import requests
from datetime import datetime, timezone, timedelta

# ---------- configuration ----------
CHANNELS_URL = "https://sportlink18.pages.dev/jtvp.json"
COOKIES_URL  = "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/sportsbiscuit.json"
OUTPUT_FILE  = "star.json"

IST = timezone(timedelta(hours=5, minutes=30))

# ---------- your helper functions ----------
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

# ---------- helper to extract __hdnea__ ----------
def extract_hdnea(final_url: str) -> str | None:
    """Return the full __hdnea__ query string (including prefix) from a URL."""
    match = re.search(r"(__hdnea__=[^&]+)", final_url)
    return match.group(1) if match else None

# ---------- fetch data ----------
channels_resp = requests.get(CHANNELS_URL)
channels_resp.raise_for_status()
channels = channels_resp.json()

cookies_resp = requests.get(COOKIES_URL)
cookies_resp.raise_for_status()
cookie_data = cookies_resp.json()

# Build a lookup: channel_id -> final_url
failed_map = {}
for item in cookie_data.get("failed_results", []):
    cid = str(item["channel_id"])
    failed_map[cid] = item["error_details"]["final_url"]

# ---------- build combined output ----------
combined = []

for ch in channels:
    cid = str(ch["id"])
    final_url = failed_map.get(cid)
    if not final_url:
        print(f"Warning: no cookie URL for channel {cid} ({ch['name']})")
        continue

    hdnea_full = extract_hdnea(final_url)
    if not hdnea_full:
        print(f"Warning: no __hdnea__ token found for channel {cid}")
        continue

    cookie_expires = get_cookie_expiry(hdnea_full)

    combined.append({
        "id": cid,
        "name": ch["name"],
        "stream_url": ch["url"],
        "cookie": hdnea_full,
        "cookie_expires": cookie_expires,
        "key_id": ch["keyId"],
        "key": ch["key"],
        "logo": ch["logo"],
    })

# ---------- write result ----------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(combined, f, indent=2, ensure_ascii=False)

print(f"✅ Combined JSON written to {OUTPUT_FILE} ({len(combined)} channels)")
