#!/usr/bin/env python3
"""
Made-in-China.com Scraper
Main application entry point
"""

import argparse
import sys
import time
from typing import List
from loguru import logger
import schedule
import os
import json
import csv
from datetime import datetime

from config import LOG_LEVEL, LOG_FORMAT
from scraper import MadeInChinaScraper
from data_manager import DataManager
from scraper import SearchResult

def setup_logging():
    """Setup logging configuration"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=LOG_FORMAT
    )
    logger.add(
        "logs/made_in_china_scraper.log",
        rotation="1 day",
        retention="30 days",
        level=LOG_LEVEL,
        format=LOG_FORMAT
    )

def search_keywords(keywords: List[str], use_selenium: bool = False, max_pages: int = 5):
    """Search for multiple keywords"""
    scraper = MadeInChinaScraper(use_selenium=use_selenium)
    data_manager = DataManager()
    
    try:
        for keyword in keywords:
            logger.info(f"Starting search for keyword: {keyword}")
            
            # Perform search
            search_result = scraper.search_products(keyword, max_pages)
            
            if search_result.listings:
                logger.info(f"Found {len(search_result.listings)} listings for '{keyword}'")
                
                # Save results
                data_manager.save_search_result(search_result)
                
                # Print summary
                print(f"\n=== Search Results for '{keyword}' ===")
                print(f"Total results: {search_result.total_results}")
                print(f"Listings found: {len(search_result.listings)}")
                
                for i, listing in enumerate(search_result.listings[:5], 1):
                    print(f"{i}. {listing.title}")
                    if listing.price:
                        print(f"   Price: ${listing.price}")
                    if listing.seller:
                        print(f"   Seller: {listing.seller.name}")
                    print()
                
                if len(search_result.listings) > 5:
                    print(f"... and {len(search_result.listings) - 5} more listings")
                
            else:
                logger.warning(f"No listings found for keyword: {keyword}")
                print(f"No listings found for '{keyword}'")
            
            # Add delay between searches
            if keyword != keywords[-1]:  # Don't delay after last keyword
                time.sleep(2)
                
    except Exception as e:
        logger.error(f"Error during search: {e}")
        print(f"Error: {e}")
    finally:
        scraper.close()

def get_product_details(urls: List[str], use_selenium: bool = False):
    """Get detailed information for specific product URLs"""
    scraper = MadeInChinaScraper(use_selenium=use_selenium)
    data_manager = DataManager()
    
    try:
        for url in urls:
            logger.info(f"Getting details for: {url}")
            
            # Get product details
            listing = scraper.get_product_details(url)
            
            if listing:
                print(f"\n=== Product Details ===")
                print(f"Title: {listing.title}")
                print(f"URL: {listing.listing_url}")
                if listing.price:
                    print(f"Price: ${listing.price}")
                if listing.brand:
                    print(f"Brand: {listing.brand}")
                if listing.seller:
                    print(f"Seller: {listing.seller.name}")
                if listing.description:
                    print(f"Description: {listing.description[:200]}...")
                print(f"Images: {len(listing.images)} found")
                
                # Save to database
                search_result = SearchResult(
                    keyword="direct_url",
                    listings=[listing],
                    total_results=1,
                    search_url=url
                )
                data_manager.save_search_result(search_result)
                
            else:
                logger.warning(f"Could not get details for: {url}")
                print(f"Could not get details for: {url}")
            
            # Add delay between requests
            if url != urls[-1]:
                time.sleep(2)
                
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        print(f"Error: {e}")
    finally:
        scraper.close()

def get_company_profile(url: str, use_selenium: bool = False):
    """Get detailed company profile information including contact details"""
    scraper = MadeInChinaScraper(use_selenium=use_selenium)
    data_manager = DataManager()
    
    try:
        logger.info(f"Getting company profile from: {url}")
        
        # Get company profile
        profile_data = scraper.get_company_profile(url)
        
        if profile_data:
            print(f"\n=== Company Profile ===")
            print(f"Company Name: {profile_data.get('company_name', 'N/A')}")
            print(f"Contact Person: {profile_data.get('contact_person', 'N/A')}")
            print(f"Email: {profile_data.get('email', 'N/A')}")
            print(f"Phone: {profile_data.get('phone', 'N/A')}")
            print(f"Address: {profile_data.get('address', 'N/A')}")
            print(f"Business Type: {profile_data.get('business_type', 'N/A')}")
            print(f"Year Established: {profile_data.get('year_established', 'N/A')}")
            print(f"Main Products: {profile_data.get('main_products', 'N/A')}")
            print(f"Certificates: {', '.join(profile_data.get('certificates', []))}")
            print(f"Profile URL: {profile_data.get('profile_url', 'N/A')}")
            
            # Save to database
            data_manager.save_company_profile(profile_data)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_name = profile_data.get('company_name', 'unknown').replace(' ', '_')
            filename = f"company_profile_{company_name}_{timestamp}"
            
            # Save as JSON
            json_path = os.path.join(data_manager.data_dir, f"{filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            
            # Save as CSV
            csv_path = os.path.join(data_manager.data_dir, f"{filename}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Field', 'Value'])
                for key, value in profile_data.items():
                    if key == 'certificates':
                        writer.writerow([key, ', '.join(value) if isinstance(value, list) else value])
                    else:
                        writer.writerow([key, value])
            
            print(f"\nData saved to:")
            print(f"  JSON: {json_path}")
            print(f"  CSV: {csv_path}")
            
        else:
            logger.warning(f"Could not get company profile from: {url}")
            print(f"Could not get company profile from: {url}")
            
    except Exception as e:
        logger.error(f"Error getting company profile: {e}")
        print(f"Error: {e}")
    finally:
        scraper.close()

def export_data(keyword: str, format_type: str = "json"):
    """Export data for a specific keyword"""
    data_manager = DataManager()
    
    try:
        filepath = data_manager.export_data(keyword, format_type)
        
        if filepath:
            print(f"Data exported successfully to: {filepath}")
        else:
            print(f"No data found for keyword: {keyword}")
            
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        print(f"Error: {e}")

def get_history(item_number: str, field_name: str = None):
    """Get history for a specific item"""
    data_manager = DataManager()
    
    try:
        history = data_manager.get_history(item_number, field_name)
        
        if history:
            print(f"\n=== History for Item: {item_number} ===")
            for entry in history:
                print(f"Field: {entry.field_name}")
                print(f"Old Value: {entry.old_value}")
                print(f"New Value: {entry.new_value}")
                print(f"Changed At: {entry.changed_at}")
                print("-" * 50)
        else:
            print(f"No history found for item: {item_number}")
            
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        print(f"Error: {e}")

def get_statistics():
    """Get database statistics"""
    data_manager = DataManager()
    
    try:
        stats = data_manager.get_statistics()
        
        print("\n=== Database Statistics ===")
        print(f"Total Products: {stats.get('total_products', 0)}")
        print(f"Total Sellers: {stats.get('total_sellers', 0)}")
        print(f"Total Searches: {stats.get('total_searches', 0)}")
        print(f"Total Changes: {stats.get('total_changes', 0)}")
        print(f"Recent Products (7 days): {stats.get('recent_products', 0)}")
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        print(f"Error: {e}")

def run_scheduled_search(keywords: List[str], interval_hours: int = 6):
    """Run scheduled searches"""
    def job():
        logger.info("Running scheduled search")
        search_keywords(keywords, use_selenium=False, max_pages=3)
    
    # Schedule the job
    schedule.every(interval_hours).hours.do(job)
    
    print(f"Scheduled search every {interval_hours} hours for keywords: {keywords}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\nStopping scheduled search...")

def analyze_certificates(url: str, use_selenium: bool = False):
    """Extract and analyze certificate PDFs for email addresses"""
    scraper = MadeInChinaScraper(use_selenium=use_selenium)
    data_manager = DataManager()
    
    try:
        logger.info(f"Analyzing certificates from: {url}")
        
        # Extract certificate information
        certificates = scraper.extract_certificate_pdfs(url)
        
        if certificates:
            print(f"\n=== Certificate Analysis ===")
            print(f"Found {len(certificates)} certificates")
            
            all_emails = []
            analyzed_certificates = []
            
            for i, cert in enumerate(certificates, 1):
                print(f"\n{i}. {cert.get('name', 'Unknown')}")
                print(f"   Type: {cert.get('type', 'Unknown')}")
                print(f"   URL: {cert.get('url', 'Not available')}")
                
                # Download and analyze certificate if URL is available
                if cert.get('url'):
                    analysis = scraper.download_and_analyze_certificate(cert['url'], cert['name'])
                    analyzed_certificates.append(analysis)
                    
                    if analysis.get('emails'):
                        print(f"   📧 Emails found: {', '.join(analysis['emails'])}")
                        all_emails.extend(analysis['emails'])
                    elif analysis.get('error'):
                        print(f"   ❌ Error: {analysis['error']}")
                    else:
                        print(f"   📭 No emails found")
                else:
                    print(f"   ⚠️  No URL available for analysis")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"certificate_analysis_{timestamp}"
            
            # Save as JSON
            json_path = os.path.join(data_manager.data_dir, f"{filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'company_url': url,
                    'certificates': analyzed_certificates,
                    'all_emails': list(set(all_emails)),
                    'total_certificates': len(certificates),
                    'total_emails_found': len(set(all_emails)),
                    'scraped_at': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            
            # Save as CSV
            csv_path = os.path.join(data_manager.data_dir, f"{filename}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Certificate Name', 'Type', 'URL', 'Emails Found', 'Error'])
                for cert in analyzed_certificates:
                    emails = ', '.join(cert.get('emails', []))
                    error = cert.get('error', '')
                    writer.writerow([
                        cert.get('name', ''),
                        cert.get('type', ''),
                        cert.get('url', ''),
                        emails,
                        error
                    ])
            
            print(f"\n=== Summary ===")
            print(f"Total certificates analyzed: {len(analyzed_certificates)}")
            print(f"Total emails found: {len(set(all_emails))}")
            if all_emails:
                print(f"Emails: {', '.join(set(all_emails))}")
            
            print(f"\nData saved to:")
            print(f"  JSON: {json_path}")
            print(f"  CSV: {csv_path}")
            
        else:
            logger.warning(f"No certificates found on: {url}")
            print(f"No certificates found on: {url}")
            
    except Exception as e:
        logger.error(f"Error analyzing certificates: {e}")
        print(f"Error: {e}")
    finally:
        scraper.close()

def main():
    """Main application entry point"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Made-in-China.com Scraper")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search for products")
    search_parser.add_argument("keywords", nargs="+", help="Keywords to search for")
    search_parser.add_argument("--selenium", action="store_true", help="Use Selenium for scraping")
    search_parser.add_argument("--max-pages", type=int, default=5, help="Maximum pages to scrape")
    
    # Product details command
    details_parser = subparsers.add_parser("details", help="Get product details")
    details_parser.add_argument("urls", nargs="+", help="Product URLs to get details for")
    details_parser.add_argument("--selenium", action="store_true", help="Use Selenium for scraping")
    
    # Company profile command
    profile_parser = subparsers.add_parser("profile", help="Get company profile and contact information")
    profile_parser.add_argument("url", help="Company profile URL to get details for")
    profile_parser.add_argument("--selenium", action="store_true", help="Use Selenium for scraping")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("keyword", help="Keyword to export data for")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    
    # History command
    history_parser = subparsers.add_parser("history", help="Get item history")
    history_parser.add_argument("item_number", help="Item number to get history for")
    history_parser.add_argument("--field", help="Specific field to get history for")
    
    # Statistics command
    stats_parser = subparsers.add_parser("stats", help="Get database statistics")
    
    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Run scheduled searches")
    schedule_parser.add_argument("keywords", nargs="+", help="Keywords to search for")
    schedule_parser.add_argument("--interval", type=int, default=6, help="Interval in hours")
    
    # Certificate analysis command
    cert_analysis_parser = subparsers.add_parser("analyze_certs", help="Analyze certificate PDFs for email addresses")
    cert_analysis_parser.add_argument("url", help="Company profile URL to analyze certificates for")
    cert_analysis_parser.add_argument("--selenium", action="store_true", help="Use Selenium for scraping")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "search":
            search_keywords(args.keywords, args.selenium, args.max_pages)
        elif args.command == "details":
            get_product_details(args.urls, args.selenium)
        elif args.command == "profile":
            get_company_profile(args.url, args.selenium)
        elif args.command == "export":
            export_data(args.keyword, args.format)
        elif args.command == "history":
            get_history(args.item_number, args.field)
        elif args.command == "stats":
            get_statistics()
        elif args.command == "schedule":
            run_scheduled_search(args.keywords, args.interval)
        elif args.command == "analyze_certs":
            analyze_certificates(args.url, args.selenium)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()







