from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

@dataclass
class ProductImage:
    """Represents a product image"""
    url: str
    alt_text: Optional[str] = None
    caption: Optional[str] = None

@dataclass
class Seller:
    """Represents a seller on Made-in-China"""
    name: str
    profile_url: Optional[str] = None
    profile_picture: Optional[str] = None
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    business_name: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    state_province: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    verified: Optional[bool] = None
    member_since: Optional[str] = None

@dataclass
class ProductListing:
    """Represents a product listing on Made-in-China"""
    # Basic listing info
    title: str
    listing_url: str
    item_number: Optional[str] = None
    sku: Optional[str] = None
    
    # Pricing
    price: Optional[float] = None
    currency: str = "USD"
    min_order_quantity: Optional[int] = None
    max_order_quantity: Optional[int] = None
    
    # Product details
    brand: Optional[str] = None
    units_available: Optional[int] = None
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    
    # Images
    images: List[ProductImage] = None
    
    # Seller info
    seller: Optional[Seller] = None
    
    # Metadata
    scraped_at: datetime = None
    last_updated: Optional[datetime] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.scraped_at is None:
            self.scraped_at = datetime.now()
        if self.specifications is None:
            self.specifications = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['seller'] = asdict(self.seller) if self.seller else None
        data['images'] = [asdict(img) for img in self.images]
        data['scraped_at'] = self.scraped_at.isoformat()
        data['last_updated'] = self.last_updated.isoformat() if self.last_updated else None
        return data

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

@dataclass
class SearchResult:
    """Represents search results for a keyword"""
    keyword: str
    listings: List[ProductListing]
    total_results: int
    search_url: str
    scraped_at: datetime = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'keyword': self.keyword,
            'listings': [listing.to_dict() for listing in self.listings],
            'total_results': self.total_results,
            'search_url': self.search_url,
            'scraped_at': self.scraped_at.isoformat()
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

@dataclass
class HistoryEntry:
    """Represents a history entry for tracking changes"""
    item_number: str
    field_name: str
    old_value: Any
    new_value: Any
    changed_at: datetime = None
    
    def __post_init__(self):
        if self.changed_at is None:
            self.changed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'item_number': self.item_number,
            'field_name': self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_at': self.changed_at.isoformat()
        }



