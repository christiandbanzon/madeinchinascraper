import os
from dotenv import load_dotenv

load_dotenv()

# Base URL
BASE_URL = "https://www.made-in-china.com"

# Search endpoints
SEARCH_URL = f"{BASE_URL}/products-search/hot-china-products"

# Headers to mimic browser requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Selenium settings
SELENIUM_TIMEOUT = 30
SELENIUM_IMPLICIT_WAIT = 10

# Data storage settings
DATA_DIR = "data"
HISTORY_DIR = "history"
LOGS_DIR = "logs"

# Create directories if they don't exist
for directory in [DATA_DIR, HISTORY_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Database settings (if using SQLite)
DATABASE_PATH = os.path.join(DATA_DIR, "made_in_china.db")

# Export settings
EXPORT_FORMATS = ["json", "csv"]

# Rate limiting
REQUEST_DELAY = 2  # seconds between requests
MAX_RETRIES = 3

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

