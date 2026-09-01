import urllib.request
import urllib.error

# Your API endpoint
url = 'https://premiumplugx.com/htt/hot.php?playlist=1'

# Headers as before
headers = {'User-Agent': 'OTT Navigator'}

req = urllib.request.Request(url, headers=headers)

try:
    print(f"Fetching playlist from {url}...")
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        
        
        content = content.replace('@Premiumplugx', '@sayan10')
        
        
       
        with open('hotstar.m3u', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Successfully fetched, replaced, and saved to 'hotstar.m3u'")
        print(f"First few lines after replacement:\n{content[:200]}...")

except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
