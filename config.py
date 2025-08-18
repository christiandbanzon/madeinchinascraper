import os
from dotenv import load_dotenv

# Load variables from a .env file when present. In Docker, compose provides envs.
load_dotenv()

# Base URL
BASE_URL = "https://www.made-in-china.com"

# Search endpoints
SEARCH_URL = f"{BASE_URL}/products-search/hot-china-products"

# Headers to mimic browser requests
HEADERS = {
    'User-Agent': os.getenv(
        'HTTP_USER_AGENT',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': os.getenv('HTTP_ACCEPT_LANGUAGE', 'en-US,en;q=0.5'),
    'Accept-Encoding': os.getenv('HTTP_ACCEPT_ENCODING', 'gzip, deflate'),
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Selenium settings (overridable via env)
SELENIUM_TIMEOUT = int(os.getenv("SELENIUM_TIMEOUT", "30"))
SELENIUM_IMPLICIT_WAIT = int(os.getenv("SELENIUM_IMPLICIT_WAIT", "10"))

# Data storage settings (overridable via env)
DATA_DIR = os.getenv("DATA_DIR", "data")
HISTORY_DIR = os.getenv("HISTORY_DIR", "history")
LOGS_DIR = os.getenv("LOGS_DIR", "logs")

# Ensure directories exist at runtime
for directory in [DATA_DIR, HISTORY_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Database settings (if using SQLite)
DATABASE_PATH = os.path.join(DATA_DIR, os.getenv("DATABASE_FILENAME", "made_in_china.db"))

# Export settings
EXPORT_FORMATS = ["json", "csv"]

# Rate limiting (overridable via env)
REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging (overridable via env)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

