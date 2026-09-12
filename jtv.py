import os
import re
import json
import base64
import time
import sys
import requests
from typing import Dict, Any
from datetime import datetime
from urllib.parse import urlparse, urlunparse

CHANNELS_URL = "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json"
COOKIE_URL = "https://allinonereborn2.online/jstrweb2/cookies.json"
SPORTS_COOKIE_URL = "https://allinonereborn2.online/jtv-fetch/jstarcookie/cookie.json"

M3U_FILE = "jtv.m3u"
JSON_FILE = "jtv.json"

USER_AGENT = "Sayan10"
MAX_RETRIES = 4
RETRY_DELAY = 5


# ---------------- RETRY FETCHER ----------------
def get_json(url: str) -> Any:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            fresh_url = f"{url}{'&' if '?' in url else '?'}t={int(time.time() * 1000)}"
            resp = requests.get(
                fresh_url,
                headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            if data is None or data == [] or data == {}:
                raise Exception("Empty response")
            print(f"[OK] Fetched {url} (attempt {attempt})")
            return data
        except Exception as e:
            last_error = e
            print(f"[WARN] Attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    raise Exception(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {last_error}")


# ---------------- COOKIE ----------------
def get_normal_cookie() -> str:
    try:
        data = get_json(COOKIE_URL)
    except Exception as e:
        print(f"[WARN] Cookie fetch failed: {e}")
        return ""

    if isinstance(data, str):
        return data
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("cookie"):
                return item["cookie"]
        return ""
    if isinstance(data, dict):
        return data.get("cookie") or ""
    return ""


# ---------------- SPORTS DATA ----------------
def get_sports_data() -> Dict[str, Any]:
    try:
        data = get_json(SPORTS_COOKIE_URL)
    except Exception as e:
        print(f"[WARN] Sports fetch failed: {e}")
        return {"sportsIds": set(), "sportsCookies": {}}

    sports_cookies = {}
    results = (data.get("successful_results") or []) + (data.get("failed_results") or [])

    for item in results:
        if not isinstance(item, dict):
            continue
        channel_id = item.get("channel_id")
        if not channel_id:
            continue
        final_url = (
            item.get("final_url")
            or (item.get("error_details") or {}).get("final_url")
            or ""
        )
        if not final_url:
            continue
        final_url = re.sub(r"/output/", "/WDVLive/", final_url, count=1, flags=re.I)
        sports_cookies[str(channel_id)] = final_url

    print(f"[INFO] Sports URLs loaded: {len(sports_cookies)}")
    return {"sportsIds": set(sports_cookies.keys()), "sportsCookies": sports_cookies}


# ---------------- HELPERS ----------------
def extract_keys(channel):
    key_id = channel.get("keyId") or ""
    key = channel.get("key") or ""
    if not key_id and isinstance(channel.get("clearkey"), dict) and channel.get("clearkey"):
        try:
            key_id, key = next(iter(channel["clearkey"].items()))
        except StopIteration:
            pass
    return key_id, key


def resolve_url(channel, sports_cookies):
    """Sports URL wins; fall back to channel URL (strip query string)."""
    channel_id = str(channel.get("id") or "")
    raw_url = channel.get("url") or ""

    if channel_id in sports_cookies:
        return sports_cookies[channel_id]

    # Strip any existing query string from base URL — cookie goes in #EXTHTTP
    parsed = urlparse(raw_url)
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, "", ""))
    return clean_url


# ---------------- M3U ENTRY ----------------
def create_channel_entry(channel, normal_cookie="", sports_cookies=None):
    if sports_cookies is None:
        sports_cookies = {}

    channel_id = str(channel.get("id") or "")
    name       = channel.get("name") or ""
    logo       = channel.get("logo") or ""
    group      = channel.get("group") or channel.get("category") or "Other"
    raw_url    = channel.get("url") or ""

    key_id, key = extract_keys(channel)
    final_url   = resolve_url(channel, sports_cookies)

    lines = []

    # EXTINF
    lines.append(
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'tvg-logo="{logo}" group-title="{group}",{name}'
    )

    # DASH / MPD
    is_mpd = (
        channel.get("type") == "dash"
        or bool(re.search(r"\.mpd(?:\?|$)", final_url, re.I))
        or bool(re.search(r"\.mpd(?:\?|$)", raw_url, re.I))
    )

    if is_mpd:
        lines.append("#KODIPROP:inputstream=inputstream.adaptive")
        lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
        if key_id and key:
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")
        elif channel.get("license_url"):
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f'#KODIPROP:inputstream.adaptive.license_key={channel["license_url"]}')

    # Cookie — proper #EXTHTTP, never appended to URL
    if normal_cookie and channel_id not in sports_cookies:
        cookie_json = json.dumps({"cookie": normal_cookie})
        lines.append(f"#EXTHTTP:{cookie_json}")

    lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
    lines.append(final_url)

    return "\n".join(lines)


