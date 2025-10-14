import os
import json
import requests
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone

WEBFLOW_API_SITE_TOKEN = os.environ["WEBFLOW_API_SITE_TOKEN"]
ANIMES_COLLECTION_ID = "67fffeccd6749ed6ce46961b"
ANIME_VIDEOS_COLLECTION_ID = "67ffcb961b77a49b301d4a26"
ANIMES_GET_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIMES_COLLECTION_ID}/items"
ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"
ANIME_VIDEOS_LIST_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"

WEBFLOW_API_HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_SITE_TOKEN}",
    "Content-Type": "application/json"
}

CREDS_JSON = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
CREDS_DICT = json.loads(CREDS_JSON)
CREDS = Credentials.from_service_account_info(CREDS_DICT, scopes=["https://www.googleapis.com/auth/spreadsheets"])
YT_API_KEY = os.environ['YOUTUBE_API_KEY']


def sync_anime_videos():
    # Fetch all existing animes in Webflow.
    all_existing_animes = fetch_all_animes()
    print(f"all_existing_animes: {len(all_existing_animes)} total")

    # Fetch all existing videos in Webflow for this anime.
    all_existing_anime_videos = fetch_all_anime_videos()
    print(f"all_existing_anime_videos: {len(all_existing_anime_videos)} total")

    # Group existing videos by anime.
    videos_by_anime = {}
    for item in all_existing_anime_videos:
        anime_id = item['fieldData'].get('anime-title-3')
        videos_by_anime.setdefault(anime_id, []).append(item)

    anime_videos_to_publish = []  # collect all new items to publish

    for anime in all_existing_animes:
        playlist_id = anime['fieldData'].get('youtube-playlist-id')

        if not playlist_id:
            continue

        # ----------------------------
        # Fetch all YouTube videos.
        # ----------------------------
        yt_videos = fetch_playlist_videos(playlist_id)
        yt_items = yt_videos.get('items')
        if not yt_items:
            continue

        # ----------------------------
        # Sort by publish date ascending, if published date is same, use playlist position
        # ----------------------------
        try:
            yt_items.sort(key=lambda v: (
                datetime.strptime(v['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"), 
                v['playlistPosition'])       
            )
        except Exception as e:
            print(f"Failed to sort videos for playlist {playlist_id}: {e}")
            continue

        # Get existing video IDs for this anime to avoid duplicates
        existing_videos = videos_by_anime.get(anime['id'], [])
        existing_video_ids = {v['fieldData']['youtube-video-id'] for v in existing_videos}

        # Find the current highest episode number (default to 0 if none)
        max_existing_order = 0
        for v in existing_videos:
            try:
                order = int(v['fieldData'].get('episode-order', 0))
                if order > max_existing_order:
                    max_existing_order = order
            except (TypeError, ValueError):
                continue
        next_episode_number = max_existing_order + 1

        # ----------------------------
        # Loop through sorted videos and assign new episode order
        # ----------------------------
        for episode_number, video in enumerate(yt_items, start=next_episode_number):
            video_id = video['id']
            if video_id in existing_video_ids:
                continue  # skip duplicates

            snippet = video['snippet']
            localized_snippet = snippet.get('localized', {})
            
            localized_video_title = localized_snippet.get('title', snippet['title'])

            print(f"{localized_video_title}: Not existing video_id: {video_id}")

            video_data = {
                "isArchived": False,
                "isDraft": False,
                "fieldData": {
                    "name": localized_video_title,
                    "youtube-video-id": video_id,
                    "youtube-video": f"https://www.youtube.com/watch?v={video_id}",
                    "anime-title-3": anime['id'],
                    "episode-order": episode_number,  # ordered by publish date
                    "youtube-video-publish-date": video['snippet']['publishedAt']
                }
            }

            # Add to Webflow
            anime_video_id = add_anime_videos_collection_item(video_data)
            if anime_video_id:
                anime_videos_to_publish.append(anime_video_id)

    # ----------------------------
    # Batch publish all new items
    # ----------------------------
    if anime_videos_to_publish:
        publish_anime_videos(anime_videos_to_publish)


def fetch_playlist_videos(playlist_id):
    yt = build('youtube', 'v3', developerKey=YT_API_KEY)
    all_video_ids = []             # Store all video IDs
    video_positions = {}           # Map videoId -> position
    next_page_token = None

    # ----------------------------
    # Get all video IDs + positions
    # ----------------------------
    while True:
        request = yt.playlistItems().list(
            part='snippet,contentDetails',
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
            snippet = video["snippet"]
            localized_snippet = snippet.get('localized', {})

            # Skip if no snippet or marked as private/deleted
            if not snippet:
                continue

            localized_video_title = localized_snippet.get('title', snippet['title']).lower()

            if localized_video_title in ("private video", "deleted video", ""):
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


def fetch_all_animes():
    return fetch_all_items(ANIMES_GET_COLLECTION_ITEMS_URL, WEBFLOW_API_HEADERS)


def fetch_all_anime_videos():
    return fetch_all_items(ANIME_VIDEOS_LIST_COLLECTION_ITEMS_URL, WEBFLOW_API_HEADERS)


def fetch_all_items(collection_url, headers):
    all_items = []
    offset = 0
    limit = 100  # Webflow API's max limit per request.

    while True:
        response = requests.get(
            f"{collection_url}?offset={offset}&limit={limit}",
            headers=headers
        )

        # Handle rate limit
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"Rate limit hit, retrying after {retry_after}s...")
            time.sleep(retry_after)
            continue  # retry the same request

        if not response.ok:
            print("Error fetching items:", response.status_code, response.text)
            break

        data = response.json()
        items = data.get("items", [])
        if not items:
            break  # no more items

        all_items.extend(items)

        # If returned less than the limit, we've reached the last page
        if len(items) < limit:
            break

        offset += limit
        time.sleep(1)  # stay under 60 req/min

    return all_items


def add_anime_videos_collection_item(video_data):
    response = safe_post(ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL, WEBFLOW_API_HEADERS, video_data)
    if not response.ok:
        print("Error adding video to collection:", response.status_code, response.text)
        return None

    new_item = response.json()
    return new_item.get("id")


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


def publish_anime_videos(item_ids):
    url = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items/publish"
    response = requests.post(
        url,
        headers=WEBFLOW_API_HEADERS,
        json={"itemIds": item_ids}
    )
    if not response.ok:
        print("Error publishing items:", response.status_code, response.text)
    else:
        print(f"Published {len(item_ids)} items.")


def main():
    sync_anime_videos()


if __name__ == "__main__":
    main()
