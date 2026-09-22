#!/usr/bin/env python3

import re
import json
import sys
import requests
from typing import Dict, List
from urllib.parse import unquote, quote

# --- JioTV defaults ---
REFERER = "https://www.jiotv.com/"
ORIGIN = "https://www.jiotv.com/"
FALLBACK_USER_AGENT = "Sayan10"

INPUT_URL = "https://raw.githubusercontent.com/sixpg/zeyo-test/refs/heads/main/jtv.m3u"
OUTPUT_FILE = "jtv3.m3u"


def fetch(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def parse_kv_pairs(s: str) -> Dict[str, str]:
    """Parse 'A=1&B=2&C=3' into {'A': '1', 'B': '2', 'C': '3'} (values are URL-decoded)."""
    out: Dict[str, str] = {}
    for pair in s.split("&"):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = unquote(v.strip())
    return out


def parse_m3u(content: str) -> List[dict]:
    """Parse an M3U where the stream line is: URL|Header=value&Header=value"""
    channels: List[dict] = []
    current: dict = {}

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            group = re.search(r'group-title="([^"]*)"', line)

            name_parts = line.split(",")
            name = name_parts[-1].strip() if len(name_parts) > 1 else "Unknown"

            current = {
                "id": tvg_id.group(1) if tvg_id else "",
                "name": tvg_name.group(1) if tvg_name else name,
                "logo": tvg_logo.group(1) if tvg_logo else "",
                "group": group.group(1) if group else "Other",
                "license_type": None,
                "license_key": None,
                "url": None,
                "headers": {},
            }
            continue

        if not current:
            continue

        if line.startswith("#KODIPROP:inputstream.adaptive.license_type="):
            current["license_type"] = line.split("=", 1)[1].strip()

        elif line.startswith("#KODIPROP:inputstream.adaptive.license_key="):
            current["license_key"] = line.split("=", 1)[1].strip()

        elif not line.startswith("#"):
            url = line
            headers: Dict[str, str] = {}

            if "|" in line:
                url, header_blob = line.split("|", 1)
                headers = parse_kv_pairs(header_blob)

            current["url"] = url.strip()
            current["headers"] = headers
            channels.append(current.copy())
            current = {}

    return channels


def build_entry(ch: dict) -> str:
    headers = dict(ch.get("headers") or {})

    user_agent = (
        headers.pop("User-Agent", None)
        or headers.pop("User-agent", None)
        or FALLBACK_USER_AGENT
    )
    cookie = headers.pop("Cookie", None) or headers.pop("cookie", None) or ""

    lines = []

    lines.append(
        f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{ch["name"]}" '
        f'tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}'
    )

    lines.append("#KODIPROP:inputstream=inputstream.adaptive")
    lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")

    if ch.get("license_key"):
        lines.append(
            f'#KODIPROP:inputstream.adaptive.license_type='
            f'{ch.get("license_type") or "clearkey"}'
        )
        lines.append(
            f'#KODIPROP:inputstream.adaptive.license_key={ch["license_key"]}'
        )

    full_headers = {
        "User-Agent": user_agent,
        "Referer": REFERER,
        "Origin": ORIGIN,
    }
    if cookie:
        full_headers["Cookie"] = cookie

    # URL-encode values so embedded '&', '=', spaces, etc. don't corrupt parsing
    stream_headers = "&".join(
        f"{quote(str(k), safe='')}={quote(str(v), safe='')}"
        for k, v in full_headers.items()
    )
    lines.append(
        f"#KODIPROP:inputstream.adaptive.stream_headers={stream_headers}"
    )

    lines.append(f"#EXTVLCOPT:http-user-agent={user_agent}")
    lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
    if cookie:
        lines.append(f"#EXTVLCOPT:http-cookie={cookie}")

    lines.append(f"#EXTHTTP:{json.dumps(full_headers, ensure_ascii=False)}")

    lines.append(ch["url"])

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("JioTV M3U Converter (pipe-suffix headers → full Kodi format)")
    print("=" * 60)

    try:
        print(f"\n[*] Downloading: {INPUT_URL}")
        content = fetch(INPUT_URL)
        print(f"[+] Downloaded {len(content)} bytes")

        print("\n[*] Parsing M3U...")
        channels = parse_m3u(content)
        print(f"[+] Parsed {len(channels)} channels")

        print("\n[*] Converting...")
        entries = []
        for ch in channels:
            try:
                entries.append(build_entry(ch))
            except Exception as e:
                print(
                    f"  [-] Skipped {ch.get('name', '?')}: {e}",
                    file=sys.stderr,
                )

        out = "#EXTM3U\n\n" + "\n\n".join(entries)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(out)

        print(f"\n[+] Wrote {len(entries)} channels → {OUTPUT_FILE}")
        print("=" * 60)

    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
