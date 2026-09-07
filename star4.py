import urllib.request
import json

def fetch_json(json_url):
    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)

def generate_m3u(data, output_file):
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
            f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{category}", {name}'
        )
        lines.append(f'#EXTVLCOPT:http-user-agent={user_agent}')
        lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
        lines.append(f'#EXTHTTP:{{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","User-Agent":"{user_agent}"}}')
        lines.append(url)  # the stream URL

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def main():
    json_url = 'https://sportlink18.pages.dev/voot.json'
    output = 'star3.m3u'

    try:
        data = fetch_json(json_url)
        generate_m3u(data, output)
        print(f'Generated {output} with {len(data)} channels')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()
