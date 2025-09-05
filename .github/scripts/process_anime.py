import os
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Authenticate Google Sheets
creds_json = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.environ['GOOGLE_SHEET_ID'])

to_add = sheet.worksheet("to add").get_all_records()
added = sheet.worksheet("added").get_all_records()
has_issues_ws = sheet.worksheet("has issues")

added_titles = set(row['anime_title'] for row in added)
to_add_titles = set()
issues = []

for row in to_add:
    title = row['anime_title']
    playlist_id = row['youtube_playlist_id']
    thumb_url = row['thumbnail_image_url']
    note = ""
    # Check for duplicates
    if title in added_titles or title in to_add_titles:
        note = "Duplicate anime_title"
        issues.append([title, playlist_id, thumb_url, note])
    else:
        to_add_titles.add(title)
        # Fetch playlist info from YouTube
        try:
            yt = build('youtube', 'v3', developerKey=os.environ['YOUTUBE_API_KEY'])
            playlist = yt.playlists().list(part='snippet', id=playlist_id).execute()
            items = yt.playlistItems().list(part='snippet', playlistId=playlist_id, maxResults=5).execute()
            # You can process playlist and items here as needed
        except Exception as e:
            note = f"YouTube API error: {e}"
            issues.append([title, playlist_id, thumb_url, note])

# Write issues to "has issues" sheet
if issues:
    has_issues_ws.clear()
    has_issues_ws.append_row(["anime_title", "youtube_playlist_id", "thumbnail_image_url", "note"])
    for issue in issues:
        has_issues_ws.append_row(issue)