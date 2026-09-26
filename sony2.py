import json
import re
import requests
from datetime import datetime, timezone, timedelta

# ---------- configuration ----------
CHANNELS_URL = "https://sportlink-jtv.pages.dev/s.json"
COOKIES_URL  = "https://allinonereborn2.online/jstrweb2/cookies.json"
OUTPUT_FILE  = "sony.json"

IST = timezone(timedelta(hours=5, minutes=30))


# ---------- helper functions ----------
def format_expiry(exp_ts: str) -> str:
    try:
        dt = datetime.fromtimestamp(int(exp_ts), tz=IST)
    except (ValueError, OSError, TypeError):
        return ""
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.day}/{dt.month}/{dt.year} {hour12}:{dt.minute:02d}:{dt.second:02d} {ampm} IST"


def get_cookie_expiry(cookie: str) -> str:
    if not cookie:
        return ""
    exp_match = re.search(r"exp=(\d+)", cookie)
    return format_expiry(exp_match.group(1)) if exp_match else ""


# ---------- fetch channels ----------
try:
    channels_resp = requests.get(CHANNELS_URL, timeout=30)
    channels_resp.raise_for_status()
    channels = channels_resp.json()
    print(f"✅ Fetched {len(channels)} channels")
except Exception as e:
    print(f"❌ Failed to fetch channels: {e}")
    raise

# ---------- fetch cookie ----------
try:
    cookies_resp = requests.get(COOKIES_URL, timeout=30)
    cookies_resp.raise_for_status()
    cookie_data = cookies_resp.json()  # list: [{last_updated:...}, {cookie:...}]

    # Extract the single shared cookie
    shared_cookie = None
    for item in cookie_data:
        if "cookie" in item:
            shared_cookie = item["cookie"]
            break

    if not shared_cookie:
        raise ValueError("No cookie found in cookies.json")

    print(f"✅ Cookie fetched, expires: {get_cookie_expiry(shared_cookie)}")

except Exception as e:
    print(f"❌ Failed to fetch cookie: {e}")
    raise

# ---------- build output ----------
combined = []

for ch in channels:
    try:
        cid  = str(ch["id"])
        name = ch.get("name", "")
    except KeyError as e:
        print(f"⚠️  Skipping channel missing key {e}: {ch}")
        continue

    combined.append({
        "id":             cid,
        "name":           name,
        "stream_url":     ch.get("streamUrl", ""),
        "cookie":         shared_cookie,
        "cookie_expires": get_cookie_expiry(shared_cookie),
        "key_id":         ch.get("keyId", ""),
        "key":            ch.get("key", ""),
        "logo":           ch.get("logo", ""),
    })

# ---------- write result ----------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(combined, f, indent=2, ensure_ascii=False)

print(f"✅ JSON written to {OUTPUT_FILE} ({len(combined)} channels)")
