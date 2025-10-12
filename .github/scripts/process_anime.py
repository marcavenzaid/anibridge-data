import os
import json
import gspread
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone
import unicodedata
import re
import time

# Set this secret in GitHub.
WEBFLOW_API_SITE_TOKEN = os.environ["WEBFLOW_API_SITE_TOKEN"]
ANIMES_COLLECTION_ID = "67fffeccd6749ed6ce46961b"
ANIME_VIDEOS_COLLECTION_ID = "67ffcb961b77a49b301d4a26"
ANIMES_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIMES_COLLECTION_ID}/items"
ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"

# Create Webflow collection item.
WEBFLOW_API_HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_SITE_TOKEN}",
    "Content-Type": "application/json"
}

YT_API_KEY = os.environ['YOUTUBE_API_KEY']

# Authenticate Google Sheets.
CREDS_JSON = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
CREDS_DICT = json.loads(CREDS_JSON)
CREDS = Credentials.from_service_account_info(CREDS_DICT, scopes=["https://www.googleapis.com/auth/spreadsheets"])
GC = gspread.authorize(CREDS)
SHEET = GC.open_by_key(os.environ['GOOGLE_SHEET_ID'])

TO_ADD = SHEET.worksheet("to add").get_all_records()
ADDED = SHEET.worksheet("added").get_all_records()

to_add_sheet = SHEET.worksheet("to add")
added_sheet = SHEET.worksheet("added")
has_issues_sheet = SHEET.worksheet("has issues")

added_titles = set(row['anime_title'] for row in ADDED)
to_add_titles = set()
added_playlist_ids = set(row['youtube_playlist_id'] for row in ADDED)
to_add_playlist_ids = set()

issues = []
rows_to_clear = []

CURRENT_DATETIME = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def process():
    animes_to_publish = []
    anime_videos_to_publish = []

    # start=2 because row 1 is header.
    for idx, row in enumerate(TO_ADD, start=2):
        title = row['anime_title']
        playlist_id = row['youtube_playlist_id']
        thumb_url = row['thumbnail_image_url']

        if playlist_id in added_playlist_ids:
            issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME, "Duplicate youtube_playlist_id in \"added\" sheet"])
            rows_to_clear.append(idx)
            continue

        if playlist_id in to_add_playlist_ids:
            issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME, "Duplicate youtube_playlist_id in \"to add\" sheet"])
            rows_to_clear.append(idx)
            continue

        to_add_playlist_ids.add(playlist_id)

        try:
            # Create new item in the Animes collection.
            playlist_videos, anime_id = create_animes_collection_items(title, playlist_id, thumb_url, idx)

            if not anime_id:
                raise Exception("Anime creation failed (no ID returned)")

            anime_videos_ids = create_anime_videos_collection_items(anime_id, playlist_videos, title, playlist_id, thumb_url)

            if not anime_videos_ids:
                raise Exception("No videos created for this anime")

            animes_to_publish.append(anime_id)
            anime_videos_to_publish.extend(anime_videos_ids)

            # Record the addition in the "added" sheet.
            added_sheet.append_row([title, playlist_id, thumb_url, CURRENT_DATETIME])
            rows_to_clear.append(idx)

        except Exception as e:
            issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME, f"Failed to process anime: {e}"])
            rows_to_clear.append(idx)
            continue  # Skip publishing this anime/videos entirely

    # Clear processed rows from "to add" sheet (clear each row).
    for row_idx in sorted(set(rows_to_clear), reverse=True):
        to_add_sheet.batch_clear([f"{row_idx}:{row_idx}"])

    # Write issues in "has issues" sheet.
    if issues:
        for issue in issues:
            has_issues_sheet.append_row(issue)

    # Publish after everything is created
    publish_items(ANIMES_COLLECTION_ID, animes_to_publish)
    publish_items(ANIME_VIDEOS_COLLECTION_ID, anime_videos_to_publish)


def create_animes_collection_items(title, playlist_id, thumb_url, idx):
    try:
        yt = build('youtube', 'v3', developerKey=YT_API_KEY)
        playlist = yt.playlists().list(
            part='contentDetails,id,localizations,snippet,status',
            id=playlist_id
        ).execute()
        playlist_videos = fetch_playlist_videos(yt, playlist_id)
        description = playlist['items'][0]['snippet'].get('description', '') if playlist.get('items') else ''

        # No need to include slug, Webflow will auto-generate it.
        data = {
            "isArchived": False,
            "isDraft": False,
            "fieldData": {
                "name": title,
                "thumbnail": thumb_url,
                "description": description,
                "youtube-playlist-id": playlist_id
            }
        }

        response = safe_post(ANIMES_CREATE_COLLECTION_ITEMS_URL, WEBFLOW_API_HEADERS, data)
        new_animes_collection_id = None
        if response.ok:
            resp_json = response.json()
            new_animes_collection_id = resp_json["id"]
            print(f"Created {title} (playlist_id: {playlist_id})")
            return playlist_videos, new_animes_collection_id
        else:
            print("Webflow error:", response.status_code, response.text)
            response.raise_for_status()
            return None, None

    except Exception as e:
        issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME, f"Error processing playlist {playlist_id}: {e}"])
        rows_to_clear.append(idx)  # Mark for clearing.
        return None, None


