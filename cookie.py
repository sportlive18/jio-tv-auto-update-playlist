import requests
import json

# URL 1: For cookie.json
url1 = "https://allinonereborn2.online/jstrweb2/cookies.json"

# URL 2: For sportcookie.json
url2 = "https://allinonereborn2.online/jtv-fetch/jstarcookie/cookie.json"

def fetch_and_save(url, filename):
    """Fetches a URL, saves the JSON response to a file, and prints it."""
    try:
        print(f"\n--- Fetching {url} ---")
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        # Save the raw JSON to a file
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Direct fetch successful. Saved to {filename}")
        print(json.dumps(data, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error for {url}: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON from {url}: {e}")

if __name__ == "__main__":
    # Fetch and save the first URL
    fetch_and_save(url1, "cookie.json")

    # Fetch and save the second URL
    fetch_and_save(url2, "sportcookie.json")
