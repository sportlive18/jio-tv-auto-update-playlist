import requests
import json

url = "https://allinonereborn2.online/jstrweb2/cookies.json"

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Save the raw JSON to a file
    with open("cookies_direct.json", "w") as f:
        json.dump(data, f, indent=2)

    print("✅ Direct fetch successful. Saved to cookies_direct.json")
    print(json.dumps(data, indent=2))

except requests.exceptions.RequestException as e:
    print(f"❌ Network error: {e}")
except json.JSONDecodeError as e:
    print(f"❌ Invalid JSON: {e}")
