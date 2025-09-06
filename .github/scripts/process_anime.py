import os
import json
import gspread
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone


# Authenticate Google Sheets
creds_json = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.environ['GOOGLE_SHEET_ID'])

to_add = sheet.worksheet("to add").get_all_records()
added = sheet.worksheet("added").get_all_records()
has_issues_ws = sheet.worksheet("has issues")
added_ws = sheet.worksheet("added")

added_titles = set(row['anime_title'] for row in added)
to_add_titles = set()
added_playlist_ids = set(row['youtube_playlist_id'] for row in added)
to_add_playlist_ids = set()
issues = []

to_add_ws = sheet.worksheet("to add")
rows_to_clear = []

WEBFLOW_COLLECTION_ID = "67fffeccd6749ed6ce46961b"
WEBFLOW_API_SITE_TOKEN = os.environ["WEBFLOW_API_SITE_TOKEN"]  # Set this secret in GitHub

for idx, row in enumerate(to_add, start=2):  # start=2 because row 1 is header
    title = row['anime_title']
    playlist_id = row['youtube_playlist_id']
    thumb_url = row['thumbnail_image_url']
    date_added = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    note = ""
    if playlist_id in added_playlist_ids or playlist_id in to_add_playlist_ids:
        note = "Duplicate youtube_playlist_id"
        issues.append([title, playlist_id, thumb_url, note])
        rows_to_clear.append(idx)  # Mark for clearing
    else:
        to_add_playlist_ids.add(playlist_id)
        try:
            yt = build('youtube', 'v3', developerKey=os.environ['YOUTUBE_API_KEY'])
            playlist = yt.playlists().list(part='snippet', id=playlist_id).execute()
            items = yt.playlistItems().list(part='snippet', playlistId=playlist_id, maxResults=5).execute()
            description = playlist['items'][0]['snippet'].get('description', '') if playlist.get('items') else ''

            # Create Webflow collection item
            webflow_url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
            headers = {
                "Authorization": f"Bearer {WEBFLOW_API_SITE_TOKEN}",
                "accept-version": "1.0.0",
                "Content-Type": "application/json"
            }
            data = {
                "fields": {
                    "name": title,
                    "thumbnail": thumb_url,
                    "description": description,
                    "youtube-playlist-id": playlist_id
                }
            }
            response = requests.post(webflow_url, headers=headers, json=data)
            response.raise_for_status()

            # Create collection items for each video in the playlist
            VIDEO_COLLECTION_ID = "67ffcb961b77a49b301d4a26"
            video_webflow_url = f"https://api.webflow.com/collections/{VIDEO_COLLECTION_ID}/items"

            for video in items.get('items', []):
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
                    "fields": {
                        "name": snippet['title'],
                        "youtube-video-id": video_id,
                        "youtube-video-url": video_url,
                        "episode-position": episode_position,
                        "youtube-video-publish-date": published_at_utc
                    }
                }
                video_response = requests.post(video_webflow_url, headers=headers, json=video_data)
                video_response.raise_for_status()

            added_ws.append_row([title, playlist_id, thumb_url, date_added])
            rows_to_clear.append(idx)  # Mark for clearing
        except Exception as e:
            note = f"YouTube API error: {e}"
            issues.append([title, playlist_id, thumb_url, note])
            rows_to_clear.append(idx)  # Mark for clearing

# Remove processed rows from "to add" sheet (clear each row)
for row_idx in sorted(set(rows_to_clear), reverse=True):
    # Assuming 3 columns: anime_title, youtube_playlist_id, thumbnail_image_url
    to_add_ws.batch_clear([f"{row_idx}:{row_idx}"])


# Write issues to "has issues" sheet
if issues:
    for issue in issues:
        has_issues_ws.append_row(issue)