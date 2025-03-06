# First import necessary libraries if not already imported
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup


# Define the function
def extract_ah_bonus_page(save_raw=True, extract_deals=False):
    """
    Extract HTML from AH Bonus page

    Args:
        save_raw (bool): Whether to save the raw HTML
        extract_deals (bool): Whether to extract just the deals section

    Returns:
        tuple: (raw_html, filename or None, extracted_content or None)
    """
    url = "https://www.ah.nl/bonus"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text

        filename = None
        if save_raw:
            debug_dir = 'debug_html'
            os.makedirs(debug_dir, exist_ok=True)
            filename = os.path.join(debug_dir, f'ah_bonus_page_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"Saved raw HTML to {filename}")

        extracted_content = None
        if extract_deals:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Extract only the deals section
            deals_container = soup.select('div.product-cards-container')  # Example selector
            if deals_container:
                extracted_content = str(deals_container[0])

        return html_content, filename, extracted_content

    except Exception as e:
        print(f"Error fetching page: {e}")
        return None, None, None

# Now actually call the function to make it run
html, saved_file, extracted = extract_ah_bonus_page(save_raw=True)

# Print confirmation
if saved_file:
    print(f"HTML successfully saved to {saved_file}")
