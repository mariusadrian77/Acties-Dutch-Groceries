import json
import time

import pandas as pd
import requests


def find_api_endpoints():
    """Try to find the API endpoints by inspecting the main page"""
    url = "https://www.ah.nl/bonus"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    page_content = response.text

    # Look for API endpoints in the JavaScript
    print("Searching for API endpoints in the page...")
    if "api/bonus" in page_content:
        print("Found API reference: api/bonus")

    # Save the page for manual inspection if needed
    with open("ah_bonus_page.html", "w", encoding="utf-8") as f:
        f.write(page_content)

    return response.text

def try_api_endpoint():
    """Try to directly access the bonus API if it exists"""
    # Common API patterns based on typical e-commerce sites
    possible_endpoints = [
        "https://www.ah.nl/api/bonus/items",
        "https://www.ah.nl/api/bonus/categories",
        "https://www.ah.nl/api/bonus/promotions",
        "https://www.ah.nl/api/bonus/products"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json"
    }

    for endpoint in possible_endpoints:
        try:
            print(f"Trying endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Success! Found working API endpoint: {endpoint}")
                    print(f"Response preview: {json.dumps(data)[:300]}...")
                    return endpoint, data
                except json.JSONDecodeError:
                    print("Endpoint returned non-JSON response")
            else:
                print(f"Endpoint returned status code: {response.status_code}")
        except Exception as e:
            print(f"Error accessing endpoint: {e}")

    return None, None

def scrape_with_requests():
    """Fallback to basic requests scraping"""
    # First check the main bonus page
    main_url = "https://www.ah.nl/bonus"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Try getting categories from main page
    response = requests.get(main_url, headers=headers)
    all_categories = []

    # Look for category IDs in the page content
    import re
    category_pattern = r'bonus\?id=(\d+)'
    category_ids = set(re.findall(category_pattern, response.text))

    print(f"Found {len(category_ids)} potential category IDs")

    # Now try to fetch each category
    all_products = []
    for category_id in category_ids:
        url = f"https://www.ah.nl/bonus?id={category_id}"
        print(f"Fetching category: {url}")

        category_response = requests.get(url, headers=headers)

        # Look for product information
        # This is a simple extraction, needs refinement based on actual page structure
        product_pattern = r'alt="([^"]+)"[^>]+class="promotion-card-image'
        products = re.findall(product_pattern, category_response.text)

        print(f"Found {len(products)} potential products")

        for product_name in products:
            all_products.append({
                'name': product_name,
                'category_id': category_id,
                'url': url
            })

        time.sleep(1)  # Be nice to the server

    return all_products

def fallback_direct_scraping():
    """Very simple direct scraping as last resort"""
    try:
        # Just get a list of all IDs to check
        test_ids = list(range(690000, 694000))  # Try a range around your example 693061
        found_categories = []

        for test_id in test_ids:
            url = f"https://www.ah.nl/bonus?id={test_id}"
            try:
                response = requests.head(url, allow_redirects=True)
                final_url = response.url

                # If we weren't redirected to the main page, this ID probably exists
                if "bonus?id=" in final_url and str(test_id) in final_url:
                    print(f"Valid category found: ID {test_id}")
                    found_categories.append(test_id)

                    # Fetch the actual page to get products
                    page_response = requests.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    })

                    # Save it for manual inspection
                    with open(f"category_{test_id}.html", "w", encoding="utf-8") as f:
                        f.write(page_response.text)
            except Exception as e:
                print(f"Error checking ID {test_id}: {e}")

            # Only check every 10th ID to be faster
            if test_id % 10 == 0:
                time.sleep(0.1)  # Small delay to be nice

        return found_categories
    except Exception as e:
        print(f"Error in fallback scraping: {e}")
        return []

def main():
    print("Looking for API endpoints...")
    endpoint, data = try_api_endpoint()

    if endpoint and data:
        print("Using API approach...")
        # Process the API data
        # Implementation depends on the API structure
    else:
        print("No API found, trying basic scraping...")
        products = scrape_with_requests()

        if products:
            print(f"Found {len(products)} products via basic scraping")
            df = pd.DataFrame(products)
            df.to_csv("ah_bonus_products_basic.csv", index=False)
        else:
            print("Basic scraping failed, trying fallback method...")
            categories = fallback_direct_scraping()

            if categories:
                print(f"Found {len(categories)} valid category IDs")
                with open("ah_category_ids.txt", "w") as f:
                    for cat_id in categories:
                        f.write(f"{cat_id}\n")
                print("Category IDs saved to ah_category_ids.txt")
            else:
                print("All attempts failed. The site may be using advanced protection.")

if __name__ == "__main__":
    main()
