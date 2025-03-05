import logging
import random
import re
import time
from datetime import datetime

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

    def get_bonus_products(self, category_url):
        """
        Scrape bonus products from a specific category page with diagnostic info
        """
        logger.info(f"Scraping products from {category_url}")

        try:
            # First, establish a session by visiting the homepage
            logger.info("Establishing session by visiting homepage")
            self.session.get(self.base_url)
            time.sleep(2 + random.random())  # Random delay

            # Now get the target page
            logger.info("Fetching category page")
            response = self.session.get(category_url)
            logger.info(f"Response status code: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Save the HTML to inspect it (diagnostic)
            with open('ah_page.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            logger.info("Saved HTML to ah_page.html for inspection")

            # Try multiple selectors to find product elements
            selectors = [
                'article[data-testhook="product-card"]',
                '.product-card',
                '.product-card-portrait',
                'article.product',
                'div[data-testid="product-card"]',
                '[data-order]',  # Common pattern in product listing
                'div.lane-item',  # Another common pattern
            ]

            product_elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    product_elements = elements
                    break

            if not product_elements:
                logger.warning("No product elements found with any selector. Page structure might be completely different.")
                # Try to find any structural elements and log their count
                for tag in ['article', 'div', 'section', 'li']:
                    count = len(soup.find_all(tag))
                    logger.info(f"Found {count} <{tag}> elements in total")

                # Check if the response is the login page or some other redirect
                if "login" in soup.get_text().lower() or "aanmelden" in soup.get_text().lower():
                    logger.warning("Detected possible login page redirect")

                return []

            # Diagnostic: Print the first product element to inspect its structure
            if product_elements:
                logger.info(f"First product element structure: {product_elements[0]}")

            products = []
            for product_element in product_elements:
                try:
                    # Flexible bonus detection - try multiple potential selectors
                    is_bonus = False
                    bonus_selectors = [
                        '.price-amount--is-bonus',
                        '.discount',
                        '.bonus',
                        '[data-testhook="bonus-label"]',
                        '.product-card__discount',
                        'span:contains("Bonus")',  # For text-based detection
                    ]

                    for selector in bonus_selectors:
                        bonus_element = None
                        try:
                            if ':contains' in selector:
                                # Handle text-based search separately
                                for span in product_element.find_all('span'):
                                    if 'bonus' in span.get_text().lower():
                                        bonus_element = span
                                        break
                            else:
                                bonus_element = product_element.select_one(selector)
                        except:
                            pass  # Some selectors might be invalid

                        if bonus_element:
                            is_bonus = True
                            logger.info(f"Found bonus element using selector: {selector}")
                            break

                    # For diagnostic purposes, assume all products are bonus products for now
                    is_bonus = True

                    # Extract basic product info
                    # Try multiple selectors for each field to increase chance of finding data

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
                    logger.error(f"Error extracting product data: {e}")

            logger.info(f"Found {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

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

    def analyze_page_structure(self, category_url):
        """Analyze page structure to understand what's happening"""
        try:
            response = self.session.get(category_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check if there's a JavaScript app rendering the content
            scripts = soup.find_all('script')
            script_count = len(scripts)
            logger.info(f"Found {script_count} script tags")

            # Look for evidence of JavaScript frameworks
            frameworks = {
                'React': ['reactjs', 'react.js', '__REACT_DEVTOOLS_GLOBAL_HOOK__'],
                'Vue': ['Vue', 'vue.js', 'vuejs'],
                'Angular': ['ng', 'angular', 'ngModel'],
                'Apollo': ['APOLLO_STATE', 'apollo']
            }

            for framework, signatures in frameworks.items():
                for script in scripts:
                    if script.string:
                        for signature in signatures:
                            if signature in script.string:
                                logger.info(f"Found evidence of {framework} framework")

            # Look for API calls
            api_endpoints = []
            for script in scripts:
                if script.string:
                    # Look for API endpoints
                    api_matches = re.findall(r'["\'](/api/[^\'"]+)["\']', script.string)
                    api_endpoints.extend(api_matches)

            if api_endpoints:
                logger.info(f"Found {len(api_endpoints)} potential API endpoints")
                for endpoint in api_endpoints[:5]:  # Show first 5
                    logger.info(f"  - {endpoint}")

            # Count types of elements
            element_counts = {}
            for tag in ['div', 'article', 'section', 'a', 'img', 'button']:
                element_counts[tag] = len(soup.find_all(tag))

            logger.info("Element counts:")
            for tag, count in element_counts.items():
                logger.info(f"  - {tag}: {count}")

        except Exception as e:
            logger.error(f"Error analyzing page structure: {e}")

# Usage example
if __name__ == "__main__":
    try:
        scraper = AlbertHeijnScraper()
        category_url = "https://www.ah.nl/producten/6401/groente-aardappelen?kenmerk=bonus"

        # First analyze the page structure to understand what we're dealing with
        logger.info("Analyzing page structure...")
        scraper.analyze_page_structure(category_url)

        logger.info("Attempting to scrape products...")
        products = scraper.get_bonus_products(category_url)

        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            scraper.save_to_csv(products, f"ah_bonus_products_{timestamp}.csv")
        else:
            logger.error("No products were retrieved. Check the logs for errors.")

    except Exception as e:
        logger.error(f"Script failed: {e}")
