import requests
import json

def fetch_and_save_cookie(output_file="cookie.json"):
    """
    Fetch the first channel's cookie from the remote JSON and save it as a JSON file.
    """
    url = "https://sonujson-v4.pages.dev/Data/sports.json"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Navigate to the first channel in the "channels" array
        channels = data.get("channels", [])
        if not channels:
            print("❌ No channels found in the response.")
            return False

        first_channel = channels[0]
        cookie = first_channel.get("cookie")

        if not cookie:
            print("❌ The first channel does not have a 'cookie' field.")
            return False

        # Write cookie to a JSON file with a "cookie" key
        with open(output_file, "w") as f:
            json.dump({"cookie": cookie}, f, indent=2)

        print(f"✅ Cookie saved to '{output_file}'")
        print(f"   Cookie: {cookie[:50]}...")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    fetch_and_save_cookie()
