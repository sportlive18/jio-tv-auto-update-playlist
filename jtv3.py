#!/usr/bin/env python3

import re
import json
import sys
import requests
from typing import Dict, List
from urllib.parse import unquote

# --- JioTV defaults ---
REFERER = "https://www.jiotv.com/"
ORIGIN = "https://www.jiotv.com/"
FALLBACK_USER_AGENT = "Sayan10"

# Placeholder UAs found in source playlists that should be replaced by FALLBACK_USER_AGENT
PLACEHOLDER_USER_AGENTS = {"droovy"}

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
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = unquote(v.strip())
    return out


def pop_header(headers: Dict[str, str], name: str, default=None):
    """Case-insensitive header pop."""
    name_lower = name.lower()
    for k in list(headers.keys()):
        if k.lower() == name_lower:
            return headers.pop(k)
    return default


def parse_m3u(content: str) -> List[dict]:
    """Parse an M3U where headers may appear on:
       - the stream line as URL|Header=value&Header=value
       - #KODIPROP:inputstream.adaptive.stream_headers=...
       - #EXTHTTP:{...json...}
    """
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

        elif line.startswith("#KODIPROP:inputstream.adaptive.stream_headers="):
            blob = line.split("=", 1)[1].strip()
            for k, v in parse_kv_pairs(blob).items():
                current["headers"].setdefault(k, v)

        elif line.startswith("#EXTHTTP:"):
            try:
                json_str = line.split(":", 1)[1].strip()
                for k, v in json.loads(json_str).items():
                    current["headers"].setdefault(k, v)
            except (ValueError, json.JSONDecodeError):
                pass

        elif not line.startswith("#"):
            url = line
            headers: Dict[str, str] = {}

            if "|" in line:
                url, header_blob = line.split("|", 1)
                headers = parse_kv_pairs(header_blob)

            # Merge: existing (#KODIPROP / #EXTHTTP) first, pipe-suffix overrides
            merged = dict(current.get("headers") or {})
            merged.update(headers)
            current["headers"] = merged
            current["url"] = url.strip()
            channels.append(current.copy())
            current = {}

    return channels


def build_entry(ch: dict) -> str:
    headers = dict(ch.get("headers") or {})

    input_ua = pop_header(headers, "User-Agent")
    if input_ua and input_ua.strip().lower() not in PLACEHOLDER_USER_AGENTS:
        user_agent = input_ua.strip()
    else:
        user_agent = FALLBACK_USER_AGENT

    cookie = pop_header(headers, "Cookie") or ""

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

    # Raw values (no percent-encoding) — matches what Kodi expects
    stream_headers = "&".join(f"{k}={v}" for k, v in full_headers.items())
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
    print("JioTV M3U Converter")
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
