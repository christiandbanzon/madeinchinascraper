import requests
import time
import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from loguru import logger
from datetime import datetime

from config import HEADERS, SELENIUM_TIMEOUT, SELENIUM_IMPLICIT_WAIT, REQUEST_DELAY, SEARCH_URL
from pdf_extractor import PDFExtractor
from models import ProductListing, Seller, ProductImage, SearchResult

class MadeInChinaScraper:
    """Scraper for Made-in-China.com"""
    
    def __init__(self, use_selenium: bool = False):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.use_selenium = use_selenium
        self.driver = None
        self.pdf_extractor = PDFExtractor(self.session)
        
        if use_selenium:
            self._setup_selenium()
    
    def _setup_selenium(self):
        """Setup Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"--user-agent={UserAgent().random}")
            
            self.driver = webdriver.Chrome(
                options=chrome_options
            )
            self.driver.implicitly_wait(SELENIUM_IMPLICIT_WAIT)
            logger.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Selenium: {e}")
            self.use_selenium = False
    
    def search_products(self, keyword: str, max_pages: int = 5) -> SearchResult:
        """Search for products using keyword"""
        logger.info(f"Searching for keyword: {keyword}")
        
        listings = []
        total_results = 0
        search_url = f"{SEARCH_URL}/{keyword}.html"
        
        try:
            if self.use_selenium:
                listings, total_results = self._search_with_selenium(keyword, max_pages)
            else:
                listings, total_results = self._search_with_requests(keyword, max_pages)
                
        except Exception as e:
            logger.error(f"Error searching for {keyword}: {e}")
            return SearchResult(keyword=keyword, listings=[], total_results=0, search_url=search_url)
        
        return SearchResult(
            keyword=keyword,
            listings=listings,
            total_results=total_results,
            search_url=search_url
        )
    
    def _search_with_requests(self, keyword: str, max_pages: int) -> tuple[List[ProductListing], int]:
        """Search using requests library"""
        listings = []
        total_results = 0
        
        for page in range(1, max_pages + 1):
            try:
                url = f"{SEARCH_URL}/{keyword}.html"
                if page > 1:
                    url = f"{SEARCH_URL}/{keyword}-p{page}.html"
                response = self.session.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract total results count
                if page == 1:
                    total_results = self._extract_total_results(soup)
                
                # Extract product listings
                page_listings = self._extract_listings_from_page(soup)
                listings.extend(page_listings)
                
                logger.info(f"Page {page}: Found {len(page_listings)} listings")
                
                time.sleep(REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"Error on page {page}: {e}")
                break
        
        return listings, total_results
    
    def _search_with_selenium(self, keyword: str, max_pages: int) -> tuple[List[ProductListing], int]:
        """Search using Selenium"""
        listings = []
        total_results = 0
        
        try:
            url = f"{SEARCH_URL}/{keyword}.html"
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-item"))
            )
            
            # Extract total results
            total_results = self._extract_total_results_selenium()
            
            for page in range(1, max_pages + 1):
                if page > 1:
                    # Navigate to next page
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, ".next-page")
                        next_button.click()
                        time.sleep(2)
                    except NoSuchElementException:
                        break
                
                # Extract listings from current page
                page_listings = self._extract_listings_from_page_selenium()
                listings.extend(page_listings)
                
                logger.info(f"Page {page}: Found {len(page_listings)} listings")
                
        except Exception as e:
            logger.error(f"Error in Selenium search: {e}")
        
        return listings, total_results
    
    def _extract_total_results(self, soup: BeautifulSoup) -> int:
        """Extract total number of search results"""
        try:
            # Look for total results count in various possible locations
            result_text = soup.find(text=re.compile(r'(\d+)\s+results?', re.IGNORECASE))
            if result_text:
                match = re.search(r'(\d+)', result_text)
                return int(match.group(1)) if match else 0
            
            # Alternative selectors
            selectors = [
                ".search-result-count",
                ".total-results",
                ".result-count",
                "[class*='count']",
                "[class*='total']"
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text()
                    match = re.search(r'(\d+)', text)
                    if match:
                        return int(match.group(1))
            
            return 0
        except Exception as e:
            logger.error(f"Error extracting total results: {e}")
            return 0
    
    def _extract_total_results_selenium(self) -> int:
        """Extract total results using Selenium"""
        try:
            # Similar logic as above but using Selenium
            selectors = [
                ".search-result-count",
                ".total-results",
                ".result-count",
                "[class*='count']",
                "[class*='total']"
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text
                    match = re.search(r'(\d+)', text)
                    if match:
                        return int(match.group(1))
                except NoSuchElementException:
                    continue
            
            return 0
        except Exception as e:
            logger.error(f"Error extracting total results with Selenium: {e}")
            return 0
    
    def _extract_listings_from_page(self, soup: BeautifulSoup) -> List[ProductListing]:
        """Extract product listings from a page"""
        listings = []
        
        # Common selectors for product items
        product_selectors = [
            ".products-item",
            ".product-item",
            ".item",
            ".product",
            "[class*='product']",
            "[class*='item']"
        ]
        
        for selector in product_selectors:
            products = soup.select(selector)
            if products:
                logger.info(f"Found {len(products)} products with selector: {selector}")
                break
        
        for product in products:
            try:
                listing = self._extract_product_data(product)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.error(f"Error extracting product data: {e}")
                continue
        
        return listings
    
    def _extract_listings_from_page_selenium(self) -> List[ProductListing]:
        """Extract product listings using Selenium"""
        listings = []
        
        try:
            # Find all product elements
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, ".product-item, .item, .product")
            
            for element in product_elements:
                try:
                    listing = self._extract_product_data_selenium(element)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.error(f"Error extracting product data with Selenium: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding product elements: {e}")
        
        return listings
    
    def _extract_product_data(self, product_element) -> Optional[ProductListing]:
        """Extract data from a product element"""
        try:
            # Extract title
            title = self._extract_text(product_element, [
                ".product-name", ".title", ".name", "h2", "h3", "h4", "a"
            ])
            
            if not title:
                return None
            
            # Extract URL
            url = self._extract_url(product_element, ["a"])
            if not url:
                return None
            
            # Extract price
            price = self._extract_price(product_element)
            
            # Extract images
            images = self._extract_images(product_element)
            
            # Extract seller info
            seller = self._extract_seller_info(product_element)
            
            # Extract other details from listing page
            min_order_quantity = self._extract_min_order_quantity(product_element)
            description = self._extract_description(product_element)
            
            # Get detailed product information from individual product page
            item_number, sku = self._get_product_details_from_page(url)
            
            # Get detailed seller information if we have a profile URL
            if seller and seller.profile_url:
                try:
                    detailed_seller = self.get_seller_details(seller.profile_url)
                    if detailed_seller:
                        # Merge the detailed information with basic info
                        seller.rating = detailed_seller.rating
                        seller.total_reviews = detailed_seller.total_reviews
                        seller.email = detailed_seller.email
                        seller.business_name = detailed_seller.business_name
                        seller.country = detailed_seller.country
                        # seller.state_province = detailed_seller.state_province  # Removed state_province field
                        # seller.zip_code = detailed_seller.zip_code  # Removed zip_code field
                        # seller.phone = detailed_seller.phone  # Removed phone field
                        seller.address = detailed_seller.address
                        seller.profile_picture = detailed_seller.profile_picture
                except Exception as e:
                    logger.warning(f"Could not get detailed seller info for {seller.profile_url}: {e}")
            
            return ProductListing(
                title=title,
                listing_url=url,
                item_number=item_number,
                sku=sku,
                price=price,
                images=images,
                seller=seller,
                min_order_quantity=min_order_quantity,
                description=description
            )
            
        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None
    
    def _extract_product_data_selenium(self, element) -> Optional[ProductListing]:
        """Extract product data using Selenium"""
        try:
            # Similar logic as above but using Selenium methods
            title = self._extract_text_selenium(element, [
                ".title", ".name", ".product-name", "h3", "h4", "a"
            ])
            
            if not title:
                return None
            
            url = self._extract_url_selenium(element, ["a"])
            if not url:
                return None
            
            price = self._extract_price_selenium(element)
            images = self._extract_images_selenium(element)
            seller = self._extract_seller_info_selenium(element)
            min_order_quantity = self._extract_min_order_quantity_selenium(element)
            description = self._extract_description_selenium(element)
            
            # Get detailed product information from individual product page
            item_number, sku = self._get_product_details_from_page(url)
            
            # Get detailed seller information if we have a profile URL
            if seller and seller.profile_url:
                try:
                    detailed_seller = self.get_seller_details(seller.profile_url)
                    if detailed_seller:
                        # Merge the detailed information with basic info
                        seller.rating = detailed_seller.rating
                        seller.total_reviews = detailed_seller.total_reviews
                        seller.email = detailed_seller.email
                        seller.business_name = detailed_seller.business_name
                        seller.country = detailed_seller.country
                        # seller.state_province = detailed_seller.state_province  # Removed state_province field
                        # seller.zip_code = detailed_seller.zip_code  # Removed zip_code field
                        # seller.phone = detailed_seller.phone  # Removed phone field
                        seller.address = detailed_seller.address
                        seller.profile_picture = detailed_seller.profile_picture
                except Exception as e:
                    logger.warning(f"Could not get detailed seller info for {seller.profile_url}: {e}")
            
            return ProductListing(
                title=title,
                listing_url=url,
                item_number=item_number,
                sku=sku,
                price=price,
                images=images,
                seller=seller,
                min_order_quantity=min_order_quantity,
                description=description
            )
            
        except Exception as e:
            logger.error(f"Error extracting product data with Selenium: {e}")
            return None
    
    def _extract_text(self, element, selectors: List[str]) -> Optional[str]:
        """Extract text from element using multiple selectors"""
        for selector in selectors:
            try:
                found = element.select_one(selector)
                if found:
                    text = found.get_text(strip=True)
                    if text:
                        return text
            except:
                continue
        return None
    
    def _extract_text_selenium(self, element, selectors: List[str]) -> Optional[str]:
        """Extract text using Selenium"""
        for selector in selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                text = found.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue
        return None
    
    def _extract_url(self, element, selectors: List[str]) -> Optional[str]:
        """Extract URL from element"""
        for selector in selectors:
            try:
                found = element.select_one(selector)
                if found:
                    url = found.get('href')
                    if url:
                        if url.startswith('/'):
                            url = f"https://www.made-in-china.com{url}"
                        return url
            except:
                continue
        return None
    
    def _extract_url_selenium(self, element, selectors: List[str]) -> Optional[str]:
        """Extract URL using Selenium"""
        for selector in selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                url = found.get_attribute('href')
                if url:
                    if url.startswith('/'):
                        url = f"https://www.made-in-china.com{url}"
                    return url
            except NoSuchElementException:
                continue
        return None
    
    def _extract_price(self, element) -> Optional[float]:
        """Extract price from element"""
        price_selectors = [
            ".product-property .price", ".price", ".cost", ".amount", "[class*='price']", "[class*='cost']"
        ]
        
        for selector in price_selectors:
            try:
                found = element.select_one(selector)
                if found:
                    text = found.get_text(strip=True)
                    # Extract numeric value (first number in price range)
                    match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                    if match:
                        return float(match.group().replace(',', ''))
            except:
                continue
        return None
    
    def _extract_price_selenium(self, element) -> Optional[float]:
        """Extract price using Selenium"""
        price_selectors = [
            ".price", ".cost", ".amount", "[class*='price']", "[class*='cost']"
        ]
        
        for selector in price_selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                text = found.text.strip()
                match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                if match:
                    return float(match.group().replace(',', ''))
            except NoSuchElementException:
                continue
        return None
    
    def _extract_images(self, element) -> List[ProductImage]:
        """Extract images from element"""
        images = []
        img_selectors = ["img", ".image", ".photo", "[class*='image']"]
        
        for selector in img_selectors:
            try:
                img_elements = element.select(selector)
                for img in img_elements:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        if src.startswith('/'):
                            src = f"https://www.made-in-china.com{src}"
                        alt = img.get('alt', '')
                        images.append(ProductImage(url=src, alt_text=alt))
            except:
                continue
        
        return images
    
    def _extract_images_selenium(self, element) -> List[ProductImage]:
        """Extract images using Selenium"""
        images = []
        img_selectors = ["img", ".image", ".photo", "[class*='image']"]
        
        for selector in img_selectors:
            try:
                img_elements = element.find_elements(By.CSS_SELECTOR, selector)
                for img in img_elements:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    if src:
                        if src.startswith('/'):
                            src = f"https://www.made-in-china.com{src}"
                        alt = img.get_attribute('alt') or ''
                        images.append(ProductImage(url=src, alt_text=alt))
            except NoSuchElementException:
                continue
        
        return images
    
    def _extract_seller_info(self, element) -> Optional[Seller]:
        """Extract seller information"""
        try:
            # Look for company name link
            company_link = element.select_one(".company-name a")
            if company_link:
                name = company_link.get_text(strip=True)
                profile_url = company_link.get('href')
                
                # Clean up the name (remove extra text)
                if name:
                    # Remove common suffixes
                    name = re.sub(r'\s*(Diamond Member|Audited Supplier|Trading Company|Manufacturer|Factory).*$', '', name, flags=re.IGNORECASE)
                    name = name.strip()
                
                # Ensure profile_url is absolute
                if profile_url and profile_url.startswith('//'):
                    profile_url = 'https:' + profile_url
                elif profile_url and profile_url.startswith('/'):
                    profile_url = 'https://www.made-in-china.com' + profile_url
                
                return Seller(
                    name=name,
                    profile_url=profile_url
                )
            
            # Fallback: look for seller name without link
            seller_selectors = [
                ".company-name", ".seller", ".company", ".supplier", "[class*='seller']", "[class*='company']"
            ]
            
            for selector in seller_selectors:
                try:
                    seller_element = element.select_one(selector)
                    if seller_element:
                        name = seller_element.get_text(strip=True)
                        if name:
                            # Clean up the name
                            name = re.sub(r'\s*(Diamond Member|Audited Supplier|Trading Company|Manufacturer|Factory).*$', '', name, flags=re.IGNORECASE)
                            name = name.strip()
                            return Seller(name=name)
                except:
                    continue
        except Exception as e:
            logger.error(f"Error extracting seller info: {e}")
        
        return None
    
    def _extract_seller_info_selenium(self, element) -> Optional[Seller]:
        """Extract seller information using Selenium"""
        try:
            # Look for company name link
            company_link = element.find_element(By.CSS_SELECTOR, ".company-name a")
            if company_link:
                name = company_link.text.strip()
                profile_url = company_link.get_attribute('href')
                
                # Clean up the name (remove extra text)
                if name:
                    # Remove common suffixes
                    name = re.sub(r'\s*(Diamond Member|Audited Supplier|Trading Company|Manufacturer|Factory).*$', '', name, flags=re.IGNORECASE)
                    name = name.strip()
                
                # Ensure profile_url is absolute
                if profile_url and profile_url.startswith('//'):
                    profile_url = 'https:' + profile_url
                elif profile_url and profile_url.startswith('/'):
                    profile_url = 'https://www.made-in-china.com' + profile_url
                
                return Seller(
                    name=name,
                    profile_url=profile_url
                )
            
            # Fallback: look for seller name without link
            seller_selectors = [
                ".company-name", ".seller", ".company", ".supplier", "[class*='seller']", "[class*='company']"
            ]
            
            for selector in seller_selectors:
                try:
                    seller_element = element.find_element(By.CSS_SELECTOR, selector)
                    name = seller_element.text.strip()
                    if name:
                        # Clean up the name
                        name = re.sub(r'\s*(Diamond Member|Audited Supplier|Trading Company|Manufacturer|Factory).*$', '', name, flags=re.IGNORECASE)
                        name = name.strip()
                        return Seller(name=name)
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.error(f"Error extracting seller info with Selenium: {e}")
        
        return None
    
    def _extract_item_number(self, element) -> Optional[str]:
        """Extract HS Code as item number"""
        try:
            # Look for HS Code in the product details
            hs_code_selectors = [
                ".hs-code", ".hscode", "[class*='hs']", "[class*='code']",
                ".product-detail .code", ".specification .code"
            ]
            
            for selector in hs_code_selectors:
                try:
                    found = element.select_one(selector)
                    if found:
                        text = found.get_text(strip=True)
                        # Look for HS Code pattern (10 digits)
                        hs_match = re.search(r'\b\d{10}\b', text)
                        if hs_match:
                            return hs_match.group(0)
                except:
                    continue
            
            # Fallback: look for any 10-digit code that might be HS Code
            all_text = element.get_text()
            hs_match = re.search(r'\b\d{10}\b', all_text)
            if hs_match:
                return hs_match.group(0)
                
        except Exception as e:
            logger.error(f"Error extracting item number (HS Code): {e}")
        
        return None
    
    def _extract_item_number_selenium(self, element) -> Optional[str]:
        """Extract HS Code as item number using Selenium"""
        try:
            # Look for HS Code in the product details
            hs_code_selectors = [
                ".hs-code", ".hscode", "[class*='hs']", "[class*='code']",
                ".product-detail .code", ".specification .code"
            ]
            
            for selector in hs_code_selectors:
                try:
                    found = element.find_element(By.CSS_SELECTOR, selector)
                    text = found.text.strip()
                    # Look for HS Code pattern (10 digits)
                    hs_match = re.search(r'\b\d{10}\b', text)
                    if hs_match:
                        return hs_match.group(0)
                except NoSuchElementException:
                    continue
            
            # Fallback: look for any 10-digit code that might be HS Code
            all_text = element.text
            hs_match = re.search(r'\b\d{10}\b', all_text)
            if hs_match:
                return hs_match.group(0)
                
        except Exception as e:
            logger.error(f"Error extracting item number (HS Code) with Selenium: {e}")
        
        return None
    
    def _extract_sku(self, element) -> Optional[str]:
        """Extract Model NO. as SKU"""
        try:
            # Look for Model NO. in the product details
            model_selectors = [
                ".model-no", ".model", ".model-number", "[class*='model']",
                ".product-detail .model", ".specification .model"
            ]
            
            for selector in model_selectors:
                try:
                    found = element.select_one(selector)
                    if found:
                        text = found.get_text(strip=True)
                        # Look for model number pattern (alphanumeric)
                        model_match = re.search(r'\b[A-Z0-9\-_]+\b', text)
                        if model_match:
                            return model_match.group(0)
                except:
                    continue
            
            # Fallback: look for any alphanumeric code that might be model number
            all_text = element.get_text()
            model_match = re.search(r'\b[A-Z0-9\-_]+\b', all_text)
            if model_match:
                return model_match.group(0)
                
        except Exception as e:
            logger.error(f"Error extracting SKU (Model NO.): {e}")
        
        return None
    
    def _extract_sku_selenium(self, element) -> Optional[str]:
        """Extract Model NO. as SKU using Selenium"""
        try:
            # Look for Model NO. in the product details
            model_selectors = [
                ".model-no", ".model", ".model-number", "[class*='model']",
                ".product-detail .model", ".specification .model"
            ]
            
            for selector in model_selectors:
                try:
                    found = element.find_element(By.CSS_SELECTOR, selector)
                    text = found.text.strip()
                    # Look for model number pattern (alphanumeric)
                    model_match = re.search(r'\b[A-Z0-9\-_]+\b', text)
                    if model_match:
                        return model_match.group(0)
                except NoSuchElementException:
                    continue
            
            # Fallback: look for any alphanumeric code that might be model number
            all_text = element.text
            model_match = re.search(r'\b[A-Z0-9\-_]+\b', all_text)
            if model_match:
                return model_match.group(0)
                
        except Exception as e:
            logger.error(f"Error extracting SKU (Model NO.) with Selenium: {e}")
        
        return None
    
    def _extract_brand(self, element) -> Optional[str]:
        """Extract brand information"""
        brand_selectors = [
            ".brand", ".manufacturer", "[class*='brand']", "[class*='manufacturer']"
        ]
        
        for selector in brand_selectors:
            try:
                found = element.select_one(selector)
                if found:
                    text = found.get_text(strip=True)
                    if text:
                        return text
            except:
                continue
        return None
    
    def _extract_brand_selenium(self, element) -> Optional[str]:
        """Extract brand using Selenium"""
        brand_selectors = [
            ".brand", ".manufacturer", "[class*='brand']", "[class*='manufacturer']"
        ]
        
        for selector in brand_selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                text = found.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue
        return None
    
    def get_product_details(self, product_url: str) -> Optional[ProductListing]:
        """Get detailed product information from product page"""
        try:
            if self.use_selenium:
                return self._get_product_details_selenium(product_url)
            else:
                return self._get_product_details_requests(product_url)
        except Exception as e:
            logger.error(f"Error getting product details for {product_url}: {e}")
            return None
    
    def _get_product_details_requests(self, product_url: str) -> Optional[ProductListing]:
        """Get product details using requests"""
        try:
            response = self.session.get(product_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract detailed information
            title = self._extract_text(soup, [".product-title", ".title", "h1"])
            description = self._extract_text(soup, [".description", ".detail", ".content"])
            price = self._extract_price(soup)
            images = self._extract_images(soup)
            seller = self._extract_seller_info(soup)
            
            return ProductListing(
                title=title or "Unknown",
                listing_url=product_url,
                price=price,
                description=description,
                images=images,
                seller=seller
            )
            
        except Exception as e:
            logger.error(f"Error getting product details with requests: {e}")
            return None
    
    def _get_product_details_selenium(self, product_url: str) -> Optional[ProductListing]:
        """Get product details using Selenium"""
        try:
            self.driver.get(product_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract detailed information
            title = self._extract_text_selenium(self.driver, [".product-title", ".title", "h1"])
            description = self._extract_text_selenium(self.driver, [".description", ".detail", ".content"])
            price = self._extract_price_selenium(self.driver)
            images = self._extract_images_selenium(self.driver)
            seller = self._extract_seller_info_selenium(self.driver)
            
            return ProductListing(
                title=title or "Unknown",
                listing_url=product_url,
                price=price,
                description=description,
                images=images,
                seller=seller
            )
            
        except Exception as e:
            logger.error(f"Error getting product details with Selenium: {e}")
            return None
    
    def get_seller_details(self, seller_profile_url: str) -> Optional[Seller]:
        """Get detailed seller information from seller profile page"""
        try:
            if self.use_selenium:
                return self._get_seller_details_selenium(seller_profile_url)
            else:
                return self._get_seller_details_requests(seller_profile_url)
        except Exception as e:
            logger.error(f"Error getting seller details for {seller_profile_url}: {e}")
            return None
    
    def _get_seller_details_requests(self, seller_profile_url: str) -> Optional[Seller]:
        """Get seller details using requests"""
        try:
            response = self.session.get(seller_profile_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract seller information
            seller_name = self._extract_text(soup, [".company-name", ".company-title", "h1", ".title"])
            
            # Extract rating and reviews
            rating = self._extract_rating(soup)
            total_reviews = self._extract_total_reviews(soup)
            
            # Extract contact information
            email = self._extract_email(soup)
            phone = self._extract_phone(soup)
            
            # Extract address information
            country = self._extract_country(soup)
            state_province = self._extract_state_province(soup)
            zip_code = self._extract_zip_code(soup)
            address = self._extract_address(soup)
            
            # Extract business information
            business_name = self._extract_business_name(soup)
            
            # Extract profile picture
            profile_picture = self._extract_profile_picture(soup)
            
            return Seller(
                name=seller_name,
                profile_url=seller_profile_url,
                profile_picture=profile_picture,
                rating=rating,
                total_reviews=total_reviews,
                business_name=business_name,
                country=country,
                address=address
            )
            
        except Exception as e:
            logger.error(f"Error getting seller details with requests: {e}")
            return None
    
    def _get_seller_details_selenium(self, seller_profile_url: str) -> Optional[Seller]:
        """Get seller details using Selenium"""
        try:
            self.driver.get(seller_profile_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract seller information
            seller_name = self._extract_text_selenium(self.driver, [".company-name", ".company-title", "h1", ".title"])
            
            # Extract rating and reviews
            rating = self._extract_rating_selenium(self.driver)
            total_reviews = self._extract_total_reviews_selenium(self.driver)
            
            # Extract contact information
            email = self._extract_email_selenium(self.driver)
            phone = self._extract_phone_selenium(self.driver)
            
            # Extract address information
            country = self._extract_country_selenium(self.driver)
            state_province = self._extract_state_province_selenium(self.driver)
            zip_code = self._extract_zip_code_selenium(self.driver)
            address = self._extract_address_selenium(self.driver)
            
            # Extract business information
            business_name = self._extract_business_name_selenium(self.driver)
            
            # Extract profile picture
            profile_picture = self._extract_profile_picture_selenium(self.driver)
            
            return Seller(
                name=seller_name,
                profile_url=seller_profile_url,
                profile_picture=profile_picture,
                rating=rating,
                total_reviews=total_reviews,
                business_name=business_name,
                country=country,
                address=address
            )
            
        except Exception as e:
            logger.error(f"Error getting seller details with Selenium: {e}")
            return None
    
    def close(self):
        """Close the scraper and cleanup resources"""
        if self.driver:
            self.driver.quit()
        self.session.close()
    
    def _extract_min_order_quantity(self, element) -> Optional[int]:
        """Extract minimum order quantity"""
        try:
            # Look for MOQ information in product-property
            moq_selectors = [
                ".product-property .attribute",
                ".moq-text",
                "[class*='moq']",
                "[class*='min']"
            ]
            
            for selector in moq_selectors:
                try:
                    found_elements = element.select(selector)
                    logger.debug(f"Found {len(found_elements)} elements with selector: {selector}")
                    for found in found_elements:
                        text = found.get_text(strip=True)
                        logger.debug(f"MOQ text: '{text}'")
                        # Look for number followed by "Pieces" or similar
                        match = re.search(r'(\d+)\s*(Pieces?|Units?|Sets?)', text, re.IGNORECASE)
                        if match:
                            moq_value = int(match.group(1))
                            logger.debug(f"Extracted MOQ: {moq_value}")
                            return moq_value
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error extracting min order quantity: {e}")
        
        return None
    
    def _extract_min_order_quantity_selenium(self, element) -> Optional[int]:
        """Extract minimum order quantity using Selenium"""
        try:
            # Look for MOQ information in product-property
            moq_selectors = [
                ".product-property .attribute",
                ".moq-text",
                "[class*='moq']",
                "[class*='min']"
            ]
            
            for selector in moq_selectors:
                try:
                    found_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for found in found_elements:
                        text = found.text.strip()
                        # Look for number followed by "Pieces" or similar
                        match = re.search(r'(\d+)\s*(Pieces?|Units?|Sets?)', text, re.IGNORECASE)
                        if match:
                            return int(match.group(1))
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.error(f"Error extracting min order quantity with Selenium: {e}")
        
        return None

    # Seller detail extraction methods
    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract seller rating from page"""
        try:
            rating_selectors = [
                ".rating",
                ".score", 
                ".stars",
                "[class*='rating']",
                "[class*='score']",
                ".evaluation-rate"
            ]
            
            for selector in rating_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    # Look for rating patterns like "5.0/5" or "Rating:5.0/5"
                    match = re.search(r'(\d+\.?\d*)/5', text)
                    if match:
                        return float(match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting rating: {e}")
        return None

    def _extract_rating_selenium(self, driver) -> Optional[float]:
        """Extract seller rating using Selenium"""
        try:
            rating_selectors = [
                ".rating",
                ".score",
                ".stars", 
                "[class*='rating']",
                "[class*='score']",
                ".evaluation-rate"
            ]
            
            for selector in rating_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        match = re.search(r'(\d+\.?\d*)/5', text)
                        if match:
                            return float(match.group(1))
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting rating with Selenium: {e}")
        return None

    def _extract_total_reviews(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract total reviews count"""
        try:
            review_selectors = [
                ".reviews",
                ".review-count",
                "[class*='review']",
                "[class*='feedback']"
            ]
            
            for selector in review_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    match = re.search(r'(\d+)', text)
                    if match:
                        return int(match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting total reviews: {e}")
        return None

    def _extract_total_reviews_selenium(self, driver) -> Optional[int]:
        """Extract total reviews count using Selenium"""
        try:
            review_selectors = [
                ".reviews",
                ".review-count", 
                "[class*='review']",
                "[class*='feedback']"
            ]
            
            for selector in review_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        match = re.search(r'(\d+)', text)
                        if match:
                            return int(match.group(1))
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting total reviews with Selenium: {e}")
        return None

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller email from certificates, PDFs, and contact sections"""
        try:
            # First, try to extract emails from certificate PDFs
            email_from_pdf = self._extract_email_from_certificate_pdfs(soup)
            if email_from_pdf:
                return email_from_pdf
            
            # Then, look for emails in certificates section text
            certificate_selectors = [
                ".certificate", ".certificates", ".cert", "[class*='certificate']",
                ".document", ".documents", "[class*='document']"
            ]
            
            for selector in certificate_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    # Find email pattern in certificate text
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                    if email_match:
                        return email_match.group(0)
            
            # Fallback: look for email in contact sections
            contact_selectors = [
                ".contact",
                ".email",
                ".contact-info",
                "[class*='contact']",
                "[class*='email']"
            ]
            
            for selector in contact_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    # Find email pattern
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                    if email_match:
                        return email_match.group(0)
        except Exception as e:
            logger.debug(f"Error extracting email: {e}")
        return None

    def _extract_email_from_certificate_pdfs(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract email from certificate PDF files by clicking on certificate images"""
        try:
            # Look for certificate image links that need to be clicked
            certificate_selectors = [
                ".certificate img",
                ".certificate a img",
                "[class*='certificate'] img",
                "img[alt*='certificate']",
                "img[alt*='Certificate']",
                "img[alt*='CE']",
                "img[alt*='CB']",
                "img[alt*='GS']"
            ]
            
            certificate_images = []
            for selector in certificate_selectors:
                images = soup.select(selector)
                for img in images:
                    # Get the parent link or the image itself
                    parent_link = img.find_parent('a')
                    if parent_link:
                        href = parent_link.get('href')
                        if href:
                            if href.startswith('http'):
                                certificate_images.append(href)
                            else:
                                certificate_images.append(f"https://www.made-in-china.com{href}")
                    else:
                        # If no parent link, try to find clickable elements around the image
                        clickable_parent = img.find_parent(attrs={'onclick': True}) or img.find_parent(attrs={'data-url': True})
                        if clickable_parent:
                            onclick = clickable_parent.get('onclick', '')
                            data_url = clickable_parent.get('data-url', '')
                            if 'certificate' in onclick.lower() or 'certificate' in data_url.lower():
                                certificate_images.append(data_url)
            
            logger.debug(f"Found {len(certificate_images)} certificate image links")
            
            # Limit to first 3 certificates to avoid too many requests
            for cert_url in certificate_images[:3]:
                try:
                    logger.debug(f"Analyzing certificate: {cert_url}")
                    analysis = self.pdf_extractor.analyze_url(cert_url)
                    if analysis.get('emails'):
                        return analysis['emails'][0]
                    
                    # Add delay between certificate clicks
                    time.sleep(2)
                    
                except Exception as e:
                    logger.debug(f"Error processing certificate {cert_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting email from certificate PDFs: {e}")
        
        return None

    # PDF text extraction is now handled by PDFExtractor

    def _extract_email_selenium(self, driver) -> Optional[str]:
        """Extract seller email from certificates, PDFs, and contact sections using Selenium"""
        try:
            # First, try to extract emails from certificate PDFs
            email_from_pdf = self._extract_email_from_certificate_pdfs_selenium(driver)
            if email_from_pdf:
                return email_from_pdf
            
            # Then, look for emails in certificates section text
            certificate_selectors = [
                ".certificate", ".certificates", ".cert", "[class*='certificate']",
                ".document", ".documents", "[class*='document']"
            ]
            
            for selector in certificate_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        # Find email pattern in certificate text
                        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                        if email_match:
                            return email_match.group(0)
                except NoSuchElementException:
                    continue
            
            # Fallback: look for email in contact sections
            contact_selectors = [
                ".contact",
                ".email",
                ".contact-info", 
                "[class*='contact']",
                "[class*='email']"
            ]
            
            for selector in contact_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                        if email_match:
                            return email_match.group(0)
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting email with Selenium: {e}")
        return None

    def _extract_email_from_certificate_pdfs_selenium(self, driver) -> Optional[str]:
        """Extract email from certificate PDF files by clicking certificate images using Selenium"""
        try:
            # Look for certificate image links that need to be clicked
            certificate_selectors = [
                ".certificate img",
                ".certificate a img",
                "[class*='certificate'] img",
                "img[alt*='certificate']",
                "img[alt*='Certificate']",
                "img[alt*='CE']",
                "img[alt*='CB']",
                "img[alt*='GS']"
            ]
            
            certificate_images = []
            for selector in certificate_selectors:
                try:
                    images = driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in images:
                        # Get the parent link or the image itself
                        try:
                            parent_link = img.find_element(By.XPATH, "./..")
                            if parent_link.tag_name == 'a':
                                href = parent_link.get_attribute('href')
                                if href:
                                    certificate_images.append(href)
                        except:
                            # If no parent link, try to find clickable elements around the image
                            try:
                                clickable_parent = img.find_element(By.XPATH, "./..")
                                onclick = clickable_parent.get_attribute('onclick')
                                data_url = clickable_parent.get_attribute('data-url')
                                if onclick and 'certificate' in onclick.lower():
                                    certificate_images.append(data_url or onclick)
                            except:
                                continue
                except NoSuchElementException:
                    continue
            
            logger.debug(f"Found {len(certificate_images)} certificate image links via Selenium")
            
            # Limit to first 3 certificates to avoid too many requests
            for cert_url in certificate_images[:3]:
                try:
                    logger.debug(f"Clicking certificate image via Selenium: {cert_url}")
                    
                    # Click on the certificate image to get the PDF
                    response = requests.get(cert_url, headers=HEADERS, timeout=15)
                    response.raise_for_status()
                    
                    # Check if the response is a PDF
                    if 'application/pdf' in response.headers.get('content-type', ''):
                        # Extract text from PDF
                        pdf_text = self._extract_text_from_pdf(response.content)
                        
                        if pdf_text:
                            # Look for email patterns in PDF text
                            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', pdf_text)
                            if email_match:
                                email = email_match.group(0)
                                logger.debug(f"Found email in certificate PDF via Selenium: {email}")
                                return email
                    else:
                        # If not a PDF, it might be a page with embedded PDF
                        cert_soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Look for embedded PDF or iframe
                        pdf_embed = cert_soup.find('embed', attrs={'type': 'application/pdf'})
                        pdf_iframe = cert_soup.find('iframe', attrs={'src': lambda x: x and '.pdf' in x})
                        
                        if pdf_embed:
                            pdf_src = pdf_embed.get('src')
                            if pdf_src:
                                pdf_response = requests.get(pdf_src, headers=HEADERS, timeout=15)
                                pdf_text = self._extract_text_from_pdf(pdf_response.content)
                                if pdf_text:
                                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', pdf_text)
                                    if email_match:
                                        return email_match.group(0)
                        
                        # Also look for emails in the certificate page text
                        page_text = cert_soup.get_text()
                        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
                        if email_match:
                            email = email_match.group(0)
                            logger.debug(f"Found email in certificate page via Selenium: {email}")
                            return email
                    
                    # Add delay between certificate clicks
                    time.sleep(2)
                    
                except Exception as e:
                    logger.debug(f"Error processing certificate {cert_url} via Selenium: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting email from certificate PDFs via Selenium: {e}")
        
        return None

    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller phone number"""
        try:
            phone_selectors = [
                ".phone",
                ".tel",
                ".telephone",
                "[class*='phone']",
                "[class*='tel']"
            ]
            
            for selector in phone_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    # Find phone pattern
                    phone_match = re.search(r'[\+\d\-\s\(\)]{7,}', text)
                    if phone_match:
                        return phone_match.group(0).strip()
        except Exception as e:
            logger.debug(f"Error extracting phone: {e}")
        return None

    def _extract_phone_selenium(self, driver) -> Optional[str]:
        """Extract seller phone number using Selenium"""
        try:
            phone_selectors = [
                ".phone",
                ".tel",
                ".telephone",
                "[class*='phone']",
                "[class*='tel']"
            ]
            
            for selector in phone_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        phone_match = re.search(r'[\+\d\-\s\(\)]{7,}', text)
                        if phone_match:
                            return phone_match.group(0).strip()
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting phone with Selenium: {e}")
        return None

    def _extract_country(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller country from company profile text"""
        try:
            # Look for location information in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    
                    # Look for Chinese provinces/cities with "China" pattern
                    location_patterns = [
                        r'([A-Za-z]+),\s*China',
                        r'([A-Za-z]+)\s*China',
                        r'Address:\s*([^,\n]+),\s*([^,\n]+),\s*China',
                        r'Location:\s*([^,\n]+),\s*([^,\n]+),\s*China'
                    ]
                    
                    for pattern in location_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            location = match.group(0)
                            # Clean up the location
                            location = re.sub(r'Address:\s*|Location:\s*', '', location)
                            return location.strip()
                            
        except Exception as e:
            logger.debug(f"Error extracting country: {e}")
        return None

    def _extract_country_selenium(self, driver) -> Optional[str]:
        """Extract seller country from company profile text using Selenium"""
        try:
            # Look for location information in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        
                        # Look for Chinese provinces/cities with "China" pattern
                        location_patterns = [
                            r'([A-Za-z]+),\s*China',
                            r'([A-Za-z]+)\s*China',
                            r'Address:\s*([^,\n]+),\s*([^,\n]+),\s*China',
                            r'Location:\s*([^,\n]+),\s*([^,\n]+),\s*China'
                        ]
                        
                        for pattern in location_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                location = match.group(0)
                                # Clean up the location
                                location = re.sub(r'Address:\s*|Location:\s*', '', location)
                                return location.strip()
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting country with Selenium: {e}")
        return None

    def _extract_state_province(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller state/province"""
        try:
            state_selectors = [
                ".state",
                ".province",
                ".region",
                "[class*='state']",
                "[class*='province']"
            ]
            
            for selector in state_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) < 30:
                        return text
        except Exception as e:
            logger.debug(f"Error extracting state/province: {e}")
        return None

    def _extract_state_province_selenium(self, driver) -> Optional[str]:
        """Extract seller state/province using Selenium"""
        try:
            state_selectors = [
                ".state",
                ".province",
                ".region",
                "[class*='state']",
                "[class*='province']"
            ]
            
            for selector in state_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) < 30:
                            return text
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting state/province with Selenium: {e}")
        return None

    def _extract_zip_code(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller zip code"""
        try:
            zip_selectors = [
                ".zip",
                ".postal",
                ".zipcode",
                "[class*='zip']",
                "[class*='postal']"
            ]
            
            for selector in zip_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    # Look for zip code pattern
                    zip_match = re.search(r'\b\d{5,6}\b', text)
                    if zip_match:
                        return zip_match.group(0)
        except Exception as e:
            logger.debug(f"Error extracting zip code: {e}")
        return None

    def _extract_zip_code_selenium(self, driver) -> Optional[str]:
        """Extract seller zip code using Selenium"""
        try:
            zip_selectors = [
                ".zip",
                ".postal",
                ".zipcode",
                "[class*='zip']",
                "[class*='postal']"
            ]
            
            for selector in zip_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        zip_match = re.search(r'\b\d{5,6}\b', text)
                        if zip_match:
                            return zip_match.group(0)
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting zip code with Selenium: {e}")
        return None

    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller address from company profile text"""
        try:
            # Look for address information in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    
                    # Look for address patterns
                    address_patterns = [
                        r'Address:\s*([^,\n]+),\s*([^,\n]+),\s*([^,\n]+)',
                        r'Location:\s*([^,\n]+),\s*([^,\n]+),\s*([^,\n]+)',
                        r'([A-Za-z]+),\s*([A-Za-z]+),\s*China',
                        r'([A-Za-z]+)\s*([A-Za-z]+),\s*China'
                    ]
                    
                    for pattern in address_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            address = match.group(0)
                            # Clean up the address
                            address = re.sub(r'Address:\s*|Location:\s*', '', address)
                            if len(address) > 5:  # Reasonable address length
                                return address.strip()
                            
        except Exception as e:
            logger.debug(f"Error extracting address: {e}")
        return None

    def _extract_address_selenium(self, driver) -> Optional[str]:
        """Extract seller address from company profile text using Selenium"""
        try:
            # Look for address information in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        
                        # Look for address patterns
                        address_patterns = [
                            r'Address:\s*([^,\n]+),\s*([^,\n]+),\s*([^,\n]+)',
                            r'Location:\s*([^,\n]+),\s*([^,\n]+),\s*([^,\n]+)',
                            r'([A-Za-z]+),\s*([A-Za-z]+),\s*China',
                            r'([A-Za-z]+)\s*([A-Za-z]+),\s*China'
                        ]
                        
                        for pattern in address_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                address = match.group(0)
                                # Clean up the address
                                address = re.sub(r'Address:\s*|Location:\s*', '', address)
                                if len(address) > 5:  # Reasonable address length
                                    return address.strip()
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting address with Selenium: {e}")
        return None

    def _extract_business_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract business/legal name from company profile text"""
        try:
            # Look for business name in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    
                    # Look for company name patterns
                    # Pattern 1: "COMPANY PROFILECompany Name" - extract just the company name
                    match = re.search(r'COMPANY PROFILE\s*([A-Za-z\s&]+(?:Co\.|Ltd|Limited|Corp|Corporation|Inc|Company|Technology|Electric|Industrial|Manufacturing|Group|International|Global))', text, re.IGNORECASE)
                    if match:
                        business_name = match.group(1).strip()
                        if len(business_name) > 3 and len(business_name) < 100:  # Reasonable business name length
                            return business_name
                    
                    # Pattern 2: "Company Name Co., Ltd" or similar
                    business_patterns = [
                        r'([A-Za-z\s&]+(?:Co\.|Ltd|Limited|Corp|Corporation|Inc|Company))',
                        r'([A-Za-z\s&]+(?:Technology|Electric|Industrial|Manufacturing))',
                        r'([A-Za-z\s&]+(?:Group|International|Global))'
                    ]
                    
                    for pattern in business_patterns:
                        match = re.search(pattern, text)
                        if match:
                            business_name = match.group(1).strip()
                            if len(business_name) > 5 and len(business_name) < 100:  # Reasonable length
                                return business_name
                            
        except Exception as e:
            logger.debug(f"Error extracting business name: {e}")
        return None

    def _extract_business_name_selenium(self, driver) -> Optional[str]:
        """Extract business/legal name from company profile text using Selenium"""
        try:
            # Look for business name in company profile text
            profile_selectors = [
                ".company-profile",
                ".profile",
                ".description",
                "[class*='profile']",
                "[class*='description']",
                "body"  # Fallback to entire page
            ]
            
            for selector in profile_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        
                        # Look for company name patterns
                        # Pattern 1: "COMPANY PROFILECompany Name" - extract just the company name
                        match = re.search(r'COMPANY PROFILE\s*([A-Za-z\s&]+(?:Co\.|Ltd|Limited|Corp|Corporation|Inc|Company|Technology|Electric|Industrial|Manufacturing|Group|International|Global))', text, re.IGNORECASE)
                        if match:
                            business_name = match.group(1).strip()
                            if len(business_name) > 3 and len(business_name) < 100:  # Reasonable business name length
                                return business_name
                        
                        # Pattern 2: "Company Name Co., Ltd" or similar
                        business_patterns = [
                            r'([A-Za-z\s&]+(?:Co\.|Ltd|Limited|Corp|Corporation|Inc|Company))',
                            r'([A-Za-z\s&]+(?:Technology|Electric|Industrial|Manufacturing))',
                            r'([A-Za-z\s&]+(?:Group|International|Global))'
                        ]
                        
                        for pattern in business_patterns:
                            match = re.search(pattern, text)
                            if match:
                                business_name = match.group(1).strip()
                                if len(business_name) > 5 and len(business_name) < 100:  # Reasonable length
                                    return business_name
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting business name with Selenium: {e}")
        return None

    def _extract_profile_picture(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller profile picture URL from avatar next to seller name"""
        try:
            # Look for avatar next to seller name
            avatar_selectors = [
                ".company-name img",  # Avatar next to company name
                ".seller-name img",   # Avatar next to seller name
                ".company-info img",  # Avatar in company info section
                ".profile-avatar img", # Profile avatar
                ".avatar img",        # General avatar
                "[class*='company'] img", # Any company-related image
                "[class*='seller'] img"   # Any seller-related image
            ]
            
            for selector in avatar_selectors:
                elements = soup.select(selector)
                for element in elements:
                    src = element.get('src') or element.get('data-src')
                    if src:
                        # Ensure it's a valid image URL
                        if src.startswith('http') or src.startswith('//'):
                            return src
                        elif src.startswith('/'):
                            return f"https://www.made-in-china.com{src}"
        except Exception as e:
            logger.debug(f"Error extracting profile picture: {e}")
        return None

    def _extract_profile_picture_selenium(self, driver) -> Optional[str]:
        """Extract seller profile picture URL from avatar next to seller name using Selenium"""
        try:
            # Look for avatar next to seller name
            avatar_selectors = [
                ".company-name img",  # Avatar next to company name
                ".seller-name img",   # Avatar next to seller name
                ".company-info img",  # Avatar in company info section
                ".profile-avatar img", # Profile avatar
                ".avatar img",        # General avatar
                "[class*='company'] img", # Any company-related image
                "[class*='seller'] img"   # Any seller-related image
            ]
            
            for selector in avatar_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        src = element.get_attribute('src') or element.get_attribute('data-src')
                        if src:
                            # Ensure it's a valid image URL
                            if src.startswith('http') or src.startswith('//'):
                                return src
                            elif src.startswith('/'):
                                return f"https://www.made-in-china.com{src}"
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting profile picture with Selenium: {e}")
        return None

    def _extract_description(self, element) -> Optional[str]:
        """Extract product description"""
        try:
            description_selectors = [
                ".description",
                ".product-description",
                ".detail",
                ".summary",
                "[class*='description']",
                "[class*='detail']",
                ".product-detail",
                ".product-summary"
            ]
            
            for selector in description_selectors:
                found = element.select_one(selector)
                if found:
                    text = found.get_text(strip=True)
                    if text and len(text) > 10:  # Reasonable description length
                        return text
        except Exception as e:
            logger.debug(f"Error extracting description: {e}")
        return None

    def _extract_description_selenium(self, element) -> Optional[str]:
        """Extract product description using Selenium"""
        try:
            description_selectors = [
                ".description",
                ".product-description",
                ".detail",
                ".summary",
                "[class*='description']",
                "[class*='detail']",
                ".product-detail",
                ".product-summary"
            ]
            
            for selector in description_selectors:
                try:
                    found = element.find_element(By.CSS_SELECTOR, selector)
                    text = found.text.strip()
                    if text and len(text) > 10:  # Reasonable description length
                        return text
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting description with Selenium: {e}")
        return None

    def _get_product_details_from_page(self, product_url: str) -> tuple[Optional[str], Optional[str]]:
        """Get HS Code and Model NO. from individual product page"""
        try:
            logger.debug(f"Getting product details from: {product_url}")
            
            # Add delay to be respectful to the server
            time.sleep(1)
            
            response = requests.get(product_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract HS Code
            hs_code = self._extract_hs_code_from_page(soup)
            
            # Extract Model NO.
            model_no = self._extract_model_no_from_page(soup)
            
            logger.debug(f"Extracted - HS Code: {hs_code}, Model NO: {model_no}")
            
            return hs_code, model_no
            
        except Exception as e:
            logger.warning(f"Error getting product details from {product_url}: {e}")
            return None, None

    def _extract_hs_code_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract HS Code from product page"""
        try:
            # Look for HS Code in various formats
            hs_code_patterns = [
                r'HS Code[:\s]*(\d{10})',
                r'H\.S\. Code[:\s]*(\d{10})',
                r'HSCode[:\s]*(\d{10})',
                r'HS[:\s]*(\d{10})'
            ]
            
            # Search in the entire page text
            page_text = soup.get_text()
            
            for pattern in hs_code_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # Also look for 10-digit numbers that might be HS codes
            # HS codes for electrical appliances are typically in the 85xxxx range
            hs_matches = re.findall(r'\b85\d{8}\b', page_text)
            if hs_matches:
                return hs_matches[0]
                
        except Exception as e:
            logger.debug(f"Error extracting HS Code: {e}")
        
        return None

    def _extract_model_no_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract Model NO. from product page"""
        try:
            # Look for Model NO. in various formats
            model_patterns = [
                r'Model NO[.:\s]*([A-Z0-9\-_]+)',
                r'Model Number[:\s]*([A-Z0-9\-_]+)',
                r'Model[:\s]*([A-Z0-9\-_]+)',
                r'Product Model[:\s]*([A-Z0-9\-_]+)'
            ]
            
            # Search in the entire page text
            page_text = soup.get_text()
            
            for pattern in model_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    model = match.group(1).strip()
                    # Filter out very short or very long model numbers
                    if 3 <= len(model) <= 20:
                        return model
            
            # Also look for alphanumeric codes that might be model numbers
            # Look for patterns like WT-8200, HD-15, etc.
            model_matches = re.findall(r'\b[A-Z]{2,4}[-_]?\d{2,4}\b', page_text)
            if model_matches:
                return model_matches[0]
                
        except Exception as e:
            logger.debug(f"Error extracting Model NO: {e}")
        
        return None

    def get_company_profile(self, company_url: str) -> Optional[Dict[str, Any]]:
        """Get detailed company profile information including contact details"""
        logger.info(f"Getting company profile from: {company_url}")
        
        try:
            if self.use_selenium:
                return self._get_company_profile_selenium(company_url)
            else:
                return self._get_company_profile_requests(company_url)
                
        except Exception as e:
            logger.error(f"Error getting company profile from {company_url}: {e}")
            return None

    def _get_company_profile_requests(self, company_url: str) -> Optional[Dict[str, Any]]:
        """Get company profile using requests"""
        try:
            response = self.session.get(company_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            profile_data = {
                'company_name': self._extract_company_name(soup),
                'contact_person': self._extract_contact_person(soup),
                'email': self._extract_email_from_page(soup),
                'phone': self._extract_phone_from_page(soup),
                'address': self._extract_company_address(soup),
                'business_type': self._extract_business_type(soup),
                'year_established': self._extract_year_established(soup),
                'main_products': self._extract_main_products(soup),
                'certificates': self._extract_certificates(soup),
                'profile_url': company_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error getting company profile with requests: {e}")
            return None

    def _get_company_profile_selenium(self, company_url: str) -> Optional[Dict[str, Any]]:
        """Get company profile using Selenium"""
        try:
            self.driver.get(company_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for page to load completely
            time.sleep(3)
            
            profile_data = {
                'company_name': self._extract_company_name_selenium(self.driver),
                'contact_person': self._extract_contact_person_selenium(self.driver),
                'email': self._extract_email_from_page_selenium(self.driver),
                'phone': self._extract_phone_from_page_selenium(self.driver),
                'address': self._extract_company_address_selenium(self.driver),
                'business_type': self._extract_business_type_selenium(self.driver),
                'year_established': self._extract_year_established_selenium(self.driver),
                'main_products': self._extract_main_products_selenium(self.driver),
                'certificates': self._extract_certificates_selenium(self.driver),
                'profile_url': company_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error getting company profile with Selenium: {e}")
            return None

    def _extract_company_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company name from company profile page"""
        try:
            # Look for company name in various selectors
            name_selectors = [
                "h1.company-name",
                ".company-name h1",
                ".company-title",
                ".company-info h1",
                "[class*='company-name']",
                "h1",
                ".profile-title"
            ]
            
            for selector in name_selectors:
                element = soup.select_one(selector)
                if element:
                    name = element.get_text(strip=True)
                    if name and len(name) > 3 and len(name) < 100:
                        return name
            
            # Also look for company name in page title
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # Extract company name from title (usually format: "Company Name - Made-in-China.com")
                if ' - Made-in-China.com' in title_text:
                    company_name = title_text.split(' - Made-in-China.com')[0]
                    if company_name and len(company_name) > 3:
                        return company_name
                        
        except Exception as e:
            logger.debug(f"Error extracting company name: {e}")
        
        return None

    def _extract_company_name_selenium(self, driver) -> Optional[str]:
        """Extract company name using Selenium"""
        try:
            name_selectors = [
                "h1.company-name",
                ".company-name h1",
                ".company-title",
                ".company-info h1",
                "[class*='company-name']",
                "h1",
                ".profile-title"
            ]
            
            for selector in name_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    name = element.text.strip()
                    if name and len(name) > 3 and len(name) < 100:
                        return name
                except NoSuchElementException:
                    continue
            
            # Check page title
            title = driver.title
            if ' - Made-in-China.com' in title:
                company_name = title.split(' - Made-in-China.com')[0]
                if company_name and len(company_name) > 3:
                    return company_name
                    
        except Exception as e:
            logger.debug(f"Error extracting company name with Selenium: {e}")
        
        return None

    def _extract_contact_person(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact person name from company profile"""
        try:
            # Look for contact person in various formats
            contact_selectors = [
                ".contact-person",
                ".contact-info .name",
                ".sales-contact",
                ".contact-details .person",
                "[class*='contact'][class*='person']",
                ".profile-contact .name"
            ]
            
            for selector in contact_selectors:
                element = soup.select_one(selector)
                if element:
                    name = element.get_text(strip=True)
                    if name and len(name) > 2 and len(name) < 50:
                        return name
            
            # Look for patterns like "Mr. Jason Lin" or "sales manager"
            page_text = soup.get_text()
            contact_patterns = [
                r'(Mr\.|Ms\.|Mrs\.)\s+([A-Za-z\s]+)',
                r'([A-Za-z\s]+)\s+(sales manager|manager|director)',
                r'Contact:\s*([A-Za-z\s]+)'
            ]
            
            for pattern in contact_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    contact = match.group(0).strip()
                    if len(contact) > 3 and len(contact) < 50:
                        return contact
                        
        except Exception as e:
            logger.debug(f"Error extracting contact person: {e}")
        
        return None

    def _extract_contact_person_selenium(self, driver) -> Optional[str]:
        """Extract contact person using Selenium"""
        try:
            contact_selectors = [
                ".contact-person",
                ".contact-info .name",
                ".sales-contact",
                ".contact-details .person",
                "[class*='contact'][class*='person']",
                ".profile-contact .name"
            ]
            
            for selector in contact_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    name = element.text.strip()
                    if name and len(name) > 2 and len(name) < 50:
                        return name
                except NoSuchElementException:
                    continue
            
            # Check page text for patterns
            page_text = driver.page_source
            contact_patterns = [
                r'(Mr\.|Ms\.|Mrs\.)\s+([A-Za-z\s]+)',
                r'([A-Za-z\s]+)\s+(sales manager|manager|director)',
                r'Contact:\s*([A-Za-z\s]+)'
            ]
            
            for pattern in contact_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    contact = match.group(0).strip()
                    if len(contact) > 3 and len(contact) < 50:
                        return contact
                        
        except Exception as e:
            logger.debug(f"Error extracting contact person with Selenium: {e}")
        
        return None

    def _extract_email_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract email address from company profile page"""
        try:
            # Look for email in various formats
            email_selectors = [
                "a[href^='mailto:']",
                ".email",
                ".contact-email",
                ".company-email",
                "[class*='email']",
                ".contact-info a[href*='mailto']"
            ]
            
            for selector in email_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # Check href attribute for mailto links
                    href = element.get('href')
                    if href and href.startswith('mailto:'):
                        email = href.replace('mailto:', '').split('?')[0]
                        if self._is_valid_email(email):
                            return email
                    
                    # Check text content for email patterns
                    text = element.get_text(strip=True)
                    if self._is_valid_email(text):
                        return text
            
            # Search entire page text for email patterns
            page_text = soup.get_text()
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, page_text)
            
            for email in emails:
                if self._is_valid_email(email):
                    return email
                    
        except Exception as e:
            logger.debug(f"Error extracting email: {e}")
        
        return None

    def _extract_email_from_page_selenium(self, driver) -> Optional[str]:
        """Extract email address using Selenium"""
        try:
            email_selectors = [
                "a[href^='mailto:']",
                ".email",
                ".contact-email",
                ".company-email",
                "[class*='email']",
                ".contact-info a[href*='mailto']"
            ]
            
            for selector in email_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Check href attribute
                        href = element.get_attribute('href')
                        if href and href.startswith('mailto:'):
                            email = href.replace('mailto:', '').split('?')[0]
                            if self._is_valid_email(email):
                                return email
                        
                        # Check text content
                        text = element.text.strip()
                        if self._is_valid_email(text):
                            return text
                except NoSuchElementException:
                    continue
            
            # Search page source for email patterns
            page_source = driver.page_source
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, page_source)
            
            for email in emails:
                if self._is_valid_email(email):
                    return email
                    
        except Exception as e:
            logger.debug(f"Error extracting email with Selenium: {e}")
        
        return None

    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format"""
        if not email or len(email) < 5 or len(email) > 100:
            return False
        
        # Basic email validation
        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return bool(re.match(email_pattern, email))

    def _extract_phone_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract phone number from company profile page"""
        try:
            # Look for phone in various formats
            phone_selectors = [
                ".phone",
                ".contact-phone",
                ".company-phone",
                "[class*='phone']",
                ".contact-info .phone",
                "a[href^='tel:']"
            ]
            
            for selector in phone_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # Check href attribute for tel links
                    href = element.get('href')
                    if href and href.startswith('tel:'):
                        phone = href.replace('tel:', '').strip()
                        if self._is_valid_phone(phone):
                            return phone
                    
                    # Check text content
                    text = element.get_text(strip=True)
                    if self._is_valid_phone(text):
                        return text
            
            # Search entire page text for phone patterns
            page_text = soup.get_text()
            phone_patterns = [
                r'\+?[\d\s\-\(\)]{7,15}',  # International format
                r'[\d\s\-\(\)]{7,15}',     # Local format
            ]
            
            for pattern in phone_patterns:
                phones = re.findall(pattern, page_text)
                for phone in phones:
                    if self._is_valid_phone(phone):
                        return phone
                        
        except Exception as e:
            logger.debug(f"Error extracting phone: {e}")
        
        return None

    def _extract_phone_from_page_selenium(self, driver) -> Optional[str]:
        """Extract phone number using Selenium"""
        try:
            phone_selectors = [
                ".phone",
                ".contact-phone",
                ".company-phone",
                "[class*='phone']",
                ".contact-info .phone",
                "a[href^='tel:']"
            ]
            
            for selector in phone_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Check href attribute
                        href = element.get_attribute('href')
                        if href and href.startswith('tel:'):
                            phone = href.replace('tel:', '').strip()
                            if self._is_valid_phone(phone):
                                return phone
                        
                        # Check text content
                        text = element.text.strip()
                        if self._is_valid_phone(text):
                            return text
                except NoSuchElementException:
                    continue
            
            # Search page source for phone patterns
            page_source = driver.page_source
            phone_patterns = [
                r'\+?[\d\s\-\(\)]{7,15}',
                r'[\d\s\-\(\)]{7,15}',
            ]
            
            for pattern in phone_patterns:
                phones = re.findall(pattern, page_source)
                for phone in phones:
                    if self._is_valid_phone(phone):
                        return phone
                        
        except Exception as e:
            logger.debug(f"Error extracting phone with Selenium: {e}")
        
        return None

    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        if not phone or len(phone) < 7 or len(phone) > 20:
            return False
        
        # Remove common separators and check if it's mostly digits
        digits_only = re.sub(r'[\s\-\(\)\+]', '', phone)
        return len(digits_only) >= 7 and digits_only.isdigit()

    def _extract_company_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company address from profile page"""
        try:
            address_selectors = [
                ".address",
                ".company-address",
                ".contact-address",
                "[class*='address']",
                ".company-info .address",
                ".profile-address"
            ]
            
            for selector in address_selectors:
                element = soup.select_one(selector)
                if element:
                    address = element.get_text(strip=True)
                    if address and len(address) > 10 and len(address) < 200:
                        return address
            
            # Look for address patterns in page text
            page_text = soup.get_text()
            address_patterns = [
                r'Address[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'Location[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'([A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*China)'
            ]
            
            for pattern in address_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    address = match.group(1).strip()
                    if len(address) > 10 and len(address) < 200:
                        return address
                        
        except Exception as e:
            logger.debug(f"Error extracting company address: {e}")
        
        return None

    def _extract_company_address_selenium(self, driver) -> Optional[str]:
        """Extract company address using Selenium"""
        try:
            address_selectors = [
                ".address",
                ".company-address",
                ".contact-address",
                "[class*='address']",
                ".company-info .address",
                ".profile-address"
            ]
            
            for selector in address_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    address = element.text.strip()
                    if address and len(address) > 10 and len(address) < 200:
                        return address
                except NoSuchElementException:
                    continue
            
            # Check page text for address patterns
            page_text = driver.page_source
            address_patterns = [
                r'Address[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'Location[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'([A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*China)'
            ]
            
            for pattern in address_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    address = match.group(1).strip()
                    if len(address) > 10 and len(address) < 200:
                        return address
                        
        except Exception as e:
            logger.debug(f"Error extracting company address with Selenium: {e}")
        
        return None

    def _extract_business_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract business type from company profile"""
        try:
            business_type_selectors = [
                ".business-type",
                ".company-type",
                "[class*='business-type']",
                ".company-info .type"
            ]
            
            for selector in business_type_selectors:
                element = soup.select_one(selector)
                if element:
                    business_type = element.get_text(strip=True)
                    if business_type and len(business_type) > 3:
                        return business_type
            
            # Look for business type patterns
            page_text = soup.get_text()
            type_patterns = [
                r'Business Type[:\s]+([^,\n]+)',
                r'Company Type[:\s]+([^,\n]+)',
                r'(Manufacturer/Factory|Trading Company|Distributor|Wholesaler)'
            ]
            
            for pattern in type_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    business_type = match.group(1).strip()
                    if len(business_type) > 3:
                        return business_type
                        
        except Exception as e:
            logger.debug(f"Error extracting business type: {e}")
        
        return None

    def _extract_business_type_selenium(self, driver) -> Optional[str]:
        """Extract business type using Selenium"""
        try:
            business_type_selectors = [
                ".business-type",
                ".company-type",
                "[class*='business-type']",
                ".company-info .type"
            ]
            
            for selector in business_type_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    business_type = element.text.strip()
                    if business_type and len(business_type) > 3:
                        return business_type
                except NoSuchElementException:
                    continue
            
            # Check page text for business type patterns
            page_text = driver.page_source
            type_patterns = [
                r'Business Type[:\s]+([^,\n]+)',
                r'Company Type[:\s]+([^,\n]+)',
                r'(Manufacturer/Factory|Trading Company|Distributor|Wholesaler)'
            ]
            
            for pattern in type_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    business_type = match.group(1).strip()
                    if len(business_type) > 3:
                        return business_type
                        
        except Exception as e:
            logger.debug(f"Error extracting business type with Selenium: {e}")
        
        return None

    def _extract_year_established(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract year established from company profile"""
        try:
            year_selectors = [
                ".year-established",
                ".established-year",
                "[class*='year']",
                ".company-info .year"
            ]
            
            for selector in year_selectors:
                element = soup.select_one(selector)
                if element:
                    year = element.get_text(strip=True)
                    if self._is_valid_year(year):
                        return year
            
            # Look for year patterns
            page_text = soup.get_text()
            year_patterns = [
                r'Established[:\s]+(\d{4})',
                r'Founded[:\s]+(\d{4})',
                r'Year[:\s]+(\d{4})',
                r'Since[:\s]+(\d{4})'
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    year = match.group(1)
                    if self._is_valid_year(year):
                        return year
                        
        except Exception as e:
            logger.debug(f"Error extracting year established: {e}")
        
        return None

    def _extract_year_established_selenium(self, driver) -> Optional[str]:
        """Extract year established using Selenium"""
        try:
            year_selectors = [
                ".year-established",
                ".established-year",
                "[class*='year']",
                ".company-info .year"
            ]
            
            for selector in year_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    year = element.text.strip()
                    if self._is_valid_year(year):
                        return year
                except NoSuchElementException:
                    continue
            
            # Check page text for year patterns
            page_text = driver.page_source
            year_patterns = [
                r'Established[:\s]+(\d{4})',
                r'Founded[:\s]+(\d{4})',
                r'Year[:\s]+(\d{4})',
                r'Since[:\s]+(\d{4})'
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    year = match.group(1)
                    if self._is_valid_year(year):
                        return year
                        
        except Exception as e:
            logger.debug(f"Error extracting year established with Selenium: {e}")
        
        return None

    def _is_valid_year(self, year: str) -> bool:
        """Validate year format"""
        try:
            year_int = int(year)
            return 1900 <= year_int <= 2025
        except (ValueError, TypeError):
            return False

    def _extract_main_products(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main products from company profile"""
        try:
            products_selectors = [
                ".main-products",
                ".products",
                ".company-products",
                "[class*='products']"
            ]
            
            for selector in products_selectors:
                element = soup.select_one(selector)
                if element:
                    products = element.get_text(strip=True)
                    if products and len(products) > 5:
                        return products
            
            # Look for products patterns
            page_text = soup.get_text()
            products_patterns = [
                r'Main Products[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'Products[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)'
            ]
            
            for pattern in products_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    products = match.group(1).strip()
                    if len(products) > 5:
                        return products
                        
        except Exception as e:
            logger.debug(f"Error extracting main products: {e}")
        
        return None

    def _extract_main_products_selenium(self, driver) -> Optional[str]:
        """Extract main products using Selenium"""
        try:
            products_selectors = [
                ".main-products",
                ".products",
                ".company-products",
                "[class*='products']"
            ]
            
            for selector in products_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    products = element.text.strip()
                    if products and len(products) > 5:
                        return products
                except NoSuchElementException:
                    continue
            
            # Check page text for products patterns
            page_text = driver.page_source
            products_patterns = [
                r'Main Products[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)',
                r'Products[:\s]+([^,\n]+(?:[,\n][^,\n]+)*)'
            ]
            
            for pattern in products_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    products = match.group(1).strip()
                    if len(products) > 5:
                        return products
                        
        except Exception as e:
            logger.debug(f"Error extracting main products with Selenium: {e}")
        
        return None

    def _extract_certificates(self, soup: BeautifulSoup) -> List[str]:
        """Extract certificates from company profile"""
        certificates = []
        try:
            # Look for certificate sections
            cert_selectors = [
                ".certificates",
                ".certificate-list",
                "[class*='certificate']",
                ".company-certificates"
            ]
            
            for selector in cert_selectors:
                elements = soup.select(selector)
                for element in elements:
                    cert_text = element.get_text(strip=True)
                    if cert_text and len(cert_text) > 3:
                        certificates.append(cert_text)
            
            # Look for certificate patterns
            page_text = soup.get_text()
            cert_patterns = [
                r'(CE|CB|GS|ISO|RoHS|FCC|UL)\s+[Cc]ertificate?',
                r'[Cc]ertificate[:\s]+([^,\n]+)',
                r'([A-Z]{2,4})\s+[Cc]ertification'
            ]
            
            for pattern in cert_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cert = match[0]
                    else:
                        cert = match
                    if cert and len(cert) > 2:
                        certificates.append(cert)
                        
        except Exception as e:
            logger.debug(f"Error extracting certificates: {e}")
        
        return list(set(certificates))  # Remove duplicates

    def _extract_certificates_selenium(self, driver) -> List[str]:
        """Extract certificates using Selenium"""
        certificates = []
        try:
            cert_selectors = [
                ".certificates",
                ".certificate-list",
                "[class*='certificate']",
                ".company-certificates"
            ]
            
            for selector in cert_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        cert_text = element.text.strip()
                        if cert_text and len(cert_text) > 3:
                            certificates.append(cert_text)
                except NoSuchElementException:
                    continue
            
            # Check page text for certificate patterns
            page_text = driver.page_source
            cert_patterns = [
                r'(CE|CB|GS|ISO|RoHS|FCC|UL)\s+[Cc]ertificate?',
                r'[Cc]ertificate[:\s]+([^,\n]+)',
                r'([A-Z]{2,4})\s+[Cc]ertification'
            ]
            
            for pattern in cert_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cert = match[0]
                    else:
                        cert = match
                    if cert and len(cert) > 2:
                        certificates.append(cert)
                        
        except Exception as e:
            logger.debug(f"Error extracting certificates with Selenium: {e}")
        
        return list(set(certificates))  # Remove duplicates

    def extract_certificate_pdfs(self, company_url: str) -> List[Dict[str, Any]]:
        """Extract PDF certificate URLs and download them for email analysis"""
        logger.info(f"Extracting certificate PDFs from: {company_url}")
        
        try:
            if self.use_selenium:
                return self._extract_certificate_pdfs_selenium(company_url)
            else:
                return self._extract_certificate_pdfs_requests(company_url)
                
        except Exception as e:
            logger.error(f"Error extracting certificate PDFs from {company_url}: {e}")
            return []

    def _extract_certificate_pdfs_requests(self, company_url: str) -> List[Dict[str, Any]]:
        """Extract certificate PDF URLs using requests"""
        try:
            response = self.session.get(company_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            certificates = []
            
            # Look for certificate sections and images
            cert_selectors = [
                ".certificates img",
                ".certificate-list img",
                "[class*='certificate'] img",
                ".company-certificates img",
                ".certificate img",
                ".cert img",
                ".company-show img",
                ".company-info img",
                ".profile-certificates img",
                ".audit-certificates img",
                ".quality-certificates img"
            ]
            
            for selector in cert_selectors:
                elements = soup.select(selector)
                for element in elements:
                    cert_info = self._extract_certificate_info(element, company_url)
                    if cert_info:
                        certificates.append(cert_info)
            
            # Look for certificate links
            cert_link_selectors = [
                "a[href*='certificate']",
                "a[href*='cert']",
                "a[href*='audit']",
                "a[href*='quality']",
                ".certificate a",
                ".cert a",
                ".audit a",
                ".quality a"
            ]
            
            for selector in cert_link_selectors:
                elements = soup.select(selector)
                for element in elements:
                    cert_info = self._extract_certificate_info(element, company_url)
                    if cert_info:
                        certificates.append(cert_info)
            
            # Look for certificate patterns in page text
            page_text = soup.get_text()
            cert_patterns = [
                r'(CE|CB|GS|ISO|RoHS|FCC|UL)\s+[Cc]ertificate?',
                r'[Cc]ertificate[:\s]+([^,\n]+)',
                r'([A-Z]{2,4})\s+[Cc]ertification',
                r'([A-Z]{2,4})\s+[Aa]udit',
                r'([A-Z]{2,4})\s+[Qq]uality'
            ]
            
            for pattern in cert_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cert_name = match[0]
                    else:
                        cert_name = match
                    if cert_name and len(cert_name) > 2:
                        # Try to find the actual certificate image/link for this type
                        cert_url = self._find_certificate_url_for_type(soup, cert_name, company_url)
                        certificates.append({
                            'name': f"{cert_name} Certificate",
                            'url': cert_url,
                            'type': 'mentioned_in_text'
                        })
            
            return certificates
            
        except Exception as e:
            logger.error(f"Error extracting certificate PDFs with requests: {e}")
            return []

    def _extract_certificate_pdfs_selenium(self, company_url: str) -> List[Dict[str, Any]]:
        """Extract certificate PDF URLs using Selenium"""
        try:
            self.driver.get(company_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for page to load completely
            time.sleep(3)
            
            certificates = []
            
            # Look for certificate sections and images
            cert_selectors = [
                ".certificates img",
                ".certificate-list img",
                "[class*='certificate'] img",
                ".company-certificates img",
                ".certificate img",
                ".cert img",
                ".company-show img",
                ".company-info img",
                ".profile-certificates img",
                ".audit-certificates img",
                ".quality-certificates img"
            ]
            
            for selector in cert_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        cert_info = self._extract_certificate_info_selenium(element, company_url)
                        if cert_info:
                            certificates.append(cert_info)
                except NoSuchElementException:
                    continue
            
            # Look for certificate links
            cert_link_selectors = [
                "a[href*='certificate']",
                "a[href*='cert']",
                "a[href*='audit']",
                "a[href*='quality']",
                ".certificate a",
                ".cert a",
                ".audit a",
                ".quality a"
            ]
            
            for selector in cert_link_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        cert_info = self._extract_certificate_info_selenium(element, company_url)
                        if cert_info:
                            certificates.append(cert_info)
                except NoSuchElementException:
                    continue
            
            # Look for certificate patterns in page source
            page_source = self.driver.page_source
            cert_patterns = [
                r'(CE|CB|GS|ISO|RoHS|FCC|UL)\s+[Cc]ertificate?',
                r'[Cc]ertificate[:\s]+([^,\n]+)',
                r'([A-Z]{2,4})\s+[Cc]ertification',
                r'([A-Z]{2,4})\s+[Aa]udit',
                r'([A-Z]{2,4})\s+[Qq]uality'
            ]
            
            for pattern in cert_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cert_name = match[0]
                    else:
                        cert_name = match
                    if cert_name and len(cert_name) > 2:
                        # Try to find the actual certificate image/link for this type
                        cert_url = self._find_certificate_url_for_type_selenium(cert_name, company_url)
                        certificates.append({
                            'name': f"{cert_name} Certificate",
                            'url': cert_url,
                            'type': 'mentioned_in_text'
                        })
            
            return certificates
            
        except Exception as e:
            logger.error(f"Error extracting certificate PDFs with Selenium: {e}")
            return []

    def _find_certificate_url_for_type(self, soup: BeautifulSoup, cert_type: str, base_url: str) -> Optional[str]:
        """Find the actual certificate URL for a specific certificate type"""
        try:
            # Look for images with alt text containing the certificate type
            alt_pattern = re.compile(f".*{cert_type}.*", re.IGNORECASE)
            
            # Search for images with matching alt text
            images = soup.find_all('img', alt=alt_pattern)
            for img in images:
                src = img.get('src')
                if src:
                    # Clean up double slashes in URLs
                    if src.startswith('//'):
                        src = src[2:]  # Remove leading //
                    
                    if src.startswith('http'):
                        return src
                    elif src.startswith('/'):
                        # Check if src already contains made-in-china.com
                        if 'made-in-china.com' in src:
                            return src
                        else:
                            return f"https://www.made-in-china.com{src}"
                    else:
                        return f"{base_url.rstrip('/')}/{src.lstrip('/')}"
            
            # Search for links with certificate type in text or href
            links = soup.find_all('a', href=True)
            for link in links:
                link_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if (cert_type.lower() in link_text.lower() or 
                    cert_type.lower() in href.lower()):
                    
                    # Clean up double slashes and fix URL construction
                    if href.startswith('//'):
                        href = 'https:' + href  # Convert // to https://
                    elif href.startswith('/'):
                        # Check if href already contains made-in-china.com
                        if 'made-in-china.com' in href:
                            # Fix double domain issue
                            if href.count('made-in-china.com') > 1:
                                href = href.replace('//www.made-in-china.com', '')
                                href = 'https://www.made-in-china.com' + href
                            else:
                                href = 'https://www.made-in-china.com' + href
                        else:
                            href = f"https://www.made-in-china.com{href}"
                    elif not href.startswith('http'):
                        href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    return href
            
            return None
            
        except Exception as e:
            logger.debug(f"Error finding certificate URL for {cert_type}: {e}")
            return None

    def _find_certificate_url_for_type_selenium(self, cert_type: str, base_url: str) -> Optional[str]:
        """Find the actual certificate URL for a specific certificate type using Selenium"""
        try:
            # Look for images with alt text containing the certificate type
            alt_pattern = f"*[alt*='{cert_type}' i]"
            
            try:
                images = self.driver.find_elements(By.CSS_SELECTOR, alt_pattern)
                for img in images:
                    src = img.get_attribute('src')
                    if src:
                        if src.startswith('http'):
                            return src
                        elif src.startswith('/'):
                            return f"https://www.made-in-china.com{src}"
                        else:
                            return f"{base_url.rstrip('/')}/{src.lstrip('/')}"
            except NoSuchElementException:
                pass
            
            # Search for links with certificate type in text or href
            try:
                links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    link_text = link.text.strip()
                    href = link.get_attribute('href') or ''
                    
                    if (cert_type.lower() in link_text.lower() or 
                        cert_type.lower() in href.lower()):
                        
                        if href.startswith('http'):
                            return href
                        elif href.startswith('/'):
                            # Check if href already contains made-in-china.com
                            if 'made-in-china.com' in href:
                                return href
                            else:
                                return f"https://www.made-in-china.com{href}"
                        else:
                            return f"{base_url.rstrip('/')}/{href.lstrip('/')}"
            except NoSuchElementException:
                pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Error finding certificate URL for {cert_type} with Selenium: {e}")
            return None

    def _extract_certificate_info(self, element, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract certificate information from HTML element"""
        try:
            # Check if it's a link
            href = element.get('href')
            if href:
                # Make URL absolute
                if href.startswith('/'):
                    cert_url = f"https://www.made-in-china.com{href}"
                elif href.startswith('http'):
                    cert_url = href
                else:
                    cert_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                
                # Get certificate name from link text or alt text
                cert_name = element.get_text(strip=True)
                if not cert_name:
                    cert_name = element.get('alt', 'Unknown Certificate')
                
                return {
                    'name': cert_name,
                    'url': cert_url,
                    'type': 'link'
                }
            
            # Check if it's an image
            src = element.get('src')
            if src:
                # Make URL absolute
                if src.startswith('/'):
                    cert_url = f"https://www.made-in-china.com{src}"
                elif src.startswith('http'):
                    cert_url = src
                else:
                    cert_url = f"{base_url.rstrip('/')}/{src.lstrip('/')}"
                
                # Get certificate name from alt text or title
                cert_name = element.get('alt') or element.get('title', 'Unknown Certificate')
                
                return {
                    'name': cert_name,
                    'url': cert_url,
                    'type': 'image'
                }
                
        except Exception as e:
            logger.debug(f"Error extracting certificate info: {e}")
        
        return None

    def _extract_certificate_info_selenium(self, element, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract certificate information from Selenium element"""
        try:
            # Check if it's a link
            href = element.get_attribute('href')
            if href:
                # Make URL absolute
                if href.startswith('/'):
                    cert_url = f"https://www.made-in-china.com{href}"
                elif href.startswith('http'):
                    cert_url = href
                else:
                    cert_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                
                # Get certificate name from link text or alt text
                cert_name = element.text.strip()
                if not cert_name:
                    cert_name = element.get_attribute('alt') or 'Unknown Certificate'
                
                return {
                    'name': cert_name,
                    'url': cert_url,
                    'type': 'link'
                }
            
            # Check if it's an image
            src = element.get_attribute('src')
            if src:
                # Make URL absolute
                if src.startswith('/'):
                    cert_url = f"https://www.made-in-china.com{src}"
                elif src.startswith('http'):
                    cert_url = src
                else:
                    cert_url = f"{base_url.rstrip('/')}/{src.lstrip('/')}"
                
                # Get certificate name from alt text or title
                cert_name = element.get_attribute('alt') or element.get_attribute('title') or 'Unknown Certificate'
                
                return {
                    'name': cert_name,
                    'url': cert_url,
                    'type': 'image'
                }
                
        except Exception as e:
            logger.debug(f"Error extracting certificate info with Selenium: {e}")
        
        return None

    def download_and_analyze_certificate(self, cert_url: str, cert_name: str) -> Dict[str, Any]:
        """Download certificate and analyze for email addresses"""
        logger.info(f"Downloading and analyzing certificate: {cert_name}")
        
        try:
            # Download the certificate
            response = self.session.get(cert_url, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            
            if 'pdf' in content_type.lower():
                return self._analyze_pdf_certificate(response.content, cert_name, cert_url)
            elif 'image' in content_type.lower() or cert_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                return self._analyze_image_certificate(response.content, cert_name, cert_url)
            else:
                # Try to analyze as text
                return self._analyze_text_certificate(response.text, cert_name, cert_url)
                
        except Exception as e:
            logger.error(f"Error downloading certificate {cert_name}: {e}")
            return {
                'name': cert_name,
                'url': cert_url,
                'emails': [],
                'phone_numbers': [],
                'error': str(e)
            }

    def _analyze_pdf_certificate(self, pdf_content: bytes, cert_name: str, cert_url: str) -> Dict[str, Any]:
        """Analyze PDF certificate for email addresses"""
        try:
            # Try to extract text from PDF
            import PyPDF2
            import io
            
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text()
            
            # Extract emails from PDF text
            emails = self._extract_emails_from_text(text_content)
            
            # Extract phone numbers from PDF text
            phone_numbers = self._extract_phone_numbers_from_text(text_content)
            
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'pdf',
                'emails': emails,
                'phone_numbers': phone_numbers,
                'text_preview': text_content[:500] + "..." if len(text_content) > 500 else text_content
            }
            
        except ImportError:
            logger.warning("PyPDF2 not installed, cannot analyze PDF")
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'pdf',
                'emails': [],
                'phone_numbers': [],
                'error': 'PyPDF2 not installed'
            }
        except Exception as e:
            logger.error(f"Error analyzing PDF certificate: {e}")
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'pdf',
                'emails': [],
                'phone_numbers': [],
                'error': str(e)
            }

    def _analyze_image_certificate(self, image_content: bytes, cert_name: str, cert_url: str) -> Dict[str, Any]:
        """Analyze image certificate for email addresses (OCR)"""
        try:
            # Try OCR to extract text from image
            import pytesseract
            from PIL import Image
            import io
            
            image = Image.open(io.BytesIO(image_content))
            
            # Try different OCR configurations for better text extraction
            text_content = ""
            
            # Try default OCR
            try:
                text_content = pytesseract.image_to_string(image)
            except Exception as e:
                logger.debug(f"Default OCR failed: {e}")
            
            # If no text found, try with different configurations
            if not text_content.strip():
                try:
                    # Try with different page segmentation modes
                    text_content = pytesseract.image_to_string(image, config='--psm 6')
                except Exception as e:
                    logger.debug(f"PSM 6 OCR failed: {e}")
            
            if not text_content.strip():
                try:
                    # Try with different OCR engine modes
                    text_content = pytesseract.image_to_string(image, config='--oem 1 --psm 6')
                except Exception as e:
                    logger.debug(f"OEM 1 OCR failed: {e}")
            
            # Extract emails from OCR text
            emails = self._extract_emails_from_text(text_content)
            
            # Also look for phone numbers and other contact info
            phone_numbers = self._extract_phone_numbers_from_text(text_content)
            
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'image',
                'emails': emails,
                'phone_numbers': phone_numbers,
                'text_preview': text_content[:500] + "..." if len(text_content) > 500 else text_content,
                'ocr_success': bool(text_content.strip())
            }
            
        except ImportError:
            logger.warning("pytesseract not installed, cannot analyze image")
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'image',
                'emails': [],
                'phone_numbers': [],
                'error': 'pytesseract not installed'
            }
        except Exception as e:
            logger.error(f"Error analyzing image certificate: {e}")
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'image',
                'emails': [],
                'phone_numbers': [],
                'error': str(e)
            }

    def _extract_phone_numbers_from_text(self, text: str) -> List[str]:
        """Extract phone numbers from text content"""
        phone_numbers = []
        try:
            # Phone number patterns
            phone_patterns = [
                r'\+?[\d\s\-\(\)]{7,15}',  # International format
                r'[\d\s\-\(\)]{7,15}',     # Local format
                r'Tel[:\s]*([\d\s\-\(\)]+)',  # Tel: format
                r'Phone[:\s]*([\d\s\-\(\)]+)',  # Phone: format
                r'[\d]{3,4}[\s\-]?[\d]{3,4}[\s\-]?[\d]{3,4}'  # Common formats
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        phone = match[0]
                    else:
                        phone = match
                    
                    if self._is_valid_phone(phone):
                        phone_numbers.append(phone)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_phones = []
            for phone in phone_numbers:
                if phone not in seen:
                    seen.add(phone)
                    unique_phones.append(phone)
            
            return unique_phones
            
        except Exception as e:
            logger.debug(f"Error extracting phone numbers from text: {e}")
            return []

    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract email addresses from text content"""
        emails = []
        try:
            # Email pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            found_emails = re.findall(email_pattern, text)
            
            for email in found_emails:
                if self._is_valid_email(email):
                    emails.append(email)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_emails = []
            for email in emails:
                if email.lower() not in seen:
                    seen.add(email.lower())
                    unique_emails.append(email)
            
            return unique_emails
            
        except Exception as e:
            logger.debug(f"Error extracting emails from text: {e}")
            return []

    def _analyze_text_certificate(self, text_content: str, cert_name: str, cert_url: str) -> Dict[str, Any]:
        """Analyze text certificate for email addresses"""
        try:
            # Extract emails from text
            emails = self._extract_emails_from_text(text_content)
            
            # Extract phone numbers from text
            phone_numbers = self._extract_phone_numbers_from_text(text_content)
            
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'text',
                'emails': emails,
                'phone_numbers': phone_numbers,
                'text_preview': text_content[:500] + "..." if len(text_content) > 500 else text_content
            }
            
        except Exception as e:
            logger.error(f"Error analyzing text certificate: {e}")
            return {
                'name': cert_name,
                'url': cert_url,
                'type': 'text',
                'emails': [],
                'phone_numbers': [],
                'error': str(e)
            }

