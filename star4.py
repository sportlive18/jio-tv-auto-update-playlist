#!/usr/bin/env python3
import re
import requests
import sys

INPUT_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/jtvplus5.m3u"
OUTPUT_FILE = "Star3.m3u"
USER_AGENT = "Virat"
EXTRA_HEADERS = {
    "Origin": "https://www.jiotv.com/",
    "Referer": "https://www.jiotv.com/"
}

# --- Filter function (only Star Sports, no Digital) ---
def is_star_sports_channel(extinf_line):
    """
    Return True if the channel is a Star Sports channel and does NOT contain "Digital".
    """
    # Extract channel name (after the last comma)
    name_match = re.search(r',([^,]+)$', extinf_line)
    if not name_match:
        return False
    name = name_match.group(1).strip().upper()
    # Must contain "STAR SPORTS" and NOT contain "DIGITAL"
    if "STAR SPORTS" in name and "DIGITAL" not in name:
        return True
    return False

# --- Conversion function (unchanged) ---
def convert_block(lines):
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
    if extra_str:
        cookie_line = f'#EXTHTTP:{{"cookie":"{cookie_value}", {extra_str}}}'
    else:
        cookie_line = f'#EXTHTTP:{{"cookie":"{cookie_value}"}}'
    new_props.append(cookie_line)

    result = [extinf] + new_props + [base_url]
    return result

# --- Main processing ---
def process_m3u(content):
    lines = content.splitlines(keepends=True)
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF'):
            # Collect the entire block
            block = []
            block.append(line.rstrip('\n'))
            i += 1
            while i < len(lines) and (lines[i].startswith('#') or lines[i].strip() == ''):
                block.append(lines[i].rstrip('\n'))
                i += 1
            if i < len(lines) and not lines[i].startswith('#'):
                block.append(lines[i].rstrip('\n'))
                i += 1

            # Apply filter: only Star Sports, no Digital
            if not is_star_sports_channel(block[0]):
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
    print(f"Downloading playlist from {INPUT_URL} ...")
    try:
        resp = requests.get(INPUT_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to download: {e}")
        sys.exit(1)

    content = resp.text
    print("Filtering Star Sports channels (excluding Digital)...")
    output = process_m3u(content)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Done! Saved as {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
