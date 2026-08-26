#!/usr/bin/env python3
import re
import requests
import sys

INPUT_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/jtv5.m3u"
OUTPUT_FILE = "star3.m3u"
USER_AGENT = "Virat "
EXTRA_HEADERS = {
    "Origin": "https://www.jiotv.com/",
    "Referer": "https://www.jiotv.com/"
}

# --- Filter function ---
def is_sports_channel(extinf_line):
    """
    Return True if the channel should be kept (sports-related).
    Checks group-title and channel name.
    """
    # Extract group-title and channel name from EXTINF line
    # Example: #EXTINF:-1 tvg-id="156" tvg-name="Star Gold HD" tvg-logo="..." group-title="STAR",Star Gold HD
    group_match = re.search(r'group-title="([^"]+)"', extinf_line)
    if group_match:
        group = group_match.group(1).upper()
        if "SPORTS" in group:
            return True

    # Also check channel name (after the last comma)
    name_match = re.search(r',([^,]+)$', extinf_line)
    if name_match:
        name = name_match.group(1).strip()
        if "STAR SPORTS" in name.upper():
            return True

    return False

# --- Conversion function (same as before) ---
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

    result = [extinf]
    result.extend(new_props)
    result.append(base_url)
    return result

# --- Main processing with filter ---
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

            # Check if this block is a sports channel
            if not is_sports_channel(block[0]):
                continue  # skip this entry

            # Convert and add to output
            converted = convert_block(block)
            for line in converted:
                new_lines.append(line + '\n')
            new_lines.append('\n')  # blank line between entries
        else:
            # Keep header lines (like #EXTM3U)
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
    print("Filtering and converting sports channels...")
    output = process_m3u(content)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Done! Saved as {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
