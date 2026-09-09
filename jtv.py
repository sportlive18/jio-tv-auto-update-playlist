import requests
import json
from datetime import datetime
import pytz
import os
import re
import sys

MAIN_LIST_URL = "https://sportlink-sky-f1.pages.dev/jtv.json"
GENERIC_COOKIE_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/cookie.json"
SPORTS_SOURCE_URL = "https://sonujson-v3.pages.dev/Data/sports.json"


def generate_m3u_playlist(channels_data):
    m3u_lines = ["#EXTM3U"]

    USER_AGENT = "Virat Paglu"
    ORIGIN = "https://www.jiotv.com/"
    REFERER = "https://www.jiotv.com/"

    for channel in channels_data:
        channel_id = channel.get("id", "")
        channel_name = channel.get("name", "")
        channel_logo = channel.get("logo", "")
        channel_url = channel.get("url", "")
        key_id = channel.get("keyId", "")
        key = channel.get("key", "")
        channel_cookie = channel.get("cookie", "")

        if key_id == "null" or key == "null" or not key_id or not key:
            continue
        if not channel_url or not channel_cookie:
            continue

        license_key = f"{key_id}:{key}"

        group_title = "Unknown"
        if "sports" in channel_url.lower() or "sport" in channel_name.lower():
            group_title = "Sports"
        elif "news" in channel_name.lower() or "news" in channel_url.lower():
            group_title = "News"
        elif "movie" in channel_name.lower() or "cinema" in channel_name.lower():
            group_title = "Movies"
        elif "music" in channel_name.lower():
            group_title = "Music"
        elif "entertainment" in channel_name.lower() or "tv" in channel_name.lower():
            group_title = "Entertainment"

        extinf = (
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{channel_name}" '
            f'tvg-logo="{channel_logo}" '
            f'group-title="{group_title}",{channel_name}'
        )
        m3u_lines.append(extinf)
        m3u_lines.append('#KODIPROP:inputstream.adaptive.manifest_type=mpd')
        m3u_lines.append('#KODIPROP:inputstream.adaptive.license_type=clearkey')
        m3u_lines.append(f'#KODIPROP:inputstream.adaptive.license_key={license_key}')
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')

        headers = {
            "cookie": channel_cookie,
            "Origin": ORIGIN,
            "Referer": REFERER,
        }
        headers_json = json.dumps(headers, separators=(',', ':'))
        m3u_lines.append(f'#EXTHTTP:{headers_json}')
        m3u_lines.append(channel_url)
        m3u_lines.append("")

    return "\n".join(m3u_lines)


def normalize_name(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def fetch_sports_source_channels():
    print("Fetching sports.json source (per-channel cookies)...")
    resp = requests.get(SPORTS_SOURCE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    raw_channels = data.get("channels", [])
    normalized = []
    for ch in raw_channels:
        normalized.append({
            "id": ch.get("id", ""),
            "name": ch.get("name", ""),
            "url": ch.get("stream_url", ""),
            "cookie": ch.get("cookie", ""),
            "keyId": ch.get("key_id", ""),
            "key": ch.get("key", ""),
            "logo": ch.get("logo", ""),
        })
    print(f"  -> {len(normalized)} channels fetched from sports.json source")
    return normalized


def fetch_and_update_jtv():
    # 1. Fetch main channel list
    print("Fetching main channel list...")
    channel_response = requests.get(MAIN_LIST_URL, timeout=30)
    channel_response.raise_for_status()
    channels_data = channel_response.json()
    print(f"  -> {len(channels_data)} channels in main list")

    # 2. Fetch generic cookie
    print("Fetching primary cookie source...")
    cookie_response = requests.get(GENERIC_COOKIE_URL, timeout=30)
    cookie_response.raise_for_status()
    cookie_data = cookie_response.json()
    print(f"  -> Cookie data type: {type(cookie_data)}, length: {len(cookie_data) if isinstance(cookie_data, list) else 'N/A'}")

    # 3. Extract generic cookie — handle both list and dict formats
    generic_cookie = None
    if isinstance(cookie_data, list):
        for item in cookie_data:
            if isinstance(item, dict) and "cookie" in item:
                generic_cookie = item["cookie"]
                break
    elif isinstance(cookie_data, dict) and "cookie" in cookie_data:
        generic_cookie = cookie_data["cookie"]

    if not generic_cookie:
        # Log the raw response to help debug
        print(f"❌ Cookie data received:\n{json.dumps(cookie_data, indent=2)[:500]}")
        raise ValueError("No cookie found in the primary source. Cannot continue.")

    print(f"  -> Generic cookie extracted (length: {len(generic_cookie)})")

    # 4. Current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist)
    formatted_time = current_time_ist.strftime("%d/%m/%Y, %I:%M:%S %p").lower()

    # 5. Fetch sports channels (per-channel cookies), placed first
    merged_channels = {}
    name_index = {}
    sports_added = 0
    try:
        sports_channels = fetch_sports_source_channels()
        for sch in sports_channels:
            cid = sch.get("id", "")
            if not cid:
                continue
            merged_channels[cid] = sch
            name_key = normalize_name(sch.get("name", ""))
            if name_key:
                name_index[name_key] = cid
            sports_added += 1
    except Exception as e:
        print(f"⚠️  Could not fetch sports.json source, continuing without it: {e}")

    # 6. Merge main-list channels (generic cookie), skipping duplicates
    main_added = 0
    main_skipped = 0
    for channel in channels_data:
        cid = channel.get("id", "")
        name_key = normalize_name(channel.get("name", ""))

        if cid in merged_channels or (name_key and name_key in name_index):
            main_skipped += 1
            continue

        merged_channels[cid] = {
            "id": cid,
            "name": channel.get("name", ""),
            "url": channel.get("url", ""),
            "cookie": generic_cookie,
            "keyId": channel.get("keyId", ""),
            "key": channel.get("key", ""),
            "logo": channel.get("logo", ""),
        }
        if name_key:
            name_index[name_key] = cid
        main_added += 1

    print(f"  -> {sports_added} channels from sports.json (own cookie, listed first)")
    print(f"  -> {main_added} channels from main list (generic cookie), {main_skipped} skipped as duplicates")

    # 7. Final structure
    updated_json = {
        "updatedAt": formatted_time,
        "channels": list(merged_channels.values()),
    }

    # 8. Save jtv.json
    print("Saving JSON file...")
    with open("jtv.json", "w", encoding="utf-8") as f:
        json.dump(updated_json, f, indent=2, ensure_ascii=False)
    print("✓ JSON saved as: jtv.json")

    # 9. Save jtv.m3u
    print("Generating M3U playlist...")
    m3u_content = generate_m3u_playlist(updated_json["channels"])
    with open("jtv.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("✓ M3U saved as: jtv.m3u")

    # 10. Stats
    total_channels = len(updated_json["channels"])
    valid_channels = len([
        c for c in updated_json["channels"]
        if c.get("keyId") not in (None, "null", "")
        and c.get("key") not in (None, "null", "")
    ])
    skipped_channels = total_channels - valid_channels

    print("\n" + "="*50)
    print("✅ SUMMARY")
    print("="*50)
    print(f"Total channels processed : {total_channels}")
    print(f"Valid channels in M3U    : {valid_channels}")
    print(f"Skipped (null keys)      : {skipped_channels}")
    print(f"Updated at               : {formatted_time}")
    print("="*50)


if __name__ == "__main__":
    try:
        fetch_and_update_jtv()
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)   # <-- non-zero exit so the workflow step fails visibly
