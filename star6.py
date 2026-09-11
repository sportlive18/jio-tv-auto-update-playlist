def extract_from_block(block):
    """
    Parse a block and return a dict if it's a Star Sports channel from JioTV.
    Returns None if it doesn't match the criteria.
    """
    extinf = None
    tvg_id = None
    tvg_name = None
    tvg_logo = None
    display_name = None
    license_key = None
    stream_url = None
    cookie = None

    for line in block:
        if line.startswith('#EXTINF'):
            extinf = line
            tvg_id = re.search(r'tvg-id="([^"]+)"', line)
            tvg_id = tvg_id.group(1) if tvg_id else None
            tvg_name = re.search(r'tvg-name="([^"]+)"', line)
            tvg_name = tvg_name.group(1) if tvg_name else None
            tvg_logo = re.search(r'tvg-logo="([^"]+)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else None
            name_match = re.search(r',([^,]+)$', line)
            display_name = name_match.group(1).strip() if name_match else None

        elif line.startswith('#KODIPROP:inputstream.adaptive.license_key'):
            val = line.split('=', 1)[1] if '=' in line else ''
            if ':' in val:
                key_id, key = val.split(':', 1)
                license_key = (key_id.strip(), key.strip())

        # --- NEW: extract cookie from #EXTHTTP:{...} ---
        elif line.startswith('#EXTHTTP:'):
            raw = line.split(':', 1)[1].strip() if ':' in line else ''
            try:
                headers = json.loads(raw)
                if isinstance(headers, dict):
                    cookie = headers.get('cookie') or headers.get('Cookie') or cookie
            except (json.JSONDecodeError, ValueError):
                # Fallback: try regex in case JSON is malformed
                m = re.search(r'"cookie"\s*:\s*"([^"]+)"', raw, re.IGNORECASE)
                if m:
                    cookie = m.group(1)

        # Also support KODIPROP stream_headers format (your original)
        elif line.startswith('#KODIPROP:inputstream.adaptive.stream_headers'):
            header_value = line.split('=', 1)[1] if '=' in line else ''
            if header_value.startswith('Cookie='):
                cookie = header_value[len('Cookie='):].strip()

        elif not line.startswith('#'):
            raw_url = line.strip()
            base_url = re.sub(r'\?.*', '', raw_url)
            stream_url = base_url

    # --- Filtering ---
    name_to_check = display_name or tvg_name or ''
    if 'star sports' not in name_to_check.lower():
        return None

    if not any(domain in stream_url for domain in ALLOWED_DOMAINS):
        return None

    if 'digital' in name_to_check.lower():
        return None

    obj = {
        "id": tvg_id,
        "name": display_name or tvg_name,
        "stream_url": stream_url,
        "cookie": cookie,
        "cookie_expires": get_cookie_expiry(cookie) if cookie else "",
        "key_id": license_key[0] if license_key else None,
        "key": license_key[1] if license_key else None,
        "logo": tvg_logo
    }
    return obj
