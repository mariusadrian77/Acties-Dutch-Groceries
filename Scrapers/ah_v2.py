import logging
import time
from datetime import datetime

import pandas as pd
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlbertHeijnAPIConnector:
    def __init__(self):
        self.headers = {
            'Host': 'api.ah.nl',
            'x-application': 'AHWEBSHOP',
            'user-agent': 'Appie/8.8.2 Model/phone Android/7.0-API24',
            'content-type': 'application/json; charset=UTF-8',
        }
        self.base_url = "https://api.ah.nl"
        self.token = self._get_anonymous_token()

    def _get_anonymous_token(self):
        """Get anonymous access token for API calls"""
        logger.info("Getting anonymous access token")
        try:
            response = requests.post(
                f"{self.base_url}/mobile-auth/v1/auth/token/anonymous",
                headers=self.headers,
                json={"clientId": "appie"}
            )
            response.raise_for_status()
            token_data = response.json()
            logger.info("Successfully obtained token")
            return token_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get token: {e}")
            raise

    def _get_auth_headers(self):
        """Get headers with authorization token"""
        auth_headers = self.headers.copy()
        auth_headers["Authorization"] = f"Bearer {self.token.get('access_token')}"
        return auth_headers

    def get_categories(self):
        """Get all product categories"""
        logger.info("Fetching product categories")
        try:
            response = requests.get(
                f"{self.base_url}/mobile-services/v1/product-shelves/categories",
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            categories = response.json()
            logger.info(f"Found {len(categories)} categories")
            return categories
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get categories: {e}")
            return []

    def get_sub_categories(self, category_id):
        """Get subcategories for a specific category"""
        logger.info(f"Fetching subcategories for category {category_id}")
        try:
            response = requests.get(
                f"{self.base_url}/mobile-services/v1/product-shelves/categories/{category_id}/sub-categories",
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            subcategories = response.json()
            logger.info(f"Found {len(subcategories)} subcategories")
            return subcategories
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get subcategories: {e}")
            return []

    def search_products(self, query=None, taxonomy_id=None, page=0, size=150, sort='RELEVANCE', bonus_only=False):
        """Search for products with various filters"""
        logger.info(f"Searching products with query={query}, taxonomy_id={taxonomy_id}, page={page}, bonus_only={bonus_only}")
        try:
            params = {
                "sortOn": sort,
                "page": page,
                "size": size,
                "query": query,
                "taxonomyId": taxonomy_id
            }

            # Add bonus filter if requested
            if bonus_only:
                params["bonus"] = "true"

            response = requests.get(
                f"{self.base_url}/mobile-services/product/search/v2",
                params=params,
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Found {len(data.get('products', []))} products on page {page}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search products: {e}")
            return {"products": [], "page": {"totalPages": 0}}

    def search_all_products(self, **kwargs):
        """Search all products across all pages"""
        logger.info(f"Searching all products with parameters: {kwargs}")

        # Get first page
        response = self.search_products(page=0, **kwargs)
        products = response.get('products', [])

        # Get total pages
        total_pages = response.get('page', {}).get('totalPages', 0)
        logger.info(f"Found {total_pages} total pages of products")

        # Get remaining pages
        for page in range(1, total_pages):
            logger.info(f"Fetching page {page+1} of {total_pages}")
            page_response = self.search_products(page=page, **kwargs)
            page_products = page_response.get('products', [])
            products.extend(page_products)

            # Add a small delay to be nice to the server
            time.sleep(0.5)

        logger.info(f"Total products found: {len(products)}")
        return products

    def get_product_details(self, product_id):
        """Get detailed information for a specific product"""
        logger.info(f"Getting details for product {product_id}")
        try:
            response = requests.get(
                f"{self.base_url}/mobile-services/product/detail/v4/fir/{product_id}",
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get product details: {e}")
            return {}

    def get_all_bonus_products(self):
        """Get all bonus products using bonus filter"""
        logger.info("Getting all bonus products")
        return self.search_all_products(bonus_only=True, sort="PRICE_DESC")

    def get_category_bonus_products(self, taxonomy_id):
        """Get bonus products for a specific category"""
        logger.info(f"Getting bonus products for category {taxonomy_id}")
        return self.search_all_products(taxonomy_id=taxonomy_id, bonus_only=True, sort="PRICE_DESC")

    def get_bonus_periods(self):
        """Get information about current bonus periods"""
        logger.info("Getting bonus periods")
        try:
            response = requests.get(
                f"{self.base_url}/mobile-services/bonuspage/v1/metadata",
                headers=self._get_auth_headers()
            )
            response.raise_for_status()
            periods = response.json().get('periods', [])
            logger.info(f"Found {len(periods)} bonus periods")
            return periods
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get bonus periods: {e}")
            return []

    def process_products_to_dict(self, products):
        """Process products into a standardized dictionary format with limited fields"""
        processed_products = []

        for product in products:
            try:
                # Extract only the required info
                product_id = product.get('webshopId', '')
                title = product.get('title', 'Unknown product')

                # Default price value
                original_price = 0

                # Get original price - handle all possible formats
                try:
                    # First try priceBeforeBonus
                    if 'priceBeforeBonus' in product and product['priceBeforeBonus']:
                        price_obj = product['priceBeforeBonus']

                        if isinstance(price_obj, dict):
                            if 'was' in price_obj:
                                original_price = float(price_obj['was'])
                            elif 'amount' in price_obj:
                                amount = price_obj['amount']
                                if isinstance(amount, dict) and 'amount' in amount:
                                    original_price = float(amount['amount'])
                                elif isinstance(amount, (int, float, str)):
                                    original_price = float(amount)
                            else:
                                # Try to find any numeric value
                                for key, value in price_obj.items():
                                    if isinstance(value, (int, float)) and value > 0:
                                        original_price = float(value)
                                        break
                        elif isinstance(price_obj, (int, float, str)):
                            original_price = float(price_obj)

                    # If no original price found, try regular price
                    if original_price == 0 and 'price' in product:
                        price_obj = product['price']

                        if isinstance(price_obj, dict):
                            if 'amount' in price_obj:
                                amount = price_obj['amount']
                                if isinstance(amount, dict) and 'amount' in amount:
                                    original_price = float(amount['amount'])
                                elif isinstance(amount, (int, float, str)):
                                    original_price = float(amount)
                            elif 'now' in price_obj:
                                original_price = float(price_obj['now'])
                        elif isinstance(price_obj, (int, float, str)):
                            original_price = float(price_obj)

                except Exception as price_error:
                    logger.error(f"Error processing price data: {price_error}")
                    # Use default value

                # Format price as string
                original_price_str = f"€{original_price:.2f}".replace('.', ',')

                product_data = {
                    'id': product_id,
                    'title': title,
                    'original_price': original_price_str
                }

                processed_products.append(product_data)

            except Exception as e:
                logger.error(f"Error processing product data: {str(e)}")

        return processed_products

    def save_to_csv(self, products, filename):
        """Save products to CSV file in products folder"""
        if not products:
            logger.warning("No products to save")
            return

        import os

        # Create products directory if it doesn't exist
        os.makedirs("products", exist_ok=True)

        # Add directory to filename
        filepath = os.path.join("products", filename)

        # Convert to DataFrame and add date and store
        df = pd.DataFrame(products)
        df['scrape_date'] = datetime.now().strftime('%Y-%m-%d')
        df['store'] = 'Albert Heijn'

        df.to_csv(filepath, index=False)
        logger.info(f"Saved {len(products)} products to {filepath}")

    def scrape_all_categories(self):
        """Scrape products from all categories"""
        logger.info("Starting to scrape all categories")

        # Get all categories
        categories = self.get_categories()
        if not categories:
            logger.error("Failed to retrieve categories")
            return

        logger.info(f"Found {len(categories)} categories")

        all_products = []

        # Process each category
        for category in categories:
            try:
                category_id = category.get('id')
                category_name = category.get('name', '').replace('/', '-')

                if not category_id:
                    continue

                logger.info(f"Processing category: {category_name} (ID: {category_id})")

                # Get products for this category
                products = self.search_all_products(taxonomy_id=category_id)
                processed_products = self.process_products_to_dict(products)

                logger.info(f"Found {len(processed_products)} products in category {category_name}")

                # Save products for this category
                if processed_products:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    category_filename = f"ah_{category_name.lower()}_{timestamp}.csv"
                    self.save_to_csv(processed_products, category_filename)

                # Add to overall collection
                all_products.extend(processed_products)

                # Add a delay between categories to be nice to the server
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error processing category: {e}")

        # Save all products combined
        if all_products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.save_to_csv(all_products, f"ah_all_categories_{timestamp}.csv")

        logger.info(f"Completed scraping all categories. Total products found: {len(all_products)}")
        return all_products


# Example usage: Scrape products from all categories
if __name__ == "__main__":
    try:
        # Initialize the API connector
        api = AlbertHeijnAPIConnector()

        # Scrape all categories
        api.scrape_all_categories()

    except Exception as e:
        logger.error(f"Script failed: {e}")
