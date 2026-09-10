import re
import json
import time
import urllib.request
import urllib.error

CHANNELS_URL = "https://raw.githubusercontent.com/sportlive18/Sky-F1/refs/heads/main/jtv.json"
COOKIE_URL = "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/biscuit.json"
SPORTS_COOKIE_URL = "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/sportsbiscuit.json"

M3U_FILE = "jtv.m3u"
JSON_FILE = "jtv.json"

USER_AGENT = "Sayan10"


# ---------------- JSON FETCHER ----------------
def get_json(url: str):
    fresh_url = f"{url}{'&' if '?' in url else '?'}t={int(time.time() * 1000)}"

    req = urllib.request.Request(
        fresh_url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urllib.request.urlopen(req) as response:
        if not (200 <= response.status < 300):
            raise Exception(f"Failed to fetch {url}: {response.status}")
        raw = response.read().decode("utf-8")

    return json.loads(raw)


# ---------------- NORMAL COOKIE ----------------
def get_normal_cookie() -> str:
    data = get_json(COOKIE_URL)

    if isinstance(data, str):
        return data

    if isinstance(data, list):
        for item in data:
            if item and isinstance(item, dict) and item.get("cookie"):
                return item.get("cookie") or ""
        return ""

    if isinstance(data, dict):
        return data.get("cookie") or ""

    return ""


# ---------------- SPORTS DATA ----------------
def get_sports_data():
    data = get_json(SPORTS_COOKIE_URL)

    sports_cookies = {}
    results = []
    results.extend(data.get("successful_results") or [])
    results.extend(data.get("failed_results") or [])

    for item in results:
        if not isinstance(item, dict):
            continue
        if not item.get("channel_id"):
            continue

        error_details = item.get("error_details") or {}
        final_url = (
            item.get("final_url")
            or error_details.get("final_url")
            or ""
        )
        if not final_url:
            continue

        # Change /output/ to /WDVLive/ while keeping query string unchanged.
        final_url = re.sub(r"/output/", "/WDVLive/", final_url, count=1, flags=re.I)
        sports_cookies[str(item["channel_id"])] = final_url

    return {
        "sportsIds": set(sports_cookies.keys()),
        "sportsCookies": sports_cookies,
    }


# ---------------- SHARED HELPERS ----------------
def extract_keys(channel):
    key_id = channel.get("keyId") or ""
    key = channel.get("key") or ""

    if not key_id and isinstance(channel.get("clearkey"), dict) and channel.get("clearkey"):
        try:
            key_id, key = next(iter(channel["clearkey"].items()))
        except StopIteration:
            pass

    return key_id, key


def resolve_final_url(channel, sports_cookies):
    """Return the stream URL, sports override wins."""
    channel_id = str(channel.get("id") or "")
    url = channel.get("url") or ""
    return sports_cookies.get(channel_id) or url


# ---------------- M3U BUILDER ----------------
def create_channel_entry(channel, normal_cookie="", sports_cookies=None):
    if sports_cookies is None:
        sports_cookies = {}

    channel_id = str(channel.get("id") or "")
    name = channel.get("name") or ""
    logo = channel.get("logo") or ""
    group = channel.get("group") or channel.get("category") or "Other"
    url = channel.get("url") or ""

    key_id, key = extract_keys(channel)
    final_url = resolve_final_url(channel, sports_cookies)

    lines = []

    # EXTINF with tvg-id
    lines.append(
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'tvg-logo="{logo}" group-title="{group}",{name}'
    )

    # Detect DASH/MPD
    is_mpd = (
        channel.get("type") == "dash"
        or bool(re.search(r"\.mpd(?:\?|$)", final_url, re.I))
        or bool(re.search(r"\.mpd(?:\?|$)", url, re.I))
    )

    if is_mpd:
        lines.append("#KODIPROP:inputstream=inputstream.adaptive")
        lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")

        if key_id and key:
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(
                f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}"
            )
        elif channel.get("license_url"):
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(
                f'#KODIPROP:inputstream.adaptive.license_key={channel.get("license_url")}'
            )

    # EXTHTTP cookie (only if we actually have one)
    if normal_cookie:
        # Ensure cookie has proper JSON escaping
        cookie_json = json.dumps({"cookie": normal_cookie})
        lines.append(f"#EXTHTTP:{cookie_json}")

    # VLC user-agent
    lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

    lines.append(final_url)
    return "\n".join(lines)


# ---------------- JSON BUILDER ----------------
def build_channel_object(channel, normal_cookie="", sports_cookies=None):
    if sports_cookies is None:
        sports_cookies = {}

    key_id, key = extract_keys(channel)

    return {
        "id": str(channel.get("id") or ""),
        "name": channel.get("name") or "",
        "url": resolve_final_url(channel, sports_cookies),
        "cookie": normal_cookie,
        "keyId": key_id,
        "key": key,
        "logo": channel.get("logo") or "",
    }


# ---------------- GENERATE ----------------
def generate_outputs():
    channels = get_json(CHANNELS_URL)
    normal_cookie = get_normal_cookie()
    sports_data = get_sports_data()

    print(f"Channels loaded: {len(channels)}")
    print(f"Sports-specific URLs loaded: {len(sports_data['sportsIds'])}")

    m3u_entries = []
    json_entries = []

    for channel in channels:
        m3u_entries.append(
            create_channel_entry(channel, normal_cookie, sports_data["sportsCookies"])
        )
        json_entries.append(
            build_channel_object(channel, normal_cookie, sports_data["sportsCookies"])
        )

    print(f"Channels generated: {len(m3u_entries)}")

    m3u_content = "\n\n".join(["#EXTM3U", ""] + m3u_entries)
    json_content = json.dumps(json_entries, indent=2, ensure_ascii=False)

    return m3u_content, json_content


# ---------------- MAIN ----------------
if __name__ == "__main__":
    m3u_content, json_content = generate_outputs()

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        f.write(json_content)

    print(f"M3U saved to {M3U_FILE}")
    print(f"JSON saved to {JSON_FILE}")
