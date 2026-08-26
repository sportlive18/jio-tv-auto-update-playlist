#!/usr/bin/env python3
import re
import requests
import sys

INPUT_URL = "https://t.ayush848694.workers.dev/"
OUTPUT_FILE = "Star2.m3u"
USER_AGENT = "Virat Paglu"
EXTRA_HEADERS = {
    "Origin": "https://www.jiotv.com/",
    "Referer": "https://www.jiotv.com/"
}

# Add any other sport keywords here if needed
SPORT_KEYWORDS = ["STAR SPORTS", "SONY SPORTS", "EUROSPORT", "TEN"]

def is_sports_channel(extinf_line):
    """Return True if the channel is sports-related."""
    # Check group-title
    group_match = re.search(r'group-title="([^"]+)"', extinf_line)
    if group_match and "SPORTS" in group_match.group(1).upper():
        return True

    # Check channel name (after the last comma)
    name_match = re.search(r',([^,]+)$', extinf_line)
    if name_match:
        name = name_match.group(1).strip().upper()
        for kw in SPORT_KEYWORDS:
            if kw in name:
                return True

    return False

def convert_block(lines):
    """Convert a single channel block to the new format."""
    extinf = None
    props = []
    url = None

    for line in lines:
        line = line.rstrip('\n')
        if line.startswith('#EXTINF'):
            extinf = line
        elif line.startswith('#KODIPROP') or line.startswith('#EXTVLCOPT') or line.startswith('#EXTHTTP'):
            props.append(line)
        elif line.strip() and not line.startswith('#'):
            url = line.strip()

    if not extinf or not url:
        return lines

    token_match = re.search(r'__hdnea__=([^&]+)', url)
    if not token_match:
        return lines

    token = token_match.group(1)
    base_url = re.sub(r'\?.*', '', url)

    new_props = []

    if not any('inputstream=inputstream.adaptive' in p for p in props):
        new_props.append('#KODIPROP:inputstream=inputstream.adaptive')

    for p in props:
        if p.startswith('#KODIPROP:inputstream.adaptive.') or p.startswith('#KODIPROP:inputstream.adaptive'):
            if 'inputstream=inputstream.adaptive' not in p:
                new_props.append(p)
        elif p.startswith('#EXTVLCOPT') and 'http-user-agent' in p:
            pass
        elif p.startswith('#EXTHTTP'):
            pass
        else:
            new_props.append(p)

    new_props.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')

    cookie_value = f'__hdnea__={token}'
    extra_str = ', '.join([f'"{k}":"{v}"' for k, v in EXTRA_HEADERS.items()])
    cookie_line = f'#EXTHTTP:{{"cookie":"{cookie_value}", {extra_str}}}' if extra_str else f'#EXTHTTP:{{"cookie":"{cookie_value}"}}'
    new_props.append(cookie_line)

    result = [extinf] + new_props + [base_url]
    return result

def process_m3u(content):
    lines = content.splitlines(keepends=True)
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF'):
            block = []
            block.append(line.rstrip('\n'))
            i += 1
            while i < len(lines) and (lines[i].startswith('#') or lines[i].strip() == ''):
                block.append(lines[i].rstrip('\n'))
                i += 1
            if i < len(lines) and not lines[i].startswith('#'):
                block.append(lines[i].rstrip('\n'))
                i += 1

            if not is_sports_channel(block[0]):
                continue

            converted = convert_block(block)
            for line in converted:
                new_lines.append(line + '\n')
            new_lines.append('\n')
        else:
            new_lines.append(line)
            i += 1

    return ''.join(new_lines)

def main():
    print(f"Downloading from {INPUT_URL} ...")
    try:
        resp = requests.get(INPUT_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Filtering sports channels (Star Sports, Sony Sports, and any group with 'SPORTS')...")
    output = process_m3u(resp.text)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Done! Saved as {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
