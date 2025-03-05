import logging
import random
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlbertHeijnScraper:
    def __init__(self):
        # More sophisticated headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9,nl;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.ah.nl/',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cookie': 'optOutCategories=[]'  # Basic cookie to help with acceptance
        }
        self.base_url = "https://www.ah.nl"
        self.session = requests.Session()

        # Apply headers to the session
        self.session.headers.update(self.headers)

    def get_all_bonus_products(self, category_url, max_pages=5):
        """
        Scrape all bonus products across multiple pages
        """
        logger.info(f"Starting multi-page scraping from {category_url}")
        all_products = []
        current_page = 1
        current_url = category_url

        # First, establish a session by visiting the homepage
        logger.info("Establishing session by visiting homepage")
        self.session.get(self.base_url)
        time.sleep(2 + random.random())  # Random delay

        while current_page <= max_pages:
            logger.info(f"Processing page {current_page}: {current_url}")

            # Get the current page
            response = self.session.get(current_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch page {current_page}: {response.status_code}")
                break

            # Parse the page
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract products from the current page
            page_products = self._extract_products_from_page(soup)
            logger.info(f"Found {len(page_products)} products on page {current_page}")
            all_products.extend(page_products)

            # Find the next page URL - try multiple methods
            next_url = None

            # Method 1: Look for "Load More" button with a URL
            load_more_selectors = [
                'button.load-more',
                '[data-testid="load-more-button"]',
                '[aria-label="Load more"]',
                '.pagination .next'
            ]
            for selector in load_more_selectors:
                load_more_btn = soup.select_one(selector)
                if load_more_btn:
                    # Try to find URL in href, data-url, or onclick attribute
                    if load_more_btn.has_attr('href'):
                        next_url = urljoin(self.base_url, load_more_btn['href'])
                    elif load_more_btn.has_attr('data-url'):
                        next_url = urljoin(self.base_url, load_more_btn['data-url'])
                    # Check for onclick handler that might contain URL
                    elif load_more_btn.has_attr('onclick'):
                        url_match = re.search(r"location\.href='([^']+)'", load_more_btn['onclick'])
                        if url_match:
                            next_url = urljoin(self.base_url, url_match.group(1))

                    if next_url:
                        logger.info(f"Found next page URL from load more button: {next_url}")
                        break

            # Method 2: Look for pagination with page numbers
            if not next_url:
                pagination_links = soup.select('.pagination a')
                current_page_links = [link for link in pagination_links if link.get_text().strip() == str(current_page)]
                next_page_links = [link for link in pagination_links if link.get_text().strip() == str(current_page + 1)]

                if next_page_links:
                    next_url = urljoin(self.base_url, next_page_links[0]['href'])
                    logger.info(f"Found next page URL from pagination: {next_url}")

            # Method 3: Modify URL parameter (page, offset, etc.)
            if not next_url:
                # Parse the current URL
                parsed_url = urlparse(current_url)
                query_params = parse_qs(parsed_url.query)

                # Try common pagination parameters
                for param in ['page', 'offset', 'p']:
                    if param in query_params:
                        # Increment the page/offset parameter
                        current_value = int(query_params[param][0])
                        query_params[param] = [str(current_value + 1)]

                        # Reconstruct the URL
                        new_query = urlencode(query_params, doseq=True)
                        parsed_url = parsed_url._replace(query=new_query)
                        next_url = urlunparse(parsed_url)
                        logger.info(f"Created next page URL by incrementing parameter: {next_url}")
                        break

                # If no pagination param found, try adding one
                if not next_url and 'page' not in query_params:
                    query_params['page'] = ['2']  # Start with page 2
                    new_query = urlencode(query_params, doseq=True)
                    parsed_url = parsed_url._replace(query=new_query)
                    next_url = urlunparse(parsed_url)
                    logger.info(f"Created next page URL by adding page parameter: {next_url}")

            # Method 4: Look for next button
            if not next_url:
                next_button_selectors = [
                    'a.next',
                    'a[rel="next"]',
                    '.pagination a[aria-label="Next"]',
                    'a:has(> svg)'  # Next buttons often contain icons
                ]

                for selector in next_button_selectors:
                    try:
                        next_button = soup.select_one(selector)
                        if next_button and next_button.has_attr('href'):
                            next_url = urljoin(self.base_url, next_button['href'])
                            logger.info(f"Found next page URL from next button: {next_url}")
                            break
                    except:
                        # Some selectors might not be valid in BeautifulSoup
                        pass

            # If we couldn't find a next page URL using any method, try to identify AJAX pagination
            if not next_url:
                # Look for JavaScript pagination clues
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # Look for API endpoints related to product listings
                        api_matches = re.findall(r'["\'](/api/products/[^\'"]+)["\']', script.string)
                        if api_matches:
                            logger.info(f"Found potential product API endpoints in script: {api_matches}")
                            # We've identified potential AJAX endpoints, but would need to
                            # reverse-engineer the specific request format

            # If we still haven't found a next page, break the loop
            if not next_url:
                logger.info("No next page URL found. Reached the end of pagination or need to use AJAX.")
                break

            # Update for next iteration
            current_url = next_url
            current_page += 1

            # Add a delay between page requests to avoid being blocked
            delay = 3 + random.random() * 2  # Random delay between 3-5 seconds
            logger.info(f"Waiting {delay:.2f} seconds before next page request...")
            time.sleep(delay)

        logger.info(f"Completed multi-page scraping. Total products found: {len(all_products)}")
        return all_products

    def _extract_products_from_page(self, soup):
        """Extract products from a page"""
        products = []

        # Try multiple selectors to find product elements
        selectors = [
            'article[data-testhook="product-card"]',
            '.product-card',
            '.product-card-portrait',
            'article.product',
            'div[data-testid="product-card"]',
            '[data-order]',
            'div.lane-item',
        ]

        product_elements = []
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                logger.info(f"Found {len(elements)} elements with selector: {selector}")
                product_elements = elements
                break

        if not product_elements:
            logger.warning("No product elements found with any selector.")
            return products

        for product_element in product_elements:
            try:
                # Check if product is on bonus
                is_bonus = False
                bonus_selectors = [
                    '.price-amount--is-bonus',
                    '.discount',
                    '.bonus',
                    '[data-testhook="bonus-label"]',
                    '.product-card__discount',
                ]

                for selector in bonus_selectors:
                    bonus_element = product_element.select_one(selector)
                    if bonus_element:
                        is_bonus = True
                        break

                # For the bonus page, all products should be bonus products
                is_bonus = True

                # Extract basic product info
                # Product ID
                product_id = ""
                for attr in ['id', 'data-id', 'data-product-id']:
                    if product_element.has_attr(attr):
                        product_id = product_element[attr]
                        break

                # Title
                title = "Unknown product"
                title_selectors = [
                    '[data-testhook="product-title"]',
                    '.product-card__title',
                    '.product-title',
                    'h3',
                    'h2',
                    '.name'
                ]
                for selector in title_selectors:
                    title_element = product_element.select_one(selector)
                    if title_element:
                        title = title_element.get_text().strip()
                        break

                # Prices
                current_price = "0.00"
                original_price = "0.00"

                # Try to find price elements with various selectors
                price_selectors = [
                    '.price-amount__amount',
                    '.price-amount',
                    '.price',
                    '[data-testhook="price"]',
                    '.product-card__price'
                ]

                # Look for any price elements
                price_elements = []
                for selector in price_selectors:
                    elements = product_element.select(selector)
                    if elements:
                        price_elements = elements
                        break

                # If we found price elements, try to determine which is current and which is original
                if price_elements:
                    if len(price_elements) >= 2:
                        # Assume first is current, second is original in a bonus scenario
                        current_price = price_elements[0].get_text().strip()
                        original_price = price_elements[1].get_text().strip()
                    elif len(price_elements) == 1:
                        current_price = price_elements[0].get_text().strip()
                        original_price = current_price

                # Discount text
                discount_text = ""
                discount_selectors = [
                    '.product-card__discount',
                    '.discount-block',
                    '.bonus-block',
                    '.promotion'
                ]
                for selector in discount_selectors:
                    discount_element = product_element.select_one(selector)
                    if discount_element:
                        discount_text = discount_element.get_text().strip()
                        break

                # Image URL
                image_url = ""
                img_element = product_element.select_one('img')
                if img_element:
                    for attr in ['src', 'data-src', 'data-lazy-src']:
                        if img_element.has_attr(attr):
                            image_url = img_element[attr]
                            break

                # Unit size
                unit_size = ""
                unit_selectors = [
                    '.product-card__unit-size',
                    '.unit-size',
                    '.product-unit'
                ]
                for selector in unit_selectors:
                    unit_element = product_element.select_one(selector)
                    if unit_element:
                        unit_size = unit_element.get_text().strip()
                        break

                product = {
                    'id': product_id,
                    'title': title,
                    'current_price': current_price,
                    'original_price': original_price,
                    'discount_text': discount_text,
                    'image_url': image_url,
                    'unit_size': unit_size,
                    'url': f"{self.base_url}/producten/product/{product_id}" if product_id else ""
                }

                products.append(product)

            except Exception as e:
                logger.error(f"Error extracting product data: {str(e)}")

        return products

    def check_ajax_loading(self, category_url):
        """Check if the page uses AJAX for loading more products"""
        logger.info(f"Checking if {category_url} uses AJAX loading")
        try:
            response = self.session.get(category_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return False

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for "Load More" buttons without hrefs (indicating AJAX)
            load_more_buttons = soup.select('button.load-more, [data-testid="load-more-button"]')
            for button in load_more_buttons:
                if not button.has_attr('href') and button.has_attr('onclick'):
                    logger.info("Found a load more button with onclick but no href (likely AJAX)")
                    return True

            # Look for API endpoints in scripts
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Check for common AJAX pagination patterns
                    ajax_patterns = [
                        'loadMore',
                        'infiniteScroll',
                        'paginateProducts',
                        'getProducts',
                        'fetchPage'
                    ]

                    for pattern in ajax_patterns:
                        if pattern in script.string:
                            logger.info(f"Found AJAX pattern '{pattern}' in script")
                            return True

            return False

        except Exception as e:
            logger.error(f"Error checking AJAX loading: {e}")
            return False

    def save_to_csv(self, products, filename):
        """Save products to CSV file"""
        if not products:
            logger.warning("No products to save")
            return

        df = pd.DataFrame(products)
        df['scrape_date'] = datetime.now().strftime('%Y-%m-%d')
        df['store'] = 'Albert Heijn'

        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(products)} products to {filename}")

# Usage example
if __name__ == "__main__":
    try:
        scraper = AlbertHeijnScraper()
        category_url = "https://www.ah.nl/producten/6401/groente-aardappelen?kenmerk=bonus"

        # Check if the page uses AJAX loading for pagination
        uses_ajax = scraper.check_ajax_loading(category_url)
        logger.info(f"Does the page use AJAX loading? {uses_ajax}")

        # Get all bonus products across multiple pages
        all_products = scraper.get_all_bonus_products(category_url, max_pages=5)

        if all_products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            scraper.save_to_csv(all_products, f"ah_bonus_products_{timestamp}.csv")
        else:
            logger.error("No products were retrieved. Check the logs for errors.")

    except Exception as e:
        logger.error(f"Script failed: {e}")
