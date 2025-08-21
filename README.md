# AniBridge Data
This repository automatically exports data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBridge website.

## About This Project
This is a solution to the problem I faced when developing AniBridge in Webflow. I needed a way to add a shop search functionality.
Webflow’s built-in search is a site search (shows results of all the text in the website), not for a single CMS collection. I am also already using the built-in search for searching other things in the website. So, it is already configured for that, and can't be configured for the shop search.

This repository solves that problem by exporting the affiliate products CMS data from Webflow into a static JSON file. That JSON can then be fetched directly on the AniBridge site and used for fast client-side search.

## Live JSON URL
The latest export is always available here: [affiliate_products.json](https://marcavenzaid.github.io/anibridge-data/affiliate_products.json)

## How It Works
- A **GitHub Actions workflow** runs once every 24 hours (or manually).
- The workflow:
	1. Fetches CMS items from the AniBridge Webflow CMS via the Webflow API.
	2. Extracts the fields we care about (`name`, `slug`, `price`, etc).
	3. Saves them into `affiliate_products.json`.
	4. Commits the JSON back to this repo.
- GitHub Pages serves the JSON publicly at the URL above.

## Tech Stack
- Webflow CMS API: Data source.
- GitHub Actions: Automates the export and commit process.
- GitHub Pages: Hosts the static JSON file.

## Usage
On the AniBridge frontend (or anywhere else), you can fetch the JSON like this:
```javascript
async function loadProducts() {
  const res = await fetch("https://marcavenzaid.github.io/anibridge-data/affiliate_products.json");
  const products = await res.json();
  console.log(products);
}
```

