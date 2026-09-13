import os
import sys
import json
import base64
import requests
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse, urlunparse

CHANNELS_URL = "https://sportlink-sky-f1.pages.dev/jtv.json"
COOKIE_URL = "https://allinonereborn2.online/jstrweb2/cookies.json"
SPORTS_COOKIE_URL = "https://allinonereborn2.online/jtv-fetch/jstarcookie/cookie.json"

UPLOAD_TO_GITHUB = True
USER_AGENT = "Virat Kohli 🐐"

TIMEOUT = 30
GITHUB_FILE_PATH = "jtvplus3.m3u"

# ---------------------------------------------------------------------------
# HTTP session (with retries + timeouts)
# ---------------------------------------------------------------------------
_session = requests.Session()
_session.headers.update({"Cache-Control": "no-cache", "Pragma": "no-cache"})

try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    _retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "PUT"]),
    )
    _adapter = HTTPAdapter(max_retries=_retry)
    _session.mount("https://", _adapter)
    _session.mount("http://", _adapter)
except Exception:  # pragma: no cover - urllib3 always ships with requests
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def to_base64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def get_json(url: str) -> Any:
    sep = "&" if "?" in url else "?"
    fresh_url = f"{url}{sep}t={int(datetime.now().timestamp() * 1000)}"
    resp = _session.get(fresh_url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def split_url_query(url: str) -> Tuple[str, Optional[str]]:
    """Return (base_url, query_string). query_string is None if absent."""
    parsed = urlparse(url)
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, "", ""))
    return base, (parsed.query or None)


def _clean_cookie(cookie: str) -> str:
    """Strip leading '?'/'&' so we never build URLs like '...?&cookie=...'."""
    cookie = (cookie or "").strip()
    while cookie.startswith(("?", "&")):
        cookie = cookie[1:]
    return cookie


