# AniBridge Data

This repository automatically exports data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBridge website.

## Live JSON URL
The latest export is always available here:

[affiliate_products.json](https://anibridge-data.vercel.app/affiliate_products.json)

## How It Works
- A **GitHub Actions workflow** runs once every 24 hours (or manually).
- The workflow:
  1. Fetches CMS items from the AniBridge Webflow CMS via the Webflow API.
  2. Extracts the fields we care about (`name`, `slug`, `price`, etc).
  3. Saves them into `affiliate_products.json`.
  4. Commits the JSON back to this repo.
- Each commit automatically triggers a **Vercel deploy**, making the JSON available publicly here: [affiliate_products.json](https://anibridge-data.vercel.app/affiliate_products.json).

## Tech Stack
- Webflow CMS API: Source of the data.
- GitHub Actions: Automates the export and commit process.
- Vercel: Hosts the static JSON file.

## Usage
On the AniBridge frontend (or anywhere else), you can fetch the JSON like this:
```javascript
async function loadProducts() {
  const res = await fetch("https://anibridge-data.vercel.app/affiliate_products.json");
  const products = await res.json();
  console.log(products);
}
```