import requests
import json

JSON_URL = "https://undefeatable.streamxlive.workers.dev/"
USER_AGENT = "Sayan10"
OUTPUT_FILE = "jtvplus2.m3u"

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
            print("Error: JSON is not a list nor an object with 'channels' key.")
            print("First 200 chars of response:", resp.text[:200])
            return

        print(f"Found {len(channels)} channels. Building M3U...")

        m3u_lines = ["#EXTM3U"]

        for ch in channels:
            ch_id = ch.get("id", "")
            name = ch.get("name", "Unknown")
            stream_url = ch.get("url", "")
            cookie = ch.get("cookie", "")
            key_id = ch.get("keyId", "")
            key = ch.get("key", "")
            logo = ch.get("logo", "")          # <-- get logo
            group = ch.get("category", "Sports")

            if not all([stream_url, cookie, key_id, key]):
                print(f"  Skipping '{name}' – missing required data.")
                continue

            license_key = f"{key_id}:{key}"

            # EXTINF line with logo
            m3u_lines.append(
                f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
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

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))

        print(f"\n✅ Playlist saved as: {OUTPUT_FILE}")
        print(f"   Total channels processed: {len(channels)}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    generate_m3u()