def create_anime_videos_collection_items(item_id, playlist_videos, title, playlist_id, thumb_url):
    video_data_list = []
    parsed_videos = []

    # ----------------------------
    # 1. Gather and parse video info first
    # ----------------------------
    for video in playlist_videos.get('items', []):
        try:
            snippet = video['snippet']
            localized_snippet = snippet.get('localized', {})

            video_id = video['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            video_title = localized_snippet.get('title', snippet['title'])

            playlist_position = video['playlistPosition']

            published_at = snippet['publishedAt']

            # Parse published date
            dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")

            parsed_videos.append({
                "video_id": video_id,
                "video_title": video_title,
                "video_url": video_url,
                "published_at": dt,
                "playlist_position": playlist_position,
            })

        except Exception as e:
            issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME,
                           f"Error preparing video {video.get('id', 'unknown')}: {e}"])
            continue

    # ----------------------------
    # 2. Sort by published date ascending, if published date is same, use playlist position
    # ----------------------------
    parsed_videos.sort(key=lambda x: (x["published_at"], x["playlist_position"]))

    print(parsed_videos)

    if not parsed_videos:
        return []

    # ----------------------------
    # 3. Create Webflow-ready items with new episode order
    # ----------------------------
    for idx, v in enumerate(parsed_videos, start=1):
        published_at_utc = v["published_at"].strftime("%Y-%m-%dT%H:%M:%SZ")

        video_data_list.append({
            "isArchived": False,
            "isDraft": False,
            "fieldData": {
                "name": v["video_title"],
                "youtube-video-id": v["video_id"],
                "youtube-video": v["video_url"],
                "anime-title-3": item_id,
                "episode-order": idx,  # Now based on publish date
                "youtube-video-publish-date": published_at_utc
            }
        })

    # ----------------------------
    # 4. Send them all at once to Webflow
    # ----------------------------
    url = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"
    try:
        response = safe_post(url, WEBFLOW_API_HEADERS, {"items": video_data_list})
        if response.ok:
            resp_json = response.json()
            new_ids = [item["id"] for item in resp_json.get("items", [])]
            print(f"Created {len(new_ids)} videos for anime ({title}, playlist_id: {playlist_id})")
            return new_ids
        else:
            print("Webflow error:", response.status_code, response.text)
            response.raise_for_status()
            return []
    except Exception as e:
        issues.append([title, playlist_id, thumb_url, CURRENT_DATETIME, f"Bulk video creation failed: {e}"])
        return []


def fetch_playlist_videos(yt, playlist_id):
    all_video_ids = []             # Store all video IDs
    video_positions = {}           # Map videoId -> position
    next_page_token = None

    # ----------------------------
    # Get all video IDs + positions
    # ----------------------------
    while True:
        request = yt.playlistItems().list(
            part="contentDetails,snippet",  # snippet is needed for position
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            position = item["snippet"]["position"]
            
            all_video_ids.append(video_id)
            video_positions[video_id] = position  # Save position

        # Pagination handling
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

        # Add delay to avoid possible problems with the API.
        time.sleep(0.5)  

    # ----------------------------
    # Fetch video details in batches of 50
    # ----------------------------
    all_videos = []
    for i in range(0, len(all_video_ids), 50):
        batch_ids = all_video_ids[i:i+50]

        request = yt.videos().list(
            part="snippet,contentDetails",
            id=",".join(batch_ids),
            hl="en"
        )
        response = request.execute()

        for video in response.get("items", []):
            snippet = video.get("snippet")

            # Skip if no snippet or marked as private/deleted
            if not snippet:
                continue

            title = snippet.get("title", "").lower()

            if title in ("private video", "deleted video", ""):
                continue

            vid = video["id"]

            # Merge position into video details
            video["playlistPosition"] = video_positions.get(vid)
            all_videos.append(video)

        # Add delay to avoid possible problems with the API.
        time.sleep(0.5)  

    # Sort results by playlist position to guarantee correct order
    all_videos.sort(key=lambda v: v.get("playlistPosition", float("inf")))

    return {"items": all_videos}


def safe_post(url, headers, json_data, retries=10):
    """
    Send a POST request safely with basic retry logic and rate-limit handling.
    """
    for attempt in range(retries):
        response = requests.post(url, headers=headers, json=json_data)
        if response.status_code == 429:  # rate limited
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"Rate limit hit, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        if response.ok:
            return response
        print(f"Error {response.status_code}: {response.text}")
        time.sleep(1)
    return response  # last response (could be error)


def publish_items(collection_id, item_ids):
    if not item_ids:
        return
    url = f"https://api.webflow.com/v2/collections/{collection_id}/items/publish"
    response = safe_post(url, WEBFLOW_API_HEADERS, {"itemIds": item_ids})
    if response.ok:
        print(f"Published {len(item_ids)} items in collection {collection_id}")
    else:
        print("Webflow publish error:", response.status_code, response.text)
        response.raise_for_status()


def main():
    process()


if __name__ == "__main__":
    main()
