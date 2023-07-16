import pandas as pd
import numpy as np
import logging
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import yaml
from geopy.geocoders import Nominatim
from pushbullet import Pushbullet
from enum import IntEnum


class NotificationType(IntEnum):
    EMAIL = 1
    PUSH_NOTIFICATION = 2


class YmereScraper():

    # constants
    YMERE_URL = "https://aanbod.ymere.nl/portal/publication/frontend/getallobjects/format/json"
    YMERE_PAYLOAD = {
        'accept': 'application/json',
        'origin': 'https://aanbod.ymere.nl',
        'referer': 'https://aanbod.ymere.nl/aanbod/huurwoningen/',
        'dwellingTypeCategory': 'woning'
    }
    YMERE_LISTINGS = "./ymere_listings.csv"
    NOTIFICATION_TYPE = NotificationType.PUSH_NOTIFICATION.value

    # initialize Nominatim API
    geolocator = Nominatim(user_agent='house_listings')

    # load sendgrid api key from yaml config file
    try:
        with open("config.yml", 'r') as stream:
            SENDGRID_API_KEY = yaml.safe_load(stream)['api-keys']['sendgrid']
    except Exception as e:
        print(f"{e}: SendGrid API KEY is not available.")
        
    # load pushbullet api key from yaml config file
    try:
        with open("config.yml", 'r') as stream:
            PUSHBULLET_API_KEY = yaml.safe_load(stream)['api-keys']['pushbullet']
    except Exception as e:
        print(f"{e}: PushBullet API KEY is not available.")


    @classmethod
    def fetch_attr(self, attr):
        """
        Fetch an attribute and return an empty string "" if None or does not exists.

        Args:
            attr:       (int|float|string|object) attribute value

        Return:
            attribute value (default type) or None
        """
        
        return attr if not None else ""

    @classmethod
    def getLocation(self, lat, long):
        """
        Get details of a location using lat & long values obtained from the listing.
        The details contain:
            - house number
            - road
            - city
            - postcode

        Args:
            lat:       (string) latitude of house.
            long:      (string) longitude of house.

        Return:
            (dict) accurate attributes about the location of the house.
        """

        try:
            # get exact address from geolocator
            location = self.geolocator.reverse(f"{lat}, {long}").raw['address']
            # keep specific keys only
            location = {x:location[x] for x in ['house_number', 'road', 'city', 'postcode']}

        except Exception as e:
            print("Locator unavailable\n", e)
            return None

        return location

    @classmethod
    def filter_listings(self, current_listings, old_listings):
        """
        Filter new listings by matching ids in the loaded csv and the scrapred listings ids.

        Args:
            current_listings:   pandas.DateFrame() containing scraped data which might contain new listings.     
            old_listings:       pandas.DateFrame() containing previously saved listings of which they have yet to expire.
        
        Return:
            new_listings:       pandas.DataFrame() containing the filtered listings of which are new.
            updates_listings:   pandas.DataFrame() containing the updated listings including the new ones.
        """
        # filter listings ids which have not been discovered yet
        new_listings_ids = [idx for idx in current_listings.index.to_list() if idx not in old_listings.index.to_list()]
        # select listings by their ids
        new_listings = current_listings.loc[new_listings_ids]
        # add new listings to csv
        updated_listings = pd.concat([old_listings, new_listings], join="inner")

        return new_listings, updated_listings

    @classmethod
    def clean_up(self, old_listings):
        """
        Clean up the old listings by iterating through the dataframe and removing and listings of which `closingDate` has passed.
        i.e.: current date is greater than closing date.

        Args:
            old_listings:       pandas.DateFrame() containing previously saved listings of which they have yet to expire.

        Return:
            pandas.DateFrame() containing previously saved listings which still have yet to expire.
        """

        # get current date (yyyy-mm-dd)
        current_date = datetime.now().date()

        drop_rows = []
        # get closing date for every listing
        for k, v in old_listings.iterrows():
            date = datetime.strptime(v['closingDate'], "%Y-%m-%d").date()

            # if closing date has passed, delete listing
            if current_date > date:
                drop_rows.append(k)

        # drop listings that expired
        return old_listings.drop(drop_rows)

    @classmethod
    def extract_listings_ymere(self, listings):
        """
        Extract housing listings from scraped data. The data is in Dutch but most attributes are numerals or dates.
        This function is hard-coded to extract the data with the following conditions:
            - The house is for rent ("huur").
            - The house is NOT for temporary students ("Tijdelijke verhuur studenten").
            - The house is located in the city of "Amsterdam".
            - The house has a rent which is affordable, meaning that the rent per month is lower than x times my gross income (where x is sensitive data).

        Args:
            listings:       (list) of scraped Ymere data containing all the housing listings, including social houses and houses for sale.

        Return:
            (dict) containing the desirable filtered listings from the scraped data.
        """
        
        dt_string = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")

        houses = []
        for house in listings:
            house_dict = {}
            
            # conditions
            to_rent = house['dwellings'][0]['rentBuy'] == 'Huur'
            action_label = house['actionLabel'][0]['label'] != 'Tijdelijke verhuur studenten'
            amsterdam = 'amsterdam' in house['city'][0]['name'].lower()
            affordable = False
            # if house rent exists and is affordable set to True, otherwise skip iteration
            if house['totalRent']:
                affordable = house['totalRent'][0] <= 1250
            else:
                continue

            if to_rent and action_label and amsterdam and affordable:
                ### extract and parse attributes ###
                house_dict['city'] = house['city'][0]['name']
                house_dict['id'] = house['id']
                house_dict['totalRent'] = self.fetch_attr(house['totalRent'][0])
                house_dict['actionLabel'] = self.fetch_attr(house['actionLabel'][0]['label'])
                house_dict['floor'] = self.fetch_attr(house['floor'][0]['name'][:2])
                house_dict['neighborhood'] = self.fetch_attr(house['neighborhood'][0]['name'])
                # improve accuracy of location
                location = self.getLocation(house['latitude'][0], house['longitude'][0])
                if location:
                    house_dict.update(location)
                house_dict['publicationDate'] = datetime.strptime(house['publicationDate'], '%Y-%m-%d %H:%M:%S').date()
                house_dict['closingDate'] = datetime.strptime(house['closingDate'], '%Y-%m-%d %H:%M:%S').date()
                house_dict['dateAdded'] = dt_string
                house_dict['url'] = f"https://aanbod.ymere.nl/aanbod/huurwoningen/details/?publicationID={house_dict['id']}"
                houses.append(house_dict)
        
        return houses

    @classmethod
    def build_content(self, new_listings, notification_type):
        """
        Build the title and body for the email / notification message dynamically.

        Args:
            new_listings:           (pandas.DataFrame) containing the new listings found.
            notification_type:      (IntEnum) email / push notification.

        Return:
            (tuple) containing title (string) and body (string) of listing information
        """

        title = f"[Ymere listing] {len(new_listings)} found!"

        if notification_type == NotificationType.EMAIL.value:
            body = f"""
            <html>
                <head>
                    <style> 
                    table, th, td {{font-size:10pt; border:1px solid black; border-collapse:collapse; text-align:left;}}
                    th, td {{padding: 5px;}}
                    </style>
                </head>
                <body>
                    <p>
                        Log in and react to ymere listings 
                        <a href="https://aanbod.ymere.nl/mijn-omgeving/inloggen/">
                            <b>here</b>
                        </a>
                    </p>
                    <br>
                    {new_listings.to_html(index=False)}
                </body>
            </html>
            """

        elif notification_type == NotificationType.PUSH_NOTIFICATION.value:
            # iterate throughout all the new listings to build stylized message content
            body = ""
            for i, listing in new_listings.reset_index().iterrows():
                body += f"\r€{listing['totalRent']} | {listing['road']} ({listing['city']})\n{listing['url']}\n"
                if i < len(new_listings)-1:
                    body += "\n"

        return title, body

    @classmethod
    def send_email(self, content, to_email="egalea.11@gmail.com"):
        """
        Send email to address with only the new listings founds.

        Args:
            content:    (tuple) containing the composed subject and html body of the email.
            to_email:   (string) containing the email address to be sent to.

        Return:
            status of email response.
        """

        message = Mail(
            from_email = "pitirross.life@gmail.com",
            to_emails = to_email,
            subject = content[0],
            html_content = content[1]
        )
        try:
            sg = SendGridAPIClient(self.SENDGRID_API_KEY)
            response = sg.send(message)
            logging.info(response.status_code)
            logging.debug(response.body)
            logging.debug(response.headers)
        except Exception as e:
            logging.debug(e.message)

        return response.status_code

    @classmethod
    def send_push_notification(self, content):
        """
        Send push notifications using pushbullet API to all connected devices.

        Args:
            content:    (tuple) containing the composed subject and html body of the email.

        Return:
            status of notification response.
        """

        pb = Pushbullet(self.PUSHBULLET_API_KEY)

        ls_devices = {}
        # send notification to all devices
        for device in pb.devices:
            ls_devices[device] = device.push_note(
                title=content[0],
                body=content[1]
            )

    @classmethod
    def send_notification(self, new_listings, notification_type=NOTIFICATION_TYPE):
        """
        Wrapper to send notification according to notification type.

        Args:
            new_listings:       (pandas.DataFrame) containing the new listings found.
            notification_type:  (IntEnum) email / push notification.

        Return:
            status of notification response.
        """

        content = self.build_content(new_listings, notification_type)
        if notification_type == NotificationType.EMAIL.value:
            status = self.send_email(content)
        else:
            status = self.send_push_notification(content)

        return status
