import os
import json
import gspread
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone
import unicodedata
import re

WEBFLOW_API_SITE_TOKEN = os.environ["WEBFLOW_API_SITE_TOKEN"]  # Set this secret in GitHub
ANIMES_COLLECTION_ID = "67fffeccd6749ed6ce46961b"
ANIME_VIDEOS_COLLECTION_ID = "67ffcb961b77a49b301d4a26"
ANIMES_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIMES_COLLECTION_ID}/items"
ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"

# Create Webflow collection item
WEBFLOW_API_HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_SITE_TOKEN}",
    "Content-Type": "application/json"
}

# Authenticate Google Sheets
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

def process():
    for idx, row in enumerate(TO_ADD, start=2):  # start=2 because row 1 is header
        title = row['anime_title']
        playlist_id = row['youtube_playlist_id']
        thumb_url = row['thumbnail_image_url']
        date_added = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        if playlist_id in added_playlist_ids:
            issues.append([title, playlist_id, thumb_url, "Duplicate youtube_playlist_id in \"added\" sheet"])
            rows_to_clear.append(idx)  # Mark rows that have been moved to another sheet for clearing.
        elif playlist_id in to_add_playlist_ids:
            issues.append([title, playlist_id, thumb_url, "Duplicate youtube_playlist_id in \"to add\" sheet"])
            rows_to_clear.append(idx)  # Mark rows that have been moved to another sheet for clearing.
        else:
            to_add_playlist_ids.add(playlist_id)
            
            playlist_items, new_animes_collection_id = create_animes_collection_items(title, playlist_id, thumb_url, idx)
            create_anime_videos_collection_items(new_animes_collection_id, playlist_items, title, playlist_id, thumb_url)
            
            added_sheet.append_row([title, playlist_id, thumb_url, date_added])
            rows_to_clear.append(idx)  # Mark rows that have been moved to another sheet for clearing.

    # Remove processed rows from "to add" sheet (clear each row)
    for row_idx in sorted(set(rows_to_clear), reverse=True):
        # Assuming 3 columns: anime_title, youtube_playlist_id, thumbnail_image_url
        to_add_sheet.batch_clear([f"{row_idx}:{row_idx}"])

    # Write issues to "has issues" sheet
    if issues:
        for issue in issues:
            has_issues_sheet.append_row(issue)

def get_all_playlist_items(yt, playlist_id):
    all_items = []
    next_page_token = None
    while True:
        request = yt.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=playlist_id,
            maxResults=50, # 50 is the maximum number of results per page.
            pageToken=next_page_token
        )
        response = request.execute()
        all_items.extend(response.get('items', []))
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return {'items': all_items}

def create_animes_collection_items(title, playlist_id, thumb_url, idx):
    try:
        yt = build('youtube', 'v3', developerKey=os.environ['YOUTUBE_API_KEY'])
        playlist = yt.playlists().list(
            part='contentDetails,id,localizations,snippet,status', 
            id=playlist_id
        ).execute()
        yt_playlist_items = get_all_playlist_items(yt, playlist_id)
        description = playlist['items'][0]['snippet'].get('description', '') if playlist.get('items') else ''

        data = {
            "isArchived": False,
            "isDraft": False,
            "fieldData": {
                "name": title,
                "slug": simple_slug(title),
                "thumbnail": thumb_url,
                "description": description,
                "youtube-playlist-id": playlist_id
            }
        }

        response = requests.post(ANIMES_CREATE_COLLECTION_ITEMS_URL, headers=WEBFLOW_API_HEADERS, json=data)
        new_animes_collection_id = None
        if response.ok:
            resp_json = response.json()
            new_animes_collection_id = resp_json["id"]
        else:
            print("Webflow error:", response.status_code, response.text)
            response.raise_for_status()

        return yt_playlist_items, new_animes_collection_id
        
    except Exception as e:
        issues.append([title, playlist_id, thumb_url, f"Error processing playlist {playlist_id}: {e}"])
        rows_to_clear.append(idx)  # Mark for clearing


def create_anime_videos_collection_items(item_id, items, title, playlist_id, thumb_url):
    # Create collection items for each video in the playlist
    for video in items.get('items', []):
        try:
            snippet = video['snippet']
            content_details = video['contentDetails']
            video_id = content_details['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            episode_position = snippet['position'] + 1
            published_at = snippet['publishedAt']
            # Format published date to "YYYY-MM-DDTHH:mm:ssZ"
            dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
            published_at_utc = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            video_data = {
                "isArchived": False,
                "isDraft": False,
                "fieldData": {
                    "name": snippet['title'],
                    "slug": simple_slug(snippet['title']),
                    "youtube-video-id": video_id,
                    "youtube-video": video_url,
                    "anime-title-3": item_id,
                    "episode-order": episode_position,
                    "youtube-video-publish-date": published_at_utc
                }
            }
            video_response = requests.post(ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL, headers=WEBFLOW_API_HEADERS, json=video_data)
            if not video_response.ok:
                print("Webflow error:", video_response.status_code, video_response.text)
                video_response.raise_for_status()

        except Exception as e:
            issues.append([title, playlist_id, thumb_url, f"Error processing video {video_id}: {e}"])
            continue


def simple_slug(text: str) -> str:
    text = unicodedata.normalize('NFD', text) # Normalize to NFD (decompose accented letters)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn') # Remove diacritics (accents)
    text = text.lower() # Lowercase
    text = re.sub(r'[^a-z0-9\s]', '', text) # Keep only a-z, 0-9, and spaces
    text = text.strip().replace(' ', '_') # Trim and replace spaces with underscores
    return text


def main():
    process()

if __name__ == "__main__":
    main()