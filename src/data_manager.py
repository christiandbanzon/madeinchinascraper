import json
import csv
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from loguru import logger

from src.config import DATA_DIR, HISTORY_DIR, DATABASE_PATH, EXPORT_FORMATS
from src.models import ProductListing, SearchResult, HistoryEntry

class DataManager:
    """Manages data storage, history tracking, and exports"""
    
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.history_dir = Path(HISTORY_DIR)
        self.data_dir = Path(DATA_DIR)
        
        # Create directories if they don't exist
        self.history_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create products table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_number TEXT UNIQUE,
                        title TEXT,
                        listing_url TEXT,
                        sku TEXT,
                        price REAL,
                        currency TEXT DEFAULT 'USD',
                        min_order_quantity INTEGER,
                        max_order_quantity INTEGER,
                        description TEXT,
                        specifications TEXT,
                        scraped_at TIMESTAMP,
                        last_updated TIMESTAMP
                    )
                ''')
                
                # Create sellers table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sellers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        profile_url TEXT,
                        profile_picture TEXT,
                        rating REAL,
                        total_reviews INTEGER,
                        business_name TEXT,
                        country TEXT,
                        address TEXT,
                        email TEXT,
                        verified BOOLEAN,
                        member_since TEXT
                    )
                ''')
                
                # Create product_images table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS product_images (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER,
                        url TEXT,
                        alt_text TEXT,
                        caption TEXT,
                        FOREIGN KEY (product_id) REFERENCES products (id)
                    )
                ''')
                
                # Create history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_number TEXT,
                        field_name TEXT,
                        old_value TEXT,
                        new_value TEXT,
                        changed_at TIMESTAMP
                    )
                ''')
                
                # Create search_results table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT,
                        total_results INTEGER,
                        search_url TEXT,
                        scraped_at TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def save_search_result(self, search_result: SearchResult):
        """Save search results to database and files"""
        try:
            # Save to database
            self._save_search_result_to_db(search_result)
            
            # Save to JSON file
            self._save_search_result_to_json(search_result)
            
            # Save to CSV file
            self._save_search_result_to_csv(search_result)
            
            logger.info(f"Saved search results for keyword: {search_result.keyword}")
            
        except Exception as e:
            logger.error(f"Error saving search result: {e}")
    
    def _save_search_result_to_db(self, search_result: SearchResult):
        """Save search result to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Save search result metadata
            cursor.execute('''
                INSERT INTO search_results (keyword, total_results, search_url, scraped_at)
                VALUES (?, ?, ?, ?)
            ''', (
                search_result.keyword,
                search_result.total_results,
                search_result.search_url,
                search_result.scraped_at.isoformat()
            ))
            
            # Save each product listing
            for listing in search_result.listings:
                self._save_product_listing_to_db(listing, cursor)
            
            conn.commit()
    
    def _save_product_listing_to_db(self, listing: ProductListing, cursor):
        """Save a product listing to database"""
        try:
            # Check if product already exists
            cursor.execute('SELECT id FROM products WHERE item_number = ?', (listing.item_number,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing product
                self._update_product_in_db(listing, cursor)
            else:
                # Insert new product
                self._insert_product_to_db(listing, cursor)
                
        except Exception as e:
            logger.error(f"Error saving product listing to database: {e}")
    
    def _insert_product_to_db(self, listing: ProductListing, cursor):
        """Insert new product to database"""
        cursor.execute('''
            INSERT INTO products (
                item_number, title, listing_url, sku, price, currency,
                min_order_quantity, max_order_quantity, description, specifications,
                scraped_at, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing.item_number,
            listing.title,
            listing.listing_url,
            listing.sku,
            listing.price,
            listing.currency,
            listing.min_order_quantity,
            listing.max_order_quantity,
            listing.description,
            json.dumps(listing.specifications) if listing.specifications else None,
            listing.scraped_at.isoformat(),
            listing.last_updated.isoformat() if listing.last_updated else None
        ))
        
        product_id = cursor.lastrowid
        
        # Save images
        for image in listing.images:
            cursor.execute('''
                INSERT INTO product_images (product_id, url, alt_text, caption)
                VALUES (?, ?, ?, ?)
            ''', (product_id, image.url, image.alt_text, image.caption))
    
    def _update_product_in_db(self, listing: ProductListing, cursor):
        """Update existing product in database and track changes"""
        # Get current values
        cursor.execute('''
            SELECT * FROM products WHERE item_number = ?
        ''', (listing.item_number,))
        
        current = cursor.fetchone()
        if not current:
            return
        
        # Compare and track changes
        self._track_changes(listing, current, cursor)
        
        # Update product
        cursor.execute('''
            UPDATE products SET
                title = ?, listing_url = ?, sku = ?, price = ?, currency = ?,
                min_order_quantity = ?, max_order_quantity = ?, description = ?, specifications = ?,
                last_updated = ?
            WHERE item_number = ?
        ''', (
            listing.title,
            listing.listing_url,
            listing.sku,
            listing.price,
            listing.currency,
            listing.min_order_quantity,
            listing.max_order_quantity,
            listing.description,
            json.dumps(listing.specifications) if listing.specifications else None,
            datetime.now().isoformat(),
            listing.item_number
        ))
    
    def _track_changes(self, new_listing: ProductListing, old_data, cursor):
        """Track changes between old and new data"""
        # Align to current products schema: id(0), item_number(1), title(2), listing_url(3), sku(4),
        # price(5), currency(6), min_order_quantity(7), max_order_quantity(8), description(9),
        # specifications(10), scraped_at(11), last_updated(12)
        fields = [
            ('title', 2),
            ('listing_url', 3),
            ('sku', 4),
            ('price', 5),
            ('currency', 6),
            ('min_order_quantity', 7),
            ('max_order_quantity', 8),
            ('description', 9)
        ]
        
        for field_name, index in fields:
            old_value = old_data[index]
            new_value = getattr(new_listing, field_name)
            
            if old_value != new_value:
                cursor.execute('''
                    INSERT INTO history (item_number, field_name, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    new_listing.item_number,
                    field_name,
                    str(old_value) if old_value is not None else None,
                    str(new_value) if new_value is not None else None,
                    datetime.now().isoformat()
                ))
    
    # Removed unused _save_seller_to_db; seller info is not persisted in current schema
    
    def _save_search_result_to_json(self, search_result: SearchResult):
        """Save search result to JSON file in standardized marketplace schema"""
        timestamp = search_result.scraped_at.strftime("%Y%m%d_%H%M%S")
        filename = f"search_{search_result.keyword}_{timestamp}.json"
        filepath = self.data_dir / filename
        
        rows = [self._listing_to_marketplace_row(listing) for listing in search_result.listings]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved JSON file: {filepath}")
    
    def _save_search_result_to_csv(self, search_result: SearchResult):
        """Save search result to CSV file in standardized marketplace schema"""
        timestamp = search_result.scraped_at.strftime("%Y%m%d_%H%M%S")
        filename = f"search_{search_result.keyword}_{timestamp}.csv"
        filepath = self.data_dir / filename
        
        # Prepare data for CSV (standardized columns)
        csv_rows = [self._listing_to_marketplace_row(listing) for listing in search_result.listings]
        if csv_rows:
            df = pd.DataFrame(csv_rows)
            # Preserve column order
            columns = [
                'Listing Title','Listing URL','Image URL','All Image URLs','Marketplace',
                'Price','Currency','Shipping','Units Available','Item Number','HS Code','Brand',
                'Seller Name','Seller URL','Seller Business','Seller Address','Seller State/Province','Seller Zip Code','Seller Profile Picture','Seller Email','Seller Phone'
            ]
            df = df.reindex(columns=columns)
            # Normalize multi-line text fields for portability
            df = df.applymap(lambda v: self._normalize_whitespace(v) if isinstance(v, str) else v)
            df.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"Saved CSV file: {filepath}")

    def _listing_to_marketplace_row(self, listing: 'ProductListing') -> Dict[str, Any]:
        """Map internal listing model to standardized marketplace row schema."""
        image_urls = [img.url for img in getattr(listing, 'images', []) or []]
        primary_image = self._select_primary_image_url(image_urls)
        seller = listing.seller
        seller_address = self._normalize_whitespace(getattr(seller, 'address', None) if seller else None)
        state_province, zip_code = self._extract_address_parts(seller_address) if seller_address else (None, None)
        item_number = listing.item_number
        hs_code = None
        if item_number and self._looks_like_hs_code(item_number):
            hs_code = item_number
            item_number = None
        row: Dict[str, Any] = {
            'Listing Title': listing.title,
            'Listing URL': listing.listing_url,
            'Image URL': primary_image,
            'All Image URLs': '; '.join([u for u in image_urls if u]),
            'Marketplace': 'Made-in-China',
            'Price': listing.price,
            'Currency': listing.currency,
            'Shipping': None,
            'Units Available': getattr(listing, 'units_available', None),
            'Item Number': item_number,
            'HS Code': hs_code,
            'Brand': getattr(listing, 'brand', None),
            'Seller Name': seller.name if seller else None,
            'Seller URL': seller.profile_url if seller else None,
            'Seller Business': getattr(seller, 'business_name', None) if seller else None,
            'Seller Address': seller_address,
            'Seller State/Province': state_province,
            'Seller Zip Code': zip_code,
            'Seller Profile Picture': getattr(seller, 'profile_picture', None) if seller else None,
            'Seller Email': getattr(seller, 'email', None) if seller else None,
            'Seller Phone': getattr(seller, 'phone', None) if seller else None,
        }
        return row

    @staticmethod
    def _normalize_whitespace(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        import re
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _select_primary_image_url(image_urls: List[str]) -> Optional[str]:
        if not image_urls:
            return None
        # Prefer first non-placeholder image
        for url in image_urls:
            if not url:
                continue
            lower = url.lower()
            # Skip known placeholders/icons/svgs
            if (
                'micstatic.com/common/img/space.png' in lower or
                '/icon/' in lower or '/logo/' in lower or '/landing/' in lower or
                lower.endswith('.svg')
            ):
                continue
            # Prefer standard image formats
            if any(lower.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff')):
                return url
            return url
        # Fallback to first
        return image_urls[0]

    @staticmethod
    def _looks_like_hs_code(value: str) -> bool:
        import re
        v = value.strip()
        return bool(re.fullmatch(r"\d{6,12}", v))

    @staticmethod
    def _extract_address_parts(address: str) -> tuple[Optional[str], Optional[str]]:
        """Extract state/province and ZIP/Postal code from a free-form address (best-effort)."""
        if not address:
            return None, None
        import re
        addr = address
        # ZIP: 5-6 digit sequences (CN often 6 digits)
        zip_match = re.search(r"\b\d{5,6}\b", addr)
        zip_code = zip_match.group(0) if zip_match else None
        # Province: look for known Chinese provinces/regions
        provinces = [
            'Guangdong','Zhejiang','Liaoning','Jiangsu','Shandong','Fujian','Beijing','Shanghai','Tianjin',
            'Chongqing','Sichuan','Henan','Hubei','Hunan','Hebei','Anhui','Jiangxi','Shanxi','Shaanxi',
            'Guangxi','Yunnan','Guizhou','Hainan','Gansu','Qinghai','Ningxia','Xinjiang','Inner Mongolia',
            'Tibet','Jilin','Heilongjiang','Hong Kong','Macau','Taiwan'
        ]
        state = None
        for p in provinces:
            if re.search(rf"\b{re.escape(p)}\b", addr, flags=re.IGNORECASE):
                state = p
                break
        return state, zip_code
    
    def get_history(self, item_number: str, field_name: Optional[str] = None) -> List[HistoryEntry]:
        """Get history for a specific item and optionally field"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if field_name:
                    cursor.execute('''
                        SELECT item_number, field_name, old_value, new_value, changed_at
                        FROM history
                        WHERE item_number = ? AND field_name = ?
                        ORDER BY changed_at DESC
                    ''', (item_number, field_name))
                else:
                    cursor.execute('''
                        SELECT item_number, field_name, old_value, new_value, changed_at
                        FROM history
                        WHERE item_number = ?
                        ORDER BY changed_at DESC
                    ''', (item_number,))
                
                rows = cursor.fetchall()
                history = []
                
                for row in rows:
                    history.append(HistoryEntry(
                        item_number=row[0],
                        field_name=row[1],
                        old_value=row[2],
                        new_value=row[3],
                        changed_at=datetime.fromisoformat(row[4])
                    ))
                
                return history
                
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
    
    def export_data(self, keyword: str, format_type: str = "json") -> Optional[str]:
        """Export data for a specific keyword"""
        try:
            if format_type not in EXPORT_FORMATS:
                raise ValueError(f"Unsupported format: {format_type}")
            
            # Get data from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT *
                    FROM products
                    WHERE title LIKE ? OR description LIKE ?
                ''', (f"%{keyword}%", f"%{keyword}%"))
                
                rows = cursor.fetchall()
                
                if not rows:
                    logger.warning(f"No data found for keyword: {keyword}")
                    return None
                
                # Convert to list of dictionaries
                data = []
                for row in rows:
                    data.append({
                        'item_number': row[1],
                        'title': row[2],
                        'listing_url': row[3],
                        'sku': row[4],
                        'price': row[5],
                        'currency': row[6],
                        'min_order_quantity': row[7],
                        'max_order_quantity': row[8],
                        'description': row[9],
                        'specifications': row[10],
                        'scraped_at': row[11],
                        'last_updated': row[12]
                    })
                
                # Export based on format
                if format_type == "json":
                    return self._export_to_json(data, keyword)
                elif format_type == "csv":
                    return self._export_to_csv(data, keyword)
                
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return None
    
    def _export_to_json(self, data: List[Dict], keyword: str) -> str:
        """Export data to JSON format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{keyword}_{timestamp}.json"
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported JSON file: {filepath}")
        return str(filepath)
    
    def _export_to_csv(self, data: List[Dict], keyword: str) -> str:
        """Export data to CSV format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{keyword}_{timestamp}.csv"
        filepath = self.data_dir / filename
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        logger.info(f"Exported CSV file: {filepath}")
        return str(filepath)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get counts
                cursor.execute('SELECT COUNT(*) FROM products')
                total_products = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM sellers')
                total_sellers = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM search_results')
                total_searches = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM history')
                total_changes = cursor.fetchone()[0]
                
                # Get recent activity
                cursor.execute('''
                    SELECT COUNT(*) FROM products 
                    WHERE scraped_at >= datetime('now', '-7 days')
                ''')
                recent_products = cursor.fetchone()[0]
                
                return {
                    'total_products': total_products,
                    'total_sellers': total_sellers,
                    'total_searches': total_searches,
                    'total_changes': total_changes,
                    'recent_products': recent_products
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def get_all_listings(self) -> List[ProductListing]:
        """Get all listings from the database"""
        listings = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all products (seller info is stored directly in products table)
                cursor.execute('''
                    SELECT * FROM products
                ''')
                
                rows = cursor.fetchall()
                
                for row in rows:
                    listing = self._row_to_product_listing_simple(row)
                    if listing:
                        listings.append(listing)
                        
        except Exception as e:
            logger.error(f"Error getting all listings: {e}")
            
        return listings
    
    # def _row_to_product_listing(self, row) -> Optional[ProductListing]:
    #     """Deprecated: old schema with joined seller fields; keeping stub for reference."""
    #     return None
    
    def _row_to_product_listing_simple(self, row) -> Optional[ProductListing]:
        """Convert simple database row to ProductListing object"""
        try:
            from models import Seller, ProductImage
            
            # Create ProductListing object (seller info is not stored in products table)
            listing = ProductListing(
                title=row[2],
                listing_url=row[3],
                item_number=row[1],
                sku=row[4],
                price=row[5],
                currency=row[6],
                min_order_quantity=row[7],
                max_order_quantity=row[8],
                description=row[9],
                seller=None,  # Seller info is not stored in products table
                scraped_at=datetime.fromisoformat(row[11]) if row[11] else None,
                last_updated=datetime.fromisoformat(row[12]) if row[12] else None
            )
            
            return listing
            
        except Exception as e:
            logger.error(f"Error converting row to ProductListing: {e}")
            return None
    
    def update_listing(self, listing: ProductListing):
        """Update a listing in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update product information
                cursor.execute('''
                    UPDATE products 
                    SET title = ?, listing_url = ?, sku = ?, price = ?, currency = ?,
                        min_order_quantity = ?, max_order_quantity = ?, description = ?, last_updated = ?
                    WHERE item_number = ?
                ''', (
                    listing.title, listing.listing_url, listing.sku, listing.price,
                    listing.currency, listing.min_order_quantity, listing.max_order_quantity,
                    listing.description, datetime.now().isoformat(), listing.item_number
                ))
                
                # Update seller information if exists
                if listing.seller:
                    cursor.execute('''
                        UPDATE sellers 
                        SET name = ?, profile_url = ?, profile_picture = ?, rating = ?,
                            total_reviews = ?, business_name = ?, country = ?, address = ?,
                            verified = ?, member_since = ?
                        WHERE id = (SELECT seller_id FROM products WHERE item_number = ?)
                    ''', (
                        listing.seller.name, listing.seller.profile_url,
                        listing.seller.profile_picture, listing.seller.rating,
                        listing.seller.total_reviews, listing.seller.business_name,
                        listing.seller.country, listing.seller.address,
                        listing.seller.verified, listing.seller.member_since,
                        listing.item_number
                    ))
                
                conn.commit()
                logger.info(f"Updated listing: {listing.title}")
                
        except Exception as e:
            logger.error(f"Error updating listing: {e}")

    def save_company_profile(self, profile_data: Dict[str, Any]):
        """Save company profile data to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create company_profiles table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS company_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_name TEXT,
                        contact_person TEXT,
                        email TEXT,
                        phone TEXT,
                        address TEXT,
                        business_type TEXT,
                        year_established TEXT,
                        main_products TEXT,
                        certificates TEXT,
                        profile_url TEXT UNIQUE,
                        scraped_at TIMESTAMP
                    )
                ''')
                
                # Insert or update company profile
                cursor.execute('''
                    INSERT OR REPLACE INTO company_profiles 
                    (company_name, contact_person, email, phone, address, business_type, 
                     year_established, main_products, certificates, profile_url, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    profile_data.get('company_name'),
                    profile_data.get('contact_person'),
                    profile_data.get('email'),
                    profile_data.get('phone'),
                    profile_data.get('address'),
                    profile_data.get('business_type'),
                    profile_data.get('year_established'),
                    profile_data.get('main_products'),
                    ', '.join(profile_data.get('certificates', [])),
                    profile_data.get('profile_url'),
                    profile_data.get('scraped_at')
                ))
                
                conn.commit()
                logger.info(f"Saved company profile: {profile_data.get('company_name', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error saving company profile: {e}")

