import os
import json
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

WEBFLOW_API_SITE_TOKEN = os.environ["WEBFLOW_API_SITE_TOKEN"]
ANIMES_COLLECTION_ID = "67fffeccd6749ed6ce46961b"
ANIME_VIDEOS_COLLECTION_ID = "67ffcb961b77a49b301d4a26"
ANIMES_GET_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIMES_COLLECTION_ID}/items"
ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL = f"https://api.webflow.com/v2/collections/{ANIME_VIDEOS_COLLECTION_ID}/items"

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
  animes = fetch_animes()
  # print(f"animes: {animes}")

  # Fetch all existing videos in Webflow for this anime.
  all_existing_anime_videos = fetch_all_anime_videos()

  # Group existing videos by anime.
  videos_by_anime = {}
  for item in all_existing_anime_videos:
      anime_id = item['fieldData'].get('anime-title-3')
      videos_by_anime.setdefault(anime_id, []).append(item)
      print(f"videos_by_anime: {videos_by_anime}")

  for anime in animes[:5]:
    print(f"anime: {anime}")
    playlist_id = anime['fieldData'].get('youtube-playlist-id')

    if playlist_id:
      # Fetch all YouTube videos.
      yt_videos = fetch_youtube_playlist_items(playlist_id)

      # Get existing video IDs for this anime to avoid duplicates.
      existing_video_ids = {v['fieldData']['youtube-video-id'] for v in videos_by_anime.get(anime['id'], [])}
      print(f"{anime}: existing_video_ids: {existing_video_ids}")

      # Loop through YouTube videos and add missing ones.
      for video in yt_videos:
        video_id = video['contentDetails']['videoId']
        if video_id not in existing_video_ids:
          print(f"{video['snippet']['title']}: Not existing video_id: {video_id}")
          # No need to include slug, Webflow will auto-generate it.
          video_data = {
            "isArchived": False,
            "isDraft": False,
            "fieldData": {
              "name": video['snippet']['title'],
              "youtube-video-id": video_id,
              "youtube-video": f"https://www.youtube.com/watch?v={video_id}",
              "anime-title-3": anime['id'],
              "episode-order": video['snippet']['position'] + 1,
              "youtube-video-publish-date": video['snippet']['publishedAt']
            }
          }
          add_anime_videos_collection_item(video_data)


def fetch_animes():
  response = requests.get(ANIMES_GET_COLLECTION_ITEMS_URL, headers=WEBFLOW_API_HEADERS)
  if response.ok:
    return response.json().get('items', [])
  else:
    print("Error fetching animes:", response.status_code, response.text)
    return []


def fetch_youtube_playlist_items(playlist_id):
    yt = build('youtube', 'v3', developerKey=YT_API_KEY)
    all_items = []
    next_page_token = None
    while True:
        yt_playlist_items = yt.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        all_items.extend(yt_playlist_items.get('items', []))
        next_page_token = yt_playlist_items.get('nextPageToken')
        if not next_page_token:
            break
    return all_items


def fetch_all_anime_videos():
  response = requests.get(ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL, headers=WEBFLOW_API_HEADERS)
  if response.ok:
    return response.json().get("items", [])
  else:
    print("Error fetching anime videos:", response.status_code, response.text)
    return []


def add_anime_videos_collection_item(video_data):
  response = requests.post(ANIME_VIDEOS_CREATE_COLLECTION_ITEMS_URL, headers=WEBFLOW_API_HEADERS, json=video_data)
  if not response.ok:
    print("Error adding video to collection:", response.status_code, response.text)


def main():
  sync_anime_videos()

if __name__ == "__main__":
  main()