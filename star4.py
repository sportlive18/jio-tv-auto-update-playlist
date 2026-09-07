import urllib.request
import json
import re

def fetch_cookie(m3u_url):
    """Extract the cookie from the given M3U URL."""
    req = urllib.request.Request(m3u_url, headers={'User-Agent': 'OTT Navigator'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode('utf-8')
    match = re.search(r'#EXTVLCOPT:http-cookie=([^\s]+)', content)
    if not match:
        raise RuntimeError('Cookie not found')
    return match.group(1)

def fetch_json(json_url):
    """Fetch and parse JSON data."""
    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)

def generate_m3u(data, cookie, output_file):
    """Create an M3U playlist with cookie and headers for voot.json streams."""
    user_agent = 'Hotstar;in.startv.hotstar/25.02.24.8.11169@virat10'
    lines = ['#EXTM3U']

    for item in data:
        name = item.get('name', 'Unknown')
        logo = item.get('logo', '')
        category = item.get('category', 'Other')
        url = item.get('url', '')

        if not url:
            continue  # skip entries without a URL

        lines.append(
            f'#EXTINF:-1 tvg-name="{name} by @virat10" tvg-logo="{logo}" group-title="{category}", {name} by @virat10'
        )
        lines.append(f'#EXTVLCOPT:http-user-agent={user_agent}')
        lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
        lines.append(f'#EXTVLCOPT:http-cookie={cookie}')
        lines.append(
            f'#EXTHTTP:{{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","User-Agent":"{user_agent}","Cookie":"{cookie}"}}'
        )
        lines.append(url)  # the .m3u8 stream URL

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def main():
    cookie_url = 'https://premiumplugx.com/htt/hot.php?playlist=1'
    json_url = 'https://sportlink18.pages.dev/voot.json'
    output = 'voot.m3u'

    try:
        cookie = fetch_cookie(cookie_url)
        print(f'🍪 Cookie: {cookie}')
        data = fetch_json(json_url)
        generate_m3u(data, cookie, output)
        print(f'✅ Generated {output} with {len(data)} channels')
    except Exception as e:
        print(f'❌ Error: {e}')

if __name__ == '__main__':
    main()
