import urllib.request
import urllib.error
url = 'https://allinonereborn2.online/m3u/jtv223.m3u'
# We MUST use a specific User-Agent like OTT Navigator, TiviMate, or okhttp to get the playlist
headers = {
    'User-Agent': 'OTT Navigator'
}
req = urllib.request.Request(url, headers=headers)
try:
    print(f"Fetching playlist from {url}...")
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        
        # Save it to a file
        with open('jtvplus2.m3u', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("Successfully fetched the playlist and saved it to 'jtvplus2.m3u'")
        print(f"First few lines:\n{content[:200]}...")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
