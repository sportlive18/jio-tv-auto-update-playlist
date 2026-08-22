import urllib.request
import urllib.error
import re

url = 'https://jhs-channels.rtxcric.workers.dev/playlist.m3u'
headers = {'User-Agent': 'OTT Navigator'}

req = urllib.request.Request(url, headers=headers)

try:
    print(f"Fetching playlist from {url}...")
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        
        # Replace tag
        content = content.replace('@rtxcric', '@sayan10')
        
        # Optional: Keep only digital channels
        lines = content.splitlines()
        filtered = []
        in_entry = False
        for line in lines:
            if line.startswith('#EXTINF') and 'Digital' in line:
                in_entry = True
            if in_entry:
                filtered.append(line)
            if line.startswith('https://') and in_entry:
                in_entry = False
        
        content = '\n'.join(filtered)
        
        with open('digital.m3u', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved {len(filtered)} lines to 'digital.m3u'")

except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
