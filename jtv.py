import requests
import json
from datetime import datetime
import pytz
import os
import re

MAIN_LIST_URL = "https://sportlink-sky-f1.pages.dev/jtv.json"
GENERIC_COOKIE_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/cookie.json"
SPORTS_SOURCE_URL = "https://sonujson-v3.pages.dev/Data/sports.json"


def generate_m3u_playlist(channels_data):
    """
    Generates an M3U playlist from the channel data.
    Uses each channel's own cookie (channel["cookie"]) and outputs
    the URL and headers in the new VLC‑compatible format.
    """
    m3u_lines = ["#EXTM3U"]

    # Customise these as needed
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

        # Skip channels with null/missing keyId, key, url or cookie
        if key_id == "null" or key == "null" or not key_id or not key:
            continue
        if not channel_url or not channel_cookie:
            continue

        license_key = f"{key_id}:{key}"

        # Simple grouping logic (same as before)
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

        # EXTINF line
        extinf = (
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{channel_name}" '
            f'tvg-logo="{channel_logo}" '
            f'group-title="{group_title}",{channel_name}'
        )
        m3u_lines.append(extinf)

        # KODIPROP lines
        m3u_lines.append('#KODIPROP:inputstream.adaptive.manifest_type=mpd')
        m3u_lines.append('#KODIPROP:inputstream.adaptive.license_type=clearkey')
        m3u_lines.append(f'#KODIPROP:inputstream.adaptive.license_key={license_key}')

        # VLC‑specific headers
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')

        headers = {
            "cookie": channel_cookie,
            "Origin": ORIGIN,
            "Referer": REFERER,
        }
        headers_json = json.dumps(headers, separators=(',', ':'))  # compact
        m3u_lines.append(f'#EXTHTTP:{headers_json}')

        # Plain stream URL
        m3u_lines.append(channel_url)
        m3u_lines.append("")   # blank line between entries

    return "\n".join(m3u_lines)


def normalize_name(name):
    """
    Normalizes a channel name for duplicate matching:
    lowercase, trim, collapse whitespace. e.g. "Star Sports 1  SD" and
    "star sports 1 sd" match, but "Star Sports 1 SD" and "Star Sports 1 HD"
    do not (SD/HD are kept, since they're different channels).
    """
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def fetch_sports_source_channels():
    """
    Fetches the sonujson sports.json source, which provides channels that
    each carry their own working cookie (instead of a shared generic one).
    Returns a list of channel dicts normalized to the main schema:
    id, name, url, cookie, keyId, key, logo
    """
    print("Fetching sports.json source (per-channel cookies)...")
    resp = requests.get(SPORTS_SOURCE_URL)
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
    """
    Fetches the main channel list and the primary cookie file, merges the
    generic cookie into each channel, then merges in the sonujson sports.json
    source (which provides its own per-channel working cookies) — channels
    with a matching id get their cookie/url/keys replaced by the sports.json
    version, and any new channels from that source are appended.
    Finally updates jtv.json and jtv.m3u.
    """
    try:
        # 1. Fetch the main channel list
        print("Fetching main channel list...")
        channel_response = requests.get(MAIN_LIST_URL)
        channel_response.raise_for_status()
        channels_data = channel_response.json()

        # 2. Fetch the primary cookies (single generic cookie)
        print("Fetching primary cookie source...")
        cookie_response = requests.get(GENERIC_COOKIE_URL)
        cookie_response.raise_for_status()
        cookie_data = cookie_response.json()

        # 3. Extract the generic cookie value
        generic_cookie = None
        if isinstance(cookie_data, list) and len(cookie_data) > 1:
            for item in cookie_data:
                if "cookie" in item:
                    generic_cookie = item["cookie"]
                    break

        if not generic_cookie:
            print("Warning: No cookie found in the primary source.")
            return

        # 4. Current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        current_time_ist = datetime.now(ist)
        formatted_time = current_time_ist.strftime("%d/%m/%Y, %I:%M:%S %p").lower()

        # 5. Fetch sports.json source first and add its channels FIRST, so
        #    they appear at the top of jtv.json / jtv.m3u. These carry their
        #    own working cookie.
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
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not fetch sports.json source, continuing without it: {e}")
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse sports.json source, continuing without it: {e}")

        # 6. Add main-list channels AFTER, using the generic cookie — but skip
        #    any channel already covered by the sports.json source (matched
        #    by id or by normalized name), so there are no duplicates.
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

        # 8. Save the updated JSON to jtv.json
        print("Saving JSON file...")
        json_filename = "jtv.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(updated_json, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON saved as: {json_filename}")

        # 9. Generate and save M3U playlist (uses each channel's own cookie)
        print("Generating M3U playlist...")
        m3u_content = generate_m3u_playlist(updated_json["channels"])

        m3u_filename = "jtv.m3u"
        with open(m3u_filename, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"✓ M3U saved as: {m3u_filename}")

        # 10. Backup files
        timestamp = datetime.now(ist).strftime('%Y%m%d_%H%M%S')

        backup_json = f"jtv_backup_{timestamp}.json"
        with open(backup_json, "w", encoding="utf-8") as f:
            json.dump(updated_json, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON backup saved as: {backup_json}")

        backup_m3u = f"jtv_backup_{timestamp}.m3u"
        with open(backup_m3u, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"✓ M3U backup saved as: {backup_m3u}")

        # 11. Stats
        total_channels = len(updated_json["channels"])
        valid_channels = len([c for c in updated_json["channels"] if c.get("keyId") != "null" and c.get("key") != "null" and c.get("keyId") and c.get("key")])
        skipped_channels = total_channels - valid_channels

        print("\n" + "="*50)
        print("✅ SUMMARY")
        print("="*50)
        print(f"Total channels processed: {total_channels}")
        print(f"Valid channels in M3U: {valid_channels}")
        print(f"Skipped channels (null keys): {skipped_channels}")
        print(f"User-Agent: Sayan10")   # This remains informational
        print(f"Updated at: {formatted_time}")
        print("="*50)

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    fetch_and_update_jtv()