def _extract_cookie(data: Any) -> str:
    """Cookies endpoint can return a string, a dict, or a list of dicts."""
    if isinstance(data, str):
        return _clean_cookie(data)

    if isinstance(data, dict):
        for key in ("cookie", "cookies", "value"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return _clean_cookie(value)
        return ""

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                value = item.get("cookie")
                if isinstance(value, str) and value.strip():
                    return _clean_cookie(value)
            elif isinstance(item, str) and item.strip():
                return _clean_cookie(item)

    return ""


def _as_channel_list(data: Any) -> list:
    """The channels endpoint may return a bare list or a wrapped object."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("channels", "data", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
def get_normal_cookie() -> str:
    try:
        return _extract_cookie(get_json(COOKIE_URL))
    except Exception as exc:
        print(f"⚠️  Could not load normal cookie: {exc}")
        return ""


def get_sports_data() -> Dict[str, Any]:
    try:
        data = get_json(SPORTS_COOKIE_URL)
    except Exception as exc:
        print(f"⚠️  Could not load sports cookies: {exc}")
        return {"sportsIds": set(), "sportsCookies": {}}

    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = list(data.get("successful_results") or []) + list(data.get("failed_results") or [])
    else:
        results = []

    sports_cookies: Dict[str, str] = {}

    for item in results:
        if not isinstance(item, dict):
            continue

        channel_id = item.get("channel_id")
        if channel_id in (None, ""):
            continue

        error_details = item.get("error_details")
        if not isinstance(error_details, dict):
            error_details = {}

        final_url = item.get("final_url") or error_details.get("final_url", "")
        if not final_url:
            continue

        sports_cookies[str(channel_id)] = str(final_url).replace("/output/", "/WDVLive/")

    return {"sportsIds": set(sports_cookies), "sportsCookies": sports_cookies}


# ---------------------------------------------------------------------------
# Playlist generation
# ---------------------------------------------------------------------------
def create_channel_entry(
    channel: Dict[str, Any],
    normal_cookie: str = "",
    sports_cookies: Optional[Dict[str, str]] = None,
) -> str:
    if not isinstance(channel, dict):
        return ""

    sports_cookies = sports_cookies or {}

    name = channel.get("name", "") or ""
    logo = channel.get("logo", "") or ""
    group = channel.get("group") or channel.get("category") or "Other"
    url = channel.get("url", "") or ""
    channel_id = str(channel.get("id", "") or "")

    if not url:
        return ""

    lines = [
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'tvg-logo="{logo}" group-title="{group}",{name}'
    ]

    # ---- DASH / MPD handling -------------------------------------------
    is_mpd = channel.get("type") == "dash" or ".mpd" in url.lower()

    if is_mpd:
        lines.append("#KODIPROP:inputstream=inputstream.adaptive")
        lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")

        license_key = None

        if channel.get("keyId") and channel.get("key"):
            license_key = f"{channel['keyId']}:{channel['key']}"
        else:
            clearkey = channel.get("clearkey")
            if isinstance(clearkey, dict) and clearkey:
                key_id, key = next(iter(clearkey.items()))
                license_key = f"{key_id}:{key}"
            elif channel.get("license_url"):
                license_key = channel["license_url"]

        if license_key:
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={license_key}")

    # ---- Build the final URL -------------------------------------------
    sports_url = sports_cookies.get(channel_id)

    if sports_url:
        final_url_with_query = sports_url
    elif normal_cookie:
        sep = "&" if "?" in url else "?"
        final_url_with_query = f"{url}{sep}{normal_cookie}"
    else:
        final_url_with_query = url

    base_url, cookie_query = split_url_query(final_url_with_query)

    # Cookie moves into the #EXTHTTP header, so the stream URL stays clean.
    if cookie_query:
        lines.append("#EXTHTTP:" + json.dumps({"cookie": cookie_query}))

    lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
    lines.append(base_url)

    return "\n".join(lines)


def generate_m3u() -> str:
    channels = _as_channel_list(get_json(CHANNELS_URL))
    normal_cookie = get_normal_cookie()
    sports_data = get_sports_data()

    print(f"Channels loaded: {len(channels)}")
    print(f"Sports-specific URLs loaded: {len(sports_data['sportsIds'])}")

    entries = []
    for ch in channels:
        entry = create_channel_entry(ch, normal_cookie, sports_data["sportsCookies"])
        if entry:
            entries.append(entry)

    print(f"Channels generated: {len(entries)}")
    return "#EXTM3U\n\n" + "\n\n".join(entries) + "\n"


# ---------------------------------------------------------------------------
# GitHub upload
# ---------------------------------------------------------------------------
def upload_to_github(content: str) -> bool:
    if not UPLOAD_TO_GITHUB:
        print("⚠️  Upload disabled by UPLOAD_TO_GITHUB flag. Skipping.")
        return False

    repo_owner = os.environ.get("GITHUB_OWNER")
    repo_name = os.environ.get("GITHUB_REPO")
    token = os.environ.get("GITHUB_TOKEN")

    if not all([repo_owner, repo_name, token]):
        print("⚠️  GitHub credentials missing. Skipping upload.")
        return False

    api_url = (
        f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        f"/contents/{GITHUB_FILE_PATH}"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Python-Script",
        "Accept": "application/vnd.github.v3+json",
    }

    # Fetch existing file (to get its sha / compare content)
    sha = None
    existing_content = ""
    try:
        existing_resp = _session.get(api_url, headers=headers, timeout=TIMEOUT)
    except Exception as exc:
        print(f"❌ GitHub lookup failed: {exc}")
        return False

    if existing_resp.status_code == 200:
        existing_json = existing_resp.json()
        sha = existing_json.get("sha")
        if existing_json.get("content"):
            try:
                existing_content = base64.b64decode(existing_json["content"]).decode("utf-8")
            except Exception:
                existing_content = ""
    elif existing_resp.status_code not in (404,):
        print(f"❌ GitHub lookup failed: {existing_resp.status_code} - {existing_resp.text}")
        return False

    def normalize(s: str) -> str:
        return s.strip().replace("\r", "")

    if sha and normalize(existing_content) == normalize(content):
        print("No changes detected. Skipping commit.")
        return True

    payload = {
        "message": f"Auto update playlist {datetime.now().isoformat(timespec='seconds')}",
        "content": to_base64(content),
    }
    # Only send "sha" when updating an existing file — GitHub rejects a null sha.
    if sha:
        payload["sha"] = sha

    try:
        put_resp = _session.put(api_url, headers=headers, json=payload, timeout=TIMEOUT)
    except Exception as exc:
        print(f"❌ GitHub upload failed: {exc}")
        return False

    if not put_resp.ok:
        print(f"❌ GitHub upload failed: {put_resp.status_code} - {put_resp.text}")
        return False

    print(f"✅ GitHub upload successful ({put_resp.status_code})")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(output_file: str = GITHUB_FILE_PATH) -> bool:
    try:
        m3u = generate_m3u()

        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(m3u)
        print(f"📁 Playlist saved locally as '{output_file}'")

        upload_to_github(m3u)

        print("✅ Playlist updated successfully")
        return True
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
