import os
import logging
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Timezone setting
TIMEZONE_AMS = timezone('Europe/Amsterdam')

YMERE_URL = "https://aanbod.ymere.nl/portal/publication/frontend/getallobjects/format/json"
YMERE_PAYLOAD = {
    'accept': 'application/json',
    'origin': 'https://aanbod.ymere.nl',
    'referer': 'https://aanbod.ymere.nl/aanbod/huurwoningen/',
    'dwellingTypeCategory': 'woning'
}
HOUSE_LISTINGS = "csv/house_listings.csv"
ALL_HOUSE_LISTINGS = "csv/all_house_listings.csv"

# Configuration from environment variables
AREA_TO_SEARCH = os.getenv("AREA_TO_SEARCH", "rotterdam")
EMAIL_SEND_TO = os.getenv("EMAIL_SEND_TO", "egalea.11@gmail.com")
EMAIL_SEND_FROM = os.getenv("EMAIL_SEND_FROM", "pitirross.life@gmail.com")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
PUSHBULLET_API_KEY = os.getenv("PUSHBULLET_API_KEY")
PUSHBULLET_E2E_ENCRYPTION = os.getenv("PUSHBULLET_E2E_ENCRYPTION")

# logging initialization
log_path = "./logs"
if not os.path.exists(log_path):
    os.makedirs(log_path)
# group logs per month (logrotate set to monthly + compress)
log_filename = f"{log_path}/housing_scraper_{datetime.now(TIMEZONE_AMS).strftime('%Y-%m')}.log"
if log_filename:
    logging.basicConfig(filename=log_filename, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
    logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")
else:

logging.getLogger("urllib3").setLevel(logging.DEBUG)
