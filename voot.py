import urllib.request
import json
import re

def fetch_cookie(m3u_url):
    req = urllib.request.Request(m3u_url, headers={'User-Agent': 'OTT Navigator'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode('utf-8')
    match = re.search(r'#EXTVLCOPT:http-cookie=([^\s]+)', content)
    if not match:
        raise RuntimeError('Cookie not found')
    return match.group(1)

def fetch_json(json_url):
    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)

def generate_m3u(data, cookie, output_file):
    user_agent = 'Hotstar;in.startv.hotstar/25.02.24.8.11169@virat10'
    lines = ['#EXTM3U']

    for item in data:
        name = item.get('name', 'Unknown')
        logo = item.get('logo', '')
        group = item.get('group', 'Other')
        mpd = item.get('mpd_url', '')
        kid = item.get('keyId', '').strip()
        key = item.get('key', '').strip()

        if len(kid) < 32:
            kid = kid.zfill(32)
        if len(key) < 32:
            key = key.zfill(32)

        # Build the full URL with query parameters
        url_with_params = (
            f"{mpd}?|"
            f"cookie={cookie}&"
            f"referer=https://www.hotstar.com/&"
            f"origin=https://www.hotstar.com&"
            f"user-agent={user_agent}"
        )

        lines.append(f'#EXTINF:-1 tvg-name="{name} by @virat10" tvg-logo="{logo}" group-title="{group}", {name} by @virat10')
        lines.append('#KODIPROP:inputstream=inputstream.adaptive')
        lines.append('#KODIPROP:inputstream.adaptive.manifest_type=mpd')
        lines.append('#KODIPROP:inputstream.adaptive.license_type=clearkey')
        lines.append(f'#KODIPROP:inputstream.adaptive.license_key={kid}:{key}')
        lines.append(f'#EXTVLCOPT:http-user-agent={user_agent}')
        lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
        lines.append('#EXTVLCOPT:http-extra-headers=Origin: https://www.hotstar.com')
        lines.append(f'#EXTVLCOPT:http-cookie={cookie}')
        lines.append(f'#EXTHTTP:{{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","Cookie":"{cookie}"}}')
        lines.append(url_with_params)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def main():
    m3u_url = 'https://premiumplugx.com/htt/hot.php?playlist=1'
    json_url = 'https://sportlink18.pages.dev/jhs.json'
    output = 'hotstar.m3u'

    try:
        cookie = fetch_cookie(m3u_url)
        print(f'Cookie: {cookie}')
        data = fetch_json(json_url)
        generate_m3u(data, cookie, output)
        print(f'Generated {output} with {len(data)} channels')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()
