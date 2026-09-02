import urllib.request
import urllib.error

url = 'https://premiumplugx.com/htt/hot.php?playlist=1'
headers = {'User-Agent': 'OTT Navigator'}

req = urllib.request.Request(url, headers=headers)

try:
    print(f"Fetching playlist from {url}...")
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        
        lines = content.splitlines()
        
        filtered = []
        in_digital_entry = False
        current_entry = []
        
        for line in lines:
            if line.startswith('#EXTINF'):
                if in_digital_entry and current_entry:
                    filtered.extend(current_entry)
                current_entry = [line]
                in_digital_entry = 'Digital' in line
            else:
                if in_digital_entry:
                    current_entry.append(line)
                    if line.startswith('http'):
                        filtered.extend(current_entry)
                        current_entry = []
                        in_digital_entry = False
        
        if in_digital_entry and current_entry:
            filtered.extend(current_entry)
        
        if filtered:
            filtered = ['#EXTM3U'] + filtered
        
        content = '\n'.join(filtered)
        
        with open('digital.m3u', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved {len(filtered)} lines to 'digital.m3u'")

except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
