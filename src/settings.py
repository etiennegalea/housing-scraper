import os
import logging
from datetime import datetime
from pytz import timezone


# Timezone setting
TIMEZONE_AMS = timezone('Europe/Amsterdam')

YMERE_URL = "https://aanbod.ymere.nl/portal/publication/frontend/getallobjects/format/json"
YMERE_PAYLOAD = {
    'accept': 'application/json',
    'origin': 'https://aanbod.ymere.nl',
    'referer': 'https://aanbod.ymere.nl/aanbod/huurwoningen/',
    'dwellingTypeCategory': 'woning'
}
YMERE_LISTINGS = "csv/ymere_listings.csv"
ALL_HOUSE_LISTINGS = "csv/all_house_listings.csv"

# logging initialization
log_path = "./logs"
if not os.path.exists(log_path):
    os.makedirs(log_path)
# group logs per month (logrotate set to monthly + compress)
log_filename = f"{log_path}/housing_scraper_{datetime.now(TIMEZONE_AMS).strftime('%Y-%m')}.log"
if log_filename:
    logging.basicConfig(filename=log_filename, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
else:
    logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")

logging.getLogger("urllib3").setLevel(logging.DEBUG)
