#!/usr/bin/env python3
"""
Merge JioTV __hdnea__ cookies from M3U playlist into the JSON channel list.
Keeps only Star Sports and Sony Sports channels.
"""

import json
import re
import requests

M3U_URL  = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/jtvplus6.m3u"
JSON_URL = "https://sportlink18.pages.dev/jtvplus.json"
OUT_FILE = "star2.json"

# Keywords to keep (case‑insensitive substring match on channel name)
KEEP_KEYWORDS = ["Star Sports", "Sony Sports"]


def fetch(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def parse_m3u_cookies(m3u_text: str) -> dict:
    """Return {tvg_id: cookie_string} from the M3U playlist."""
    cookies = {}
    current_id = None

    for line in m3u_text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            m = re.search(r'tvg-id="([^"]*)"', line)
            current_id = m.group(1) if m else None
        elif line.startswith("#EXTHTTP:") and current_id:
            payload = line[len("#EXTHTTP:"):].strip()
            try:
                data = json.loads(payload)
                cookie = data.get("cookie", "")
                if cookie:
                    cookies[current_id] = cookie
            except json.JSONDecodeError:
                pass
            current_id = None

    return cookies


def merge_and_filter(json_url: str, cookie_map: dict) -> list:
    channels = json.loads(fetch(json_url))
    merged = 0
    kept = []

    for ch in channels:
        cid = str(ch.get("id", ""))
        name = ch.get("name", "")

        # --- filter: only Star Sports / Sony Sports ---
        if not any(kw.lower() in name.lower() for kw in KEEP_KEYWORDS):
            continue

        # --- attach cookie ---
        if cid in cookie_map:
            ch["cookie"] = cookie_map[cid]
            merged += 1
        else:
            ch["cookie"] = ""

        kept.append(ch)

    print(f"[+] Kept {len(kept)} channels (Star Sports / Sony Sports)")
    print(f"[+] Cookies merged for {merged}/{len(kept)} kept channels")
    return kept


if __name__ == "__main__":
    print("[*] Fetching M3U...")
    m3u = fetch(M3U_URL)
    print(f"[+] {len(m3u):,} bytes")

    print("[*] Parsing cookies...")
    cookie_map = parse_m3u_cookies(m3u)
    print(f"[+] Found {len(cookie_map)} cookie entries")

    print("[*] Fetching JSON, filtering, and merging...")
    result = merge_and_filter(JSON_URL, cookie_map)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[+] Written -> {OUT_FILE}")
