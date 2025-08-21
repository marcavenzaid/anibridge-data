# AniBridge Data
This repository automatically exports data from the AniBridge Webflow CMS and makes it available as a JSON file for use in the AniBridge website.

## About This Project
This is a solution to the problem I faced when developing AniBridge in Webflow, where there is no way to create a search functionality for the shop that contains the affiliate products.

Webflow offers a site search function, but it is for the entire website. 

So, I decided to create this solution, which automatically exports the affiliate products data from the AniBridge Webflow CMS and makes it available as a JSON file, which can be fetched and used for searching products in the AniBridge shop.

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

