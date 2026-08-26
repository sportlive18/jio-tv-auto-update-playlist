#!/usr/bin/env python3
import re
import requests
import sys

INPUT_URL = "https://raw.githubusercontent.com/sportlive18/jio-tv-auto-update-playlist/refs/heads/main/jtv5.m3u"
OUTPUT_FILE = "jtvplus.m3u"
USER_AGENT = "Virat Paglu"
EXTRA_HEADERS = {
    "Origin": "https://www.jiotv.com/",
    "Referer": "https://www.jiotv.com/"
}

def convert_block(lines):
    """
    Convert a block of lines (from #EXTINF to the URL) to the new format.
    Returns a list of lines with proper newlines.
    """
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
        return lines  # malformed, keep original

    # Extract token from URL query
    token_match = re.search(r'__hdnea__=([^&]+)', url)
    if not token_match:
        # No token, keep as is (maybe already in cookie format)
        return lines

    token = token_match.group(1)
    # Remove query string
    base_url = re.sub(r'\?.*', '', url)

    # Build new property lines
    new_props = []

    # 1. Add inputstream.adaptive (if not present)
    if not any('inputstream=inputstream.adaptive' in p for p in props):
        new_props.append('#KODIPROP:inputstream=inputstream.adaptive')

    # 2. Keep existing adaptive.* properties (manifest_type, license_type, license_key)
    for p in props:
        if p.startswith('#KODIPROP:inputstream.adaptive.') or p.startswith('#KODIPROP:inputstream.adaptive'):
            if 'inputstream=inputstream.adaptive' not in p:
                new_props.append(p)
        elif p.startswith('#EXTVLCOPT') and 'http-user-agent' in p:
            # skip old user-agent, we'll add our own
            pass
        elif p.startswith('#EXTHTTP'):
            # skip old EXTHTTP, we'll add our own
            pass
        else:
            # Keep any other custom lines (if any)
            new_props.append(p)

    # 3. Add user-agent
    new_props.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')

    # 4. Build cookie header with extra headers
    cookie_value = f'__hdnea__={token}'
    extra_str = ', '.join([f'"{k}":"{v}"' for k, v in EXTRA_HEADERS.items()])
    if extra_str:
        cookie_line = f'#EXTHTTP:{{"cookie":"{cookie_value}", {extra_str}}}'
    else:
        cookie_line = f'#EXTHTTP:{{"cookie":"{cookie_value}"}}'
    new_props.append(cookie_line)

    # Combine
    result = [extinf]
    result.extend(new_props)
    result.append(base_url)
    return result

def process_m3u(content):
    lines = content.splitlines(keepends=True)
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF'):
            # Collect block until the URL (a non-# line)
            block = []
            block.append(line.rstrip('\n'))
            i += 1
            while i < len(lines) and (lines[i].startswith('#') or lines[i].strip() == ''):
                block.append(lines[i].rstrip('\n'))
                i += 1
            # Now the URL (if exists)
            if i < len(lines) and not lines[i].startswith('#'):
                block.append(lines[i].rstrip('\n'))
                i += 1
            # Convert block
            converted = convert_block(block)
            # Write each line followed by newline, and add a blank line after each entry
            for line in converted:
                new_lines.append(line + '\n')
            new_lines.append('\n')  # extra blank line between entries
        else:
            # Header or empty line
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
    print("Converting entries...")
    output = process_m3u(content)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Done! Saved as {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
