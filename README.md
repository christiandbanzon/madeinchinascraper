# Made-in-China.com Scraper

## Project structure

```
.
├─ src/                 # application code
│  ├─ app.py            # CLI implementation
│  ├─ config.py         # settings (env-driven)
│  ├─ data_manager.py   # storage, exports, DB
│  ├─ models.py         # dataclasses
│  ├─ pdf_extractor.py  # PDF/image email extraction (OCR)
│  └─ scraper.py        # scraper logic
├─ cli/
│  └─ main.py           # entrypoint: python -m cli.main
├─ scripts/             # utility scripts
├─ docs/                # docs and deployment notes
├─ examples/            # example HTML and artifacts
├─ docker-compose.yml   # runs the service
├─ Dockerfile           # container image
├─ .env.example         # sample env
└─ .gitignore           # ignores data/, logs/, history/
```

## Quick start

Local:
```bash
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python -m cli.main --help
python -m cli.main search "nike shoes" --max-pages 1
```

Docker:
```bash
cp .env.example .env
docker compose up --build
```

Common commands:
```bash
python -m cli.main analyze_certs "<seller_profile_url>" --selenium
python -m cli.main export "keyword" --format csv
```
A comprehensive web scraping solution for extracting product and seller data from Made-in-China.com. This system is designed to handle keyword-based searches, track historical changes, and export data in multiple formats.

## Features

- **Keyword-based Product Search**: Search for products using keywords
- **Detailed Product Information**: Extract comprehensive product details including images, pricing, and specifications
- **Seller Information**: Capture seller details including ratings, contact information, and business details
- **Historical Tracking**: Maintain a complete history of changes for all data fields
- **Multiple Export Formats**: Export data in JSON and CSV formats
- **Scheduled Scraping**: Run automated searches at specified intervals
- **Database Storage**: SQLite database for persistent data storage
- **Dual Scraping Methods**: Support for both requests-based and Selenium-based scraping

## Data Fields Captured

### Product Listings
- Listing Title
- Product Images
- Product SKU
- Item Number
- Price
- Currency
- Units Available
- Brand
- Listing URL
- Full Product Description
- Minimum/Maximum Order Quantities

### Seller Information
- Seller Name
- Seller Profile Picture
- Seller Profile URL
- Seller Rating
- Total Reviews
- Email Address
- Business/Legal Name
- Country
- State/Province
- Zip Code
- Phone Number
- Address

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd made-in-china-scraper
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install Chrome WebDriver** (for Selenium functionality):
The system will automatically download and manage Chrome WebDriver using `webdriver-manager`.

## Usage

### Basic Search
Search for products using keywords:

```bash
python main.py search "instyler" "instyler rotating iron" "instyler hair dryer"
```

### Advanced Search Options
```bash
# Use Selenium for JavaScript-heavy pages
python main.py search "instyler" --selenium

# Limit the number of pages to scrape
python main.py search "instyler" --max-pages 10
```

### Get Product Details
Extract detailed information from specific product URLs:

```bash
python main.py details "https://www.made-in-china.com/product-url-1" "https://www.made-in-china.com/product-url-2"
```

### Export Data
Export data for a specific keyword:

```bash
# Export as JSON
python main.py export "instyler" --format json

# Export as CSV
python main.py export "instyler" --format csv
```

### View History
Check the change history for a specific item:

```bash
# Get all history for an item
python main.py history "ITEM123456"

# Get history for a specific field
python main.py history "ITEM123456" --field price
```

### Database Statistics
View database statistics:

```bash
python main.py stats
```

### Scheduled Scraping
Run automated searches at regular intervals:

```bash
# Run searches every 6 hours
python main.py schedule "instyler" "instyler rotating iron" --interval 6
```

## Configuration

The system can be configured through the `config.py` file:

- **Request Delays**: Adjust the delay between requests to avoid rate limiting
- **Selenium Settings**: Configure timeout and wait times
- **Export Formats**: Specify supported export formats
- **Database Path**: Set the SQLite database location
- **Logging**: Configure log levels and formats

## Data Storage

### Database Structure
The system uses SQLite with the following tables:

- **products**: Product listings and details
- **sellers**: Seller information
- **product_images**: Product image URLs and metadata
- **history**: Change tracking for all fields
- **search_results**: Search metadata and results

### File Storage
- **JSON Files**: Search results saved as timestamped JSON files
- **CSV Files**: Search results saved as timestamped CSV files
- **Log Files**: Application logs with rotation and retention

## Example Keywords

For the Instyler brand, you can use these keywords:
- instyler
- instyler rotating iron
- instyler hair dryer
- instyler styling iron
- instyler styling brush
- instyler dryer
- instyler accessories
- instyler 7x
- instyler straightener

## Output Formats

### JSON Format
```json
{
  "keyword": "instyler",
  "listings": [
    {
      "title": "Professional Instyler Rotating Iron",
      "listing_url": "https://www.made-in-china.com/product-url",
      "item_number": "ITEM123456",
      "price": 29.99,
      "currency": "USD",
      "brand": "Instyler",
      "seller": {
        "name": "ABC Trading Co.",
        "rating": 4.5,
        "total_reviews": 150
      },
      "images": [
        {
          "url": "https://example.com/image1.jpg",
          "alt_text": "Instyler Rotating Iron"
        }
      ],
      "scraped_at": "2024-01-15T10:30:00"
    }
  ],
  "total_results": 150,
  "scraped_at": "2024-01-15T10:30:00"
}
```

### CSV Format
The CSV export includes all product and seller fields in a flat structure suitable for spreadsheet analysis.

## Historical Tracking

The system automatically tracks changes to all data fields:

- **Price Changes**: Monitor price fluctuations over time
- **Inventory Updates**: Track availability changes
- **Seller Information**: Monitor seller rating and review changes
- **Product Details**: Track title, description, and specification updates

## Rate Limiting and Ethics

- **Respectful Scraping**: Built-in delays between requests
- **User-Agent Rotation**: Random user agents to avoid detection
- **Error Handling**: Graceful handling of network issues and blocked requests
- **Logging**: Comprehensive logging for monitoring and debugging

## Troubleshooting

### Common Issues

1. **No Results Found**: 
   - Check if the website structure has changed
   - Try using Selenium mode: `--selenium`
   - Verify the keyword spelling

2. **Selenium Issues**:
   - Ensure Chrome is installed
   - Check internet connection
   - Try increasing timeout values in config.py

3. **Database Errors**:
   - Check file permissions for the data directory
   - Verify SQLite is working properly

### Debug Mode
Enable detailed logging by modifying `LOG_LEVEL` in `config.py`:
```python
LOG_LEVEL = "DEBUG"
```

## Future Enhancements

- **Multi-region Support**: Support for different Made-in-China regional sites
- **API Integration**: Direct API access if available
- **Advanced Filtering**: Category and price range filtering
- **Real-time Monitoring**: Web interface for monitoring scraping progress
- **Data Visualization**: Charts and graphs for trend analysis

## Legal Considerations

- **Terms of Service**: Ensure compliance with Made-in-China.com's terms of service
- **Rate Limiting**: Respect the website's rate limiting policies
- **Data Usage**: Use scraped data responsibly and in accordance with applicable laws
- **Attribution**: Provide proper attribution when using scraped data

## Support

For issues and questions:
1. Check the logs in the `logs/` directory
2. Review the troubleshooting section
3. Check the database for data integrity
4. Verify network connectivity and website accessibility

## License

This project is for educational and research purposes. Please ensure compliance with all applicable laws and website terms of service.







