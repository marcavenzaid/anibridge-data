# AniBridge Data
This repository contains Workflows to automate some processes for AniBridge.

## Workflows
|Workflow name                 | Schedule                    |
|------------------------------|-----------------------------|
|Export Webflow CMS to JSON    | runs every day at 00:00 UTC |
|Export Webflow Animes to JSON | runs every day at 01:00 UTC |
|Webflow Add Anime             | runs every day at 02:00 UTC |
|Webflow Sync Anime Videos     | runs every day at 03:00 UTC |

### Export Webflow CMS to JSON Workflow
This workflow automatically exports the affiliate products data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBridge website.

This is a solution to the problem I faced when developing AniBridge in Webflow. I needed a way to add a shop search functionality.
Webflow’s built-in search is a site search (shows results of all the text in the website), not for a single CMS collection. I am also already using the built-in search for searching other things in the website. So, it is already configured for that, and can't be configured for the shop search.

This repository solves that problem by exporting the affiliate products CMS data from Webflow into a static JSON file. That JSON can then be fetched directly on the AniBridge site and used for fast client-side search.

#### Live JSON URL
The latest export is always available here: [affiliate_products.json](https://marcavenzaid.github.io/anibridge-data/affiliate_products.json)

#### How It Works
- A **GitHub Actions workflow** runs once every 24 hours, at 00:00 UTC (or manually).
- The workflow:
	1. Fetch CMS items from the AniBridge Webflow CMS via the Webflow API.
	2. Extract the required fields (`name`, `slug`, `price`, etc).
	3. Save the fields into `affiliate_products.json`.
	4. Commit the JSON back to this repo.
- GitHub Pages serves the JSON publicly at the URL above.

#### Usage
On the AniBridge frontend (or anywhere else), you can fetch the JSON like this:
```javascript
async function loadProducts() {
  const res = await fetch("https://marcavenzaid.github.io/anibridge-data/affiliate_products.json");
  const products = await res.json();
  console.log(products);
}
```

### Export Webflow Animes to JSON Workflow
This workflow auto automatically exports the Animes Collection data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBeidge website.

#### Live JSON URL
The latest export is always available here: [animes.json](https://marcavenzaid.github.io/anibridge-data/animes.json)

#### How It Works
- A **GitHub Actions workflow** runs once every 24 hours, at 01:00 UTC (or manually).
- The workflow:
	1. Fetch CMS items from the AniBridge Webflow CMS via the Webflow API.
	2. Extract the required fields (`name`, `slug`, `thumbnail`, etc).
	3. Save the fields into `animes.json`.
	4. Commit the JSON back to this repo.
- GitHub Pages serves the JSON publicly at the URL above.

#### Usage
On the AniBridge frontend (or anywhere else), you can fetch the JSON like this:
```javascript
async function loadProducts() {
  const res = await fetch("https://marcavenzaid.github.io/anibridge-data/animes.json");
  const products = await res.json();
  console.log(products);
}
```

### Webflow Add Anime Workflow
This workflow reads the new anime entries in the anibridge-add-anime-sheet Google Sheet and automatically creates Animes CMS Collection items and Anime Videos Collection items in Webflow CMS.

This way, only the Google sheet input of anime title, YouTube playlist ID, and thumbnail image URL is needed to add new anime to the website.

anibridge-add-anime-sheet: https://docs.google.com/spreadsheets/d/1C5sDE4ntv_-JlCZdby4B5eiMLcZJOhUKHQZjkvMJTyY

#### How It Works
- A **GitHub Actions workflow** runs every day at 02:00 UTC (or manually).
- The workflow:
	1. Fetch the entries in the anibridge-add-anime-sheet.
	2. Check for duplicates in the "to add" and "added" sheets, if there are, then move those entries to the "has issues" sheet.
	3. Fetch the details of the youtube playlist and the details of the videos in that playlist.
	4. Create Animes Collection items and the corresponding Anime Videos Collection items.
	5. If there are issues encountered, then move those entries to the "has issues" sheet.
	6. Publish the new Collection items in Webflow.

### Webflow Sync Anime Videos Workflow
This workflow checks for new videos added to the YouTube playlist of the animes that are in the AniBridge CMS, if there are, then it will create Anime Videos CMS Collection items for those videos. This is for ongoing anime series so that the new episodes gets added to AniBridge automatically.

#### How It Works
- A **GitHub Actions workflow** runs every day at 03:00 UTC (or manually).
- The workflow:
	1. Fetch the items from Animes Collection.
	2. Check the playlist of each of the items if there is a new video.
	3. If there is a new video, fetch the details of the new video.
	4. Create the Anime Videos Collection items.
	5. Publish the new Collection items in Webflow.