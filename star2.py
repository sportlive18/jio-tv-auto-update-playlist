import urllib.request
import urllib.parse
import json
import re

# ---------- CONFIG ----------
COOKIE_URL = "https://premiumplugx.com/htt/hot.php?playlist=1"
JSON_URL   = "https://sportlink18.pages.dev/star.json"
OUTPUT     = "Star2.m3u"

USER_AGENT = "Virat Kohli"
REFERER    = "https://www.hotstar.com/"
ORIGIN     = "https://www.hotstar.com"
TIMEOUT    = 15
# ----------------------------

UA_MOZ = "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"


def http_get(url, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA_MOZ})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def fetch_cookie(url):
    """Return cookie string from a playlist or plain-text endpoint."""
    text = http_get(url, headers={"User-Agent": "OTT Navigator"})

    # 1) #EXTVLCOPT:http-cookie=... style
    m = re.search(r"#EXTVLCOPT:http-cookie=([^\s\r\n]+)", text)
    if m:
        return m.group(1).strip()

    # 2) bare hdntl=... cookie
    m = re.search(r"(hdntl=[^\s\r\n&\"']+)", text)
    if m:
        return m.group(1).strip()

    # 3) generic "Cookie: ..." header line
    m = re.search(r"Cookie:\s*([^\r\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 4) fallback: whole body if it looks like a cookie
    stripped = text.strip()
    if stripped and "=" in stripped and len(stripped) < 4000:
        return stripped

    raise RuntimeError("Cookie not found in response")


def fetch_json(url):
    text = http_get(url, headers={"User-Agent": UA_MOZ})
    return json.loads(text)


def build_url(url, cookie):
    """Append auth params as query string for Hotstar CDN."""
    sep = "&" if "?" in url else "?"
    params = {
        "cookie": cookie,
        "referer": REFERER,
        "origin": ORIGIN,
        "user-agent": USER_AGENT,
    }
    return url + sep + urllib.parse.urlencode(params)


def is_mpd(url):
    """True if the URL path ends with .mpd, even if a query/hash is present."""
    try:
        path = urllib.parse.urlparse(url).path
    except Exception:
        path = url
    return path.lower().endswith(".mpd")


def get_clearkey(item):
    """Return (kid, key) using several possible JSON field names, else (None, None)."""
    key_id = (
        item.get("keyId")
        or item.get("key_id")
        or item.get("kid")
        or item.get("clearkey_id")
    )
    key = (
        item.get("key")
        or item.get("clearkey")
        or item.get("ck")
    )

    # Combined "kid:key" string?
    if not key_id or not key:
        combined = item.get("clearkey") or item.get("license_key") or ""
        if isinstance(combined, str) and ":" in combined:
            a, b = combined.split(":", 1)
            key_id = key_id or a.strip()
            key    = key    or b.strip()

    if key_id and key:
        return str(key_id).strip(), str(key).strip()
    return None, None


def generate_m3u(items, cookie, out_file):
    lines = ["#EXTM3U"]
    written = 0

    for item in items:
        url = (item.get("url") or item.get("mpd_url") or "").strip()
        if not url:
            continue

        name     = item.get("name", "Unknown")
        logo     = item.get("logo", "")
        category = item.get("group") or item.get("category") or "Other"

        lines.append(
            f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="{category}", {name}'
        )

        # ---- MPD handling (works with or without query string) ----
        if is_mpd(url):
            key_id, key = get_clearkey(item)

            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            # Headers that Kodi's adaptive addon forwards to manifest + segments
            lines.append(
                "#KODIPROP:inputstream.adaptive.stream_headers="
                f"User-Agent={USER_AGENT}&Referer={REFERER}&Origin={ORIGIN}"
            )
            # Always emit license_key (Kodi errors out if missing on some builds)
            lines.append(
                f"#KODIPROP:inputstream.adaptive.license_key={key_id or ''}:{key or ''}"
            )
            # ClearKey DRM only when we actually have a keypair
            if key_id and key:
                lines.append(
                    "#KODIPROP:inputstream.adaptive.license_type=clearkey"
                )

        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-extra-headers=Origin: {ORIGIN}")
        lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
        lines.append(
            '#EXTHTTP:{"Origin":"%s","Referer":"%s","User-Agent":"%s","Cookie":"%s"}'
            % (ORIGIN, REFERER, USER_AGENT, cookie)
        )

        lines.append(build_url(url, cookie))
        lines.append("")  # blank line between entries
        written += 1

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    return written


def main():
    try:
        print("-> Fetching cookie ...")
        cookie = fetch_cookie(COOKIE_URL)
        print(f"   OK ({len(cookie)} chars)")

        print("-> Fetching JSON ...")
        data = fetch_json(JSON_URL)
        if isinstance(data, dict):
            data = data.get("items") or data.get("channels") or []
        print(f"   OK ({len(data)} entries)")

        print("-> Writing M3U ...")
        total = generate_m3u(data, cookie, OUTPUT)
        print(f"[OK] {OUTPUT} written ({total} channels)")
    except Exception as e:
        print(f"[FAIL] {e}")


if __name__ == "__main__":
    main()
