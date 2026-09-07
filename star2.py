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
    filtered_lines = []
    
    # Keep the M3U header
    if lines and lines[0].startswith('#EXTM3U'):
        filtered_lines.append(lines[0])
        i = 1
    else:
        i = 0
    
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF'):
            # Case‑insensitive check for "Star Sports"
            if 'Star Sports' in line or 'star sports' in line.lower():
                filtered_lines.append(line)
                i += 1
                while i < len(lines) and lines[i].strip() == '':
                    i += 1
                if i < len(lines):
                    filtered_lines.append(lines[i])
                else:
                    break
            else:
                # Skip this entire entry
                i += 1
                while i < len(lines) and lines[i].strip() == '':
                    i += 1
                if i < len(lines) and not lines[i].startswith('#EXTINF'):
                    i += 1
                continue
        else:
            # Skip non‑#EXTINF lines (comments, etc.)
            i += 1
            continue
        i += 1
    
    filtered_content = '\n'.join(filtered_lines)
    
    with open('hotstar.m3u', 'w', encoding='utf-8') as f:
        f.write(filtered_content)
    
    print("Successfully filtered and saved 'hotstar.m3u' (Star Sports only, no replacement).")

except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
