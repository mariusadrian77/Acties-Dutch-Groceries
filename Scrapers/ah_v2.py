import json
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
        """Process products into a standardized dictionary format"""
        processed_products = []

        for product in products:
            try:
                # Extract basic product info
                product_id = product.get('webshopId', '')
                title = product.get('title', 'Unknown product')

                # Debug the product structure for the first few products
                if len(processed_products) < 2:
                    logger.info(f"Product structure: {json.dumps(product, default=str)[:500]}...")

                # Default values for prices
                current_price = 0
                original_price = 0

                # Get prices - handle all possible formats
                try:
                    # Current price
                    if 'price' in product:
                        price_obj = product['price']

                        # Handle different price structures
                        if isinstance(price_obj, dict):
                            if 'now' in price_obj:
                                current_price = float(price_obj['now'])
                            elif 'amount' in price_obj:
                                amount = price_obj['amount']
                                if isinstance(amount, dict) and 'amount' in amount:
                                    current_price = float(amount['amount'])
                                elif isinstance(amount, (int, float, str)):
                                    current_price = float(amount)
                            else:
                                # Try to find any numeric value
                                for key, value in price_obj.items():
                                    if isinstance(value, (int, float)) and value > 0:
                                        current_price = float(value)
                                        break
                        elif isinstance(price_obj, (int, float, str)):
                            current_price = float(price_obj)

                    # Original price / price before bonus
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

                    # If no original price found, use current price
                    if original_price == 0:
                        original_price = current_price

                    # Also check "promotionPrice" if available
                    if current_price == 0 and 'promotionPrice' in product:
                        promo_price = product['promotionPrice']
                        if isinstance(promo_price, (int, float, str)):
                            current_price = float(promo_price)
                        elif isinstance(promo_price, dict) and 'amount' in promo_price:
                            current_price = float(promo_price['amount'])

                except Exception as price_error:
                    logger.error(f"Error processing price data: {price_error}")
                    # Use default values

                # Format prices as strings
                current_price_str = f"€{current_price:.2f}".replace('.', ',')
                original_price_str = f"€{original_price:.2f}".replace('.', ',')

                # Get promotion info
                discount_text = ""
                try:
                    if 'discountLabels' in product and product['discountLabels']:
                        if isinstance(product['discountLabels'], list) and len(product['discountLabels']) > 0:
                            discount_info = product['discountLabels'][0]
                            if isinstance(discount_info, dict):
                                discount_text = discount_info.get('text', '')
                    elif 'discount' in product and product['discount']:
                        discount_info = product['discount']
                        if isinstance(discount_info, dict):
                            discount_text = discount_info.get('label', '') or discount_info.get('text', '')
                except Exception as discount_error:
                    logger.error(f"Error processing discount data: {discount_error}")

                # Get image
                image_url = ""
                try:
                    if 'images' in product:
                        images = product['images']
                        if isinstance(images, list) and images:
                            image_url = images[0].get('url', '')
                        elif isinstance(images, dict):
                            image_url = images.get('url', '')
                except Exception as image_error:
                    logger.error(f"Error processing image data: {image_error}")

                # Get unit size
                unit_size = ""
                try:
                    unit_size = product.get('packageSizeText', '') or product.get('unitSize', '')
                except Exception as size_error:
                    logger.error(f"Error processing unit size data: {size_error}")

                # Extract category info
                category_name = ''
                try:
                    if 'taxonomy' in product:
                        taxonomy = product.get('taxonomy', {})
                        if isinstance(taxonomy, dict) and 'category' in taxonomy:
                            category = taxonomy['category']
                            if isinstance(category, dict) and 'nodes' in category:
                                nodes = category['nodes']
                                if isinstance(nodes, list) and nodes:
                                    category_name = nodes[0].get('name', '')
                    elif 'categoryName' in product:
                        category_name = product.get('categoryName', '')
                except Exception as category_error:
                    logger.error(f"Error processing category data: {category_error}")

                product_data = {
                    'id': product_id,
                    'title': title,
                    'current_price': current_price_str,
                    'original_price': original_price_str,
                    'discount_text': discount_text,
                    'image_url': image_url,
                    'unit_size': unit_size,
                    'category': category_name,
                    'url': f"https://www.ah.nl/producten/product/{product_id}" if product_id else ""
                }

                processed_products.append(product_data)

            except Exception as e:
                logger.error(f"Error processing product data: {str(e)}")
                # Add debugging info
                logger.error(f"Problem with product: {json.dumps(product, default=str)[:300]}...")

        return processed_products

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


# Example usage: Scrape products from vegetables & potatoes category (ID 6401)
if __name__ == "__main__":
    try:
        # Initialize the API connector
        api = AlbertHeijnAPIConnector()

        # Get products from vegetables & potatoes category
        category_id = "6401"  # vegetables & potatoes
        logger.info(f"Scraping products from category {category_id} (groente-aardappelen)")

        # Option 1: Get all products in the category
        products = api.search_all_products(taxonomy_id=category_id)
        processed_products = api.process_products_to_dict(products)

        # Option 2: Get only bonus products in the category
        # products = api.get_category_bonus_products(category_id)
        # processed_products = api.process_products_to_dict(products)

        if processed_products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            api.save_to_csv(processed_products, f"ah_groente_aardappelen_{timestamp}.csv")
            logger.info(f"Completed scraping with {len(processed_products)} products saved")
        else:
            logger.error("No products were retrieved. Check the logs for errors.")

    except Exception as e:
        logger.error(f"Script failed: {e}")
