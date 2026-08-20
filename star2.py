import requests
import json

JSON_URL = "https://undefeatable.streamxlive.workers.dev/"
USER_AGENT = "Sayan10"          
OUTPUT_FILE = "Star2.m3u"

# Only include channels from this category (set to None to disable filtering)
FILTER_CATEGORY = "Sports"   # change to "Entertainment" or None to include all

def generate_m3u():
    try:
        print(f"Fetching data from {JSON_URL} ...")
        resp = requests.get(JSON_URL)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            channels = data
        elif isinstance(data, dict) and "channels" in data:
            channels = data["channels"]
        else:
            print("Error: JSON format not recognized.")
            print("First 200 chars:", resp.text[:200])
            return

        print(f"Found {len(channels)} channels total.")
        
        # Filter by category
        if FILTER_CATEGORY is not None:
            channels = [ch for ch in channels if ch.get("category") == FILTER_CATEGORY]
            print(f"Filtered to {len(channels)} channels in '{FILTER_CATEGORY}' category.")
        else:
            print("No category filter applied.")

        m3u_lines = ["#EXTM3U"]

        for ch in channels:
            ch_id = ch.get("id", "")
            name = ch.get("name", "Unknown")
            stream_url = ch.get("url", "")
            cookie = ch.get("cookie", "")
            key_id = ch.get("keyId", "")
            key = ch.get("key", "")
            logo = ch.get("logo", "")
            category = ch.get("category", "Sports")  # fallback

            # Skip incomplete entries
            if not all([stream_url, cookie, key_id, key]):
                print(f"  Skipping '{name}' – missing required data.")
                continue

            license_key = f"{key_id}:{key}"

            # Group title: you can use the category or hardcode "Sports"
            group_title = category   # or set to "Sports" always

            m3u_lines.append(
                f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group_title}",{name}'
            )

            m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            m3u_lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            m3u_lines.append(f"#KODIPROP:inputstream.adaptive.license_key={license_key}")
            m3u_lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

            headers = {
                "cookie": cookie,
                "Origin": "https://www.jiotv.com/",
                "Referer": "https://www.jiotv.com/",
            }
            headers_json = json.dumps(headers, separators=(',', ':'))
            m3u_lines.append(f"#EXTHTTP:{headers_json}")
            m3u_lines.append(stream_url)
            m3u_lines.append("")

        # Write file
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))

        print(f"\n✅ Playlist saved as: {OUTPUT_FILE}")
        print(f"   Total channels written: {len(channels)}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_m3u()