# ---------------- JSON ENTRY ----------------
def build_channel_object(channel, normal_cookie="", sports_cookies=None):
    if sports_cookies is None:
        sports_cookies = {}

    key_id, key = extract_keys(channel)

    return {
        "id":     str(channel.get("id") or ""),
        "name":   channel.get("name") or "",
        "url":    resolve_url(channel, sports_cookies),
        "cookie": normal_cookie if str(channel.get("id") or "") not in sports_cookies else "",
        "keyId":  key_id,
        "key":    key,
        "logo":   channel.get("logo") or "",
        "group":  channel.get("group") or channel.get("category") or "Other",
    }


# ---------------- VALIDATE ----------------
def validate(channels, m3u_entries, json_entries):
    errors = []
    if not channels:
        errors.append("Channels list is empty")
    if not m3u_entries:
        errors.append("M3U output is empty")
    if not json_entries:
        errors.append("JSON output is empty")
    if len(m3u_entries) != len(json_entries):
        errors.append(f"Count mismatch: {len(m3u_entries)} M3U vs {len(json_entries)} JSON")
    if len(m3u_entries) < len(channels) * 0.8:
        errors.append(f"Too many channels dropped: expected ~{len(channels)}, got {len(m3u_entries)}")

    if errors:
        for e in errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] Validation passed: {len(m3u_entries)} channels")


# ---------------- GITHUB UPLOAD ----------------
def to_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def upload_to_github(filename: str, content: str):
    repo_owner = os.environ.get("GITHUB_OWNER") or os.environ.get("GITHUB_REPOSITORY", "").split("/")[0]
    repo_name  = os.environ.get("GITHUB_REPO")  or os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
    token      = os.environ.get("GITHUB_TOKEN")

    if not all([repo_owner, repo_name, token]):
        print(f"[WARN] GitHub credentials missing — skipping upload for {filename}")
        return

    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{filename}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Python-Script",
        "Accept": "application/vnd.github.v3+json",
    }

    existing = requests.get(api_url, headers=headers)
    sha = None
    if existing.status_code == 200:
        sha = existing.json().get("sha")
        existing_content = base64.b64decode(existing.json().get("content", "")).decode("utf-8")
        if existing_content.strip().replace("\r", "") == content.strip().replace("\r", ""):
            print(f"[INFO] No changes in {filename} — skipping commit")
            return

    payload = {
        "message": f"Auto-update {filename}: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "content": to_base64(content),
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(api_url, headers=headers, json=payload)
    if resp.ok:
        print(f"[OK] Uploaded {filename} to GitHub ({resp.status_code})")
    else:
        print(f"[ERROR] GitHub upload failed for {filename}: {resp.status_code} — {resp.text}", file=sys.stderr)


# ---------------- MAIN ----------------
def main():
    print(f"[START] {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")

    channels = get_json(CHANNELS_URL)
    if isinstance(channels, dict):
        channels = channels.get("channels") or channels.get("data") or []
    print(f"[INFO] Channels loaded: {len(channels)}")

    normal_cookie = get_normal_cookie()
    print(f"[INFO] Cookie: {'found' if normal_cookie else 'not found'}")

    sports_data = get_sports_data()

    m3u_entries  = []
    json_entries = []

    for ch in channels:
        try:
            m3u_entries.append(create_channel_entry(ch, normal_cookie, sports_data["sportsCookies"]))
            json_entries.append(build_channel_object(ch, normal_cookie, sports_data["sportsCookies"]))
        except Exception as e:
            print(f"[WARN] Skipped channel '{ch.get('name', '?')}': {e}", file=sys.stderr)

    validate(channels, m3u_entries, json_entries)

    timestamp   = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    m3u_content = f'#EXTM3U x-tvg-url="" updated="{timestamp}"\n\n' + "\n\n".join(m3u_entries)
    json_content = json.dumps(json_entries, indent=2, ensure_ascii=False)

    # Save locally
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"[INFO] M3U saved → {M3U_FILE}")

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        f.write(json_content)
    print(f"[INFO] JSON saved → {JSON_FILE}")

    # Optional GitHub API upload
    upload_to_github(M3U_FILE, m3u_content)
    upload_to_github(JSON_FILE, json_content)

    print("[DONE] All outputs written successfully.")


if __name__ == "__main__":
    main()
