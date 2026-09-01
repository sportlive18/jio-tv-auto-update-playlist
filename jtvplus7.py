#!/usr/bin/env python3


import re
import requests
import urllib.parse

def parse_m3u(m3u_content):
    """Parse M3U content and extract channels"""
    lines = m3u_content.split('\n')
    channels = []
    current = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Check for EXTINF line
        if line.startswith('#EXTINF:'):
            # Parse EXTINF
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            group_title = re.search(r'group-title="([^"]*)"', line)
            
            name_parts = line.split(',')
            channel_name = name_parts[-1].strip() if len(name_parts) > 1 else "Unknown"
            
            current = {
                'id': tvg_id.group(1) if tvg_id else '',
                'name': tvg_name.group(1) if tvg_name else channel_name,
                'logo': tvg_logo.group(1) if tvg_logo else '',
                'group': group_title.group(1) if group_title else 'Unknown',
                'url': None,
                'license_key': None,
                'user_agent': 'Droovy',
                'cookie': None,
                'headers': {}
            }
            
        # Check for KODIPROP license key
        elif line.startswith('#KODIPROP:inputstream.adaptive.license_key=') and current:
            license_key = line.replace('#KODIPROP:inputstream.adaptive.license_key=', '').strip()
            if ':' in license_key:
                current['license_key'] = license_key
            
        # Check for EXTVLCOPT user-agent
        elif line.startswith('#EXTVLCOPT:http-user-agent=') and current:
            current['user_agent'] = line.replace('#EXTVLCOPT:http-user-agent=', '').strip()
            
        # Check for EXTHTTP headers
        elif line.startswith('#EXTHTTP:') and current:
            try:
                headers_str = line.replace('#EXTHTTP:', '').strip()
                # Remove curly braces and parse
                if headers_str.startswith('{') and headers_str.endswith('}'):
                    headers_str = headers_str[1:-1]
                    # Parse key-value pairs
                    for part in headers_str.split(','):
                        if ':' in part:
                            key, value = part.split(':', 1)
                            key = key.strip().strip('"')
                            value = value.strip().strip('"')
                            current['headers'][key] = value
                            if key.lower() == 'cookie':
                                current['cookie'] = value
            except:
                pass
                
        # Check for stream URL (not starting with #)
        elif not line.startswith('#') and current:
            current['url'] = line
            
            # Extract cookie from URL if present
            if 'Cookie=' in line:
                cookie_match = re.search(r'Cookie=([^&|]+)', line)
                if cookie_match:
                    current['cookie'] = cookie_match.group(1)
            
            # Extract user-agent from URL if present
            if 'User-Agent=' in line:
                ua_match = re.search(r'User-Agent=([^&|]+)', line)
                if ua_match:
                    current['user_agent'] = urllib.parse.unquote(ua_match.group(1))
            
            # Only add if we have a URL
            if current['url']:
                channels.append(current.copy())
            current = {}
        
        i += 1
    
    return channels

def convert_channel(channel):
    """Convert a single channel to desired format"""
    lines = []
    
    # EXTINF line
    lines.append(f'#EXTINF:-1 tvg-id="{channel["id"]}" tvg-name="{channel["name"]}" tvg-logo="{channel["logo"]}" group-title="{channel["group"]}",{channel["name"]}')
    
    # KODIPROP properties
    lines.append('#KODIPROP:inputstream=inputstream.adaptive')
    lines.append('#KODIPROP:inputstream.adaptive.manifest_type=mpd')
    
    # License key
    if channel.get('license_key'):
        lines.append('#KODIPROP:inputstream.adaptive.license_type=clearkey')
        lines.append(f'#KODIPROP:inputstream.adaptive.license_key={channel["license_key"]}')
    
    # User-Agent
    if channel.get('user_agent'):
        lines.append(f'#EXTVLCOPT:http-user-agent={channel["user_agent"]}')
    
    # Headers
    headers = {}
    if channel.get('cookie'):
        headers['cookie'] = channel['cookie']
    
    # Add origin and referer if needed
    if channel.get('headers'):
        if 'Origin' in channel['headers']:
            headers['Origin'] = channel['headers']['Origin']
        if 'Referer' in channel['headers']:
            headers['Referer'] = channel['headers']['Referer']
    
    if headers:
        lines.append(f'#EXTHTTP:{json.dumps(headers)}')
    
    # Clean URL - remove query parameters that are already handled
    url = channel['url']
    # Remove User-Agent and Cookie from URL as they're handled by EXTVLCOPT and EXTHTTP
    if '|' in url:
        url = url.split('|')[0]
    
    # Check if URL has query parameters
    if '?' in url:
        base_url, params = url.split('?', 1)
        # Keep only necessary params
        param_list = []
        for param in params.split('&'):
            if not param.startswith('User-Agent=') and not param.startswith('Cookie='):
                param_list.append(param)
        
        if param_list:
            url = f"{base_url}?{'&'.join(param_list)}"
        else:
            url = base_url
    
    lines.append(url)
    return '\n'.join(lines) + '\n\n'

def generate_converted_m3u():
    # Input M3U URL
    m3u_url = "https://raw.githubusercontent.com/sixpg/zeyo-test/refs/heads/main/jtv.m3u"
    
    print("=" * 60)
    print("M3U to Kodi Format Converter")
    print("=" * 60)
    
    try:
        # Download M3U
        print(f"\n[*] Downloading M3U: {m3u_url}")
        response = requests.get(m3u_url, timeout=30)
        response.raise_for_status()
        m3u_content = response.text
        print(f"[+] Downloaded {len(m3u_content)} bytes")
        
        # Parse M3U
        print("\n[*] Parsing M3U...")
        channels = parse_m3u(m3u_content)
        print(f"[+] Found {len(channels)} channels")
        
        # Show sample
        if channels:
            print("\n[*] Sample channel:")
            sample = channels[0]
            print(f"  ID: {sample['id']}")
            print(f"  Name: {sample['name']}")
            print(f"  License Key: {sample.get('license_key', 'None')}")
            print(f"  User-Agent: {sample.get('user_agent', 'None')}")
            print(f"  Cookie: {sample.get('cookie', 'None')[:50]}...")
        
        
        print("\n[*] Converting channels...")
        output_file = "jtv3.m3u"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            
            converted = 0
            for ch in channels:
                try:
                    block = convert_channel(ch)
                    f.write(block)
                    converted += 1
                except Exception as e:
                    print(f"  [-] Error converting {ch.get('name', 'Unknown')}: {e}")
            
        print(f"\n[+] Successfully converted {converted} channels")
        print(f"[+] Output saved to: {output_file}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import json
    generate_converted_m3u()
