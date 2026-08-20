import re
import json
import requests
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def format_expiry(exp_ts: str) -> str:
    """Convert a unix timestamp string to a 'D/M/YYYY H:MM:SS AM/PM IST' string."""
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
    """Extract the exp=<unix_ts> value from a __hdnea__-style cookie string, if present."""
    if not cookie:
        return ""
    exp_match = re.search(r"exp=(\d+)", cookie)
    return format_expiry(exp_match.group(1)) if exp_match else ""


def fetch_sports_channels():
    """
    Fetch data from the API, filter Star Sports channels,
    transform them into the target format, and save to star.json.
    """
    url = "https://undefeatable.streamxlive.workers.dev/"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return

    star_sports_channels = []

    for channel in data:
        name = channel.get("name", "")
        # Check category and name (case‑insensitive)
        if channel.get("category") == "Sports" and "star sports" in name.lower():
            cookie = channel.get("cookie")
            transformed = {
                "id": channel.get("id"),
                "name": channel.get("name"),
                "stream_url": channel.get("url"),
                "cookie": cookie,
                # Derived from the exp=<unix_ts> field inside the cookie, if present
                "cookie_expires": get_cookie_expiry(cookie),
                "key_id": channel.get("keyId"),
                "key": channel.get("key"),
                "logo": channel.get("logo")
            }
            star_sports_channels.append(transformed)

    # Write the result to star.json
    with open("star.json", "w", encoding="utf-8") as f:
        json.dump(star_sports_channels, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(star_sports_channels)} Star Sports channel(s) to star.json")


if __name__ == "__main__":
    fetch_sports_channels()
