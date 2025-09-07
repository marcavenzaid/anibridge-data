# AniBridge Data
This repository contains Workflows to automate some processes for AniBridge.

## Workflows
1. Export Webflow CMS to JSON - runs every day at 00:00 UTC
2. Webflow Add Anime - runs every day at 01:00 UTC
3. Webflow Sync Anime Videos - runs every day at 02:00 UTC

### Export Webflow CMS to JSON Workflow
This workflow automatically exports data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBridge website.

This is a solution to the problem I faced when developing AniBridge in Webflow. I needed a way to add a shop search functionality.
Webflow’s built-in search is a site search (shows results of all the text in the website), not for a single CMS collection. I am also already using the built-in search for searching other things in the website. So, it is already configured for that, and can't be configured for the shop search.

This repository solves that problem by exporting the affiliate products CMS data from Webflow into a static JSON file. That JSON can then be fetched directly on the AniBridge site and used for fast client-side search.

#### Live JSON URL
The latest export is always available here: [affiliate_products.json](https://marcavenzaid.github.io/anibridge-data/affiliate_products.json)

#### How It Works
- A **GitHub Actions workflow** runs once every 24 hours, at 00:00 UTC (or manually).
- The workflow:
	1. Fetches CMS items from the AniBridge Webflow CMS via the Webflow API.
	2. Extracts the fields we care about (`name`, `slug`, `price`, etc).
	3. Saves them into `affiliate_products.json`.
	4. Commits the JSON back to this repo.
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

### Webflow Add Anime Workflow
This workflow reads the new anime entries in the anibridge-add-anime-sheet Google Sheet and automatically creates a Animes Collection items and Anime Videos Collection items in Webflow CMS.

This way, only Google sheet input of anime title, youtube playlist id, and thumbnail image url are needed to add new anime to the website.

anibridge-add-anime-sheet: https://docs.google.com/spreadsheets/d/1C5sDE4ntv_-JlCZdby4B5eiMLcZJOhUKHQZjkvMJTyY

#### How It Works
- A **GitHub Actions workflow** runs once every 24 hours, at 01:00 UTC (or manually).
- The workflow:
	1. Fetches the entris in the anibridge-add-anime-sheet.
	2. Check for duplicates and other issues, if there are, then move those entries to the "has issues" sheet.
	3. Fetches the details of the youtube playlist and the details of the videos in that playlist.
	4. Create Animes Collection items and the corresponding Anime Videos Collection items.

### Webflow Sync Anime Videos Workflow
This workflow adds new videos added to the anime playlist that AniBridge already have in its CMS. This is for ongoing anime series so that the new episodes gets added to AniBridge automatically.

#### How It Works
- A **GitHub Actions workflow** runs once every 24 hours, at 02:00 UTC (or manually).
- The workflow:
	1. Fetch the items from Animes Collection.
	2. Check the playlist of each of the items if there is a new video.
	3. If there is a new video, fetch the details of the new video.
	4. Add the new item to the Anime Videos Collection.