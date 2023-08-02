import requests
import pandas as pd
import logging

import settings
from ymere_scraper import YmereScraper, NotificationType


if __name__ == "__main__":
    """
    Calls on YmereScraper class to scrape rentable houses from Ymere.
    """

    # set logger name
    logging.getLogger(__name__)

    ys = YmereScraper()

    # scrape a JSON object of currently available Ymere houses
    r = requests.post(ys.YMERE_URL, data=ys.YMERE_PAYLOAD)
    logging.info(f'<Status code: {r.status_code}>')
    data = r.json()['result']

    # extract ymere listings from obtained json object
    try:
        new_listings = ys.extract_listings_ymere(data)

        if new_listings:
            logging.info("Houses available found...")
            new_listings = pd.DataFrame(new_listings).set_index('id').sort_values('id')

            try:
                # read df from file
                old_listings = pd.read_csv(ys.YMERE_LISTINGS, index_col="id")

                # clean up old listings
                old_listings = ys.clean_up(old_listings)

                # filter
                new_listings, updated_listings = ys.filter_listings(new_listings, old_listings)

                # write new df to file
                updated_listings.to_csv(ys.YMERE_LISTINGS)

            except Exception as e:
                logging.info("No old listings found. Writing new listings to file.")
                new_listings.to_csv(ys.YMERE_LISTINGS)

            # send email notification if new listings found (not empty)
            if not new_listings.empty:
                logging.info(f"Sending notification via {NotificationType(ys.NOTIFICATION_TYPE).name}.")
                ys.send_notification(new_listings, notification_type=ys.NOTIFICATION_TYPE)
            else:
                logging.debug("No new houses found.")
        else:
            logging.info("No houses found.")

    except Exception as e:
        logging.error(e)
