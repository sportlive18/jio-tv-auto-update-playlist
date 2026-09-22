import json
import re
import urllib.request
import sys

# ---------- Configuration ----------
JSON_URL = "https://sportlink-jtv.pages.dev/Sony.json"
PLAYLIST_URL = "https://premiumplugx.com/Sliv/sony_playlist.php?m3u"
OUTPUT_FILE = "sony5.m3u"
USER_AGENT = "virat@10"

# ---------- Helper functions ----------
def fetch_text(url):
    """Fetch plain text (used for the PHP playlist)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def fetch_json(url):
    """Fetch JSON data."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def extract_cookie_from_playlist(text):
    """
    Extract the hdnea Cookie from M3U text.
    Priority:
      1. '# Cookie:' line
      2. '#EXTVLCOPT:http-cookie=' line
      3. '"Cookie"' field inside '#EXTHTTP' JSON
    """
    # 1) Header comment: # Cookie: hdnea=...
    m = re.search(r"#\s*Cookie:\s*(hdnea=[^\s#]+)", text)
    if m:
        return m.group(1).strip()

    # 2) First #EXTVLCOPT:http-cookie=
    m = re.search(r"#EXTVLCOPT:http-cookie=(hdnea=[^\s\n]+)", text)
    if m:
        return m.group(1).strip()

    # 3) Cookie field inside #EXTHTTP JSON
    m = re.search(r'"Cookie"\s*:\s*"([^"]+)"', text)
    if m:
        return m.group(1).strip()

    return None

# ---------- M3U generation ----------
def build_m3u(channels, cookie):
    """Merge channel list and Cookie into an M3U file."""
    lines = ["#EXTM3U"]

    for ch in channels:
        tvg_id = ch.get("tvg_id", "")
        tvg_name = ch.get("tvg_name", "")
        group = ch.get("group_title", "")
        logo = ch.get("logo", "")
        url = ch.get("url", "")

        headers = ch.get("headers", {}) or {}
        referrer = headers.get("Referrer", "")
        origin = headers.get("Origin", "")

        # EXTINF line
        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" '
            f'tvg-logo="{logo}" group-title="{group}",{tvg_name}'
        )

        # EXTVLCOPT lines (for VLC / Tivimate)
        if cookie:
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
        if referrer:
            lines.append(f"#EXTVLCOPT:http-referrer={referrer}")
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

        # EXTHTTP line (for Kodi / OTT Navigator)
        http_headers = {
            "User-Agent": USER_AGENT,
            "Referrer": referrer,
            "Origin": origin,
        }
        if cookie:
            http_headers["Cookie"] = cookie

        # Remove empty values
        http_headers = {k: v for k, v in http_headers.items() if v}
        lines.append(f"#EXTHTTP:{json.dumps(http_headers, ensure_ascii=False)}")

        # URL
        lines.append(url)
        lines.append("")  # blank line separator

    return "\n".join(lines)

# ---------- Main ----------
def main():
    print("Downloading JSON channel list...")
    try:
        channels = fetch_json(JSON_URL)
    except Exception as e:
        print(f"Failed to fetch JSON: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(channels)} channels")

    print("Downloading PHP playlist to extract Cookie...")
    try:
        playlist_text = fetch_text(PLAYLIST_URL)
    except Exception as e:
        print(f"Failed to fetch playlist: {e}", file=sys.stderr)
        sys.exit(1)

    cookie = extract_cookie_from_playlist(playlist_text)

    if cookie:
        print(f"Extracted Cookie: {cookie[:60]}...")
    else:
        print("Warning: Could not extract Cookie from playlist. Cookie header will be omitted.")

    print("Generating M3U...")
    m3u_content = build_m3u(channels, cookie)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Successfully generated {OUTPUT_FILE} with {len(channels)} channels")

if __name__ == "__main__":
    main()
