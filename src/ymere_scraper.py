import pandas as pd
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import yaml
from geopy.geocoders import Nominatim
from pushbullet import Pushbullet
from enum import IntEnum
import logging

import settings
from funda_scraper import FundaScraper, preprocess
from translate import Translator


class NotificationType(IntEnum):
    EMAIL = 1
    PUSH_NOTIFICATION = 2


class HouseScraper():

    # constants
    NOTIFICATION_TYPE = NotificationType.EMAIL.value

    # initialize Nominatim API
    geolocator = Nominatim(user_agent='house_listings')

    try:
        with open("src/.config.yml", 'r') as stream:
            config = yaml.safe_load(stream)
            if config is not None and 'api-keys' in config:
                SENDGRID_API_KEY = config['api-keys'].get('sendgrid')
                PUSHBULLET_API_KEY = config['api-keys'].get('pushbullet')
                if SENDGRID_API_KEY is None or PUSHBULLET_API_KEY is None:
                    raise ValueError("API keys not found in the YAML file.")
            else:
                raise ValueError("Invalid YAML structure or missing 'api-keys' key.")
    except Exception as e:
        print(f"{e}: API KEY is not available.")


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
    def extract_log_datetime(self, log_id:str) -> str:
        """
        Extract log datetime as string from log_id
        """

        log_datetime = datetime.strptime(log_id, '%Y%m-%d%H-%M%S')
        return log_datetime.strftime('%d-%m-%Y %H:%M:%S')

    @classmethod
    def clean_listings(self, df:pd.DataFrame):
        """
        Manually clean listings to extract desired fields.

        Args:
            df: (Pandas.DataFrame)  the scraped house listings
        """

        clean_df = pd.DataFrame()

        # info
        clean_df["house_id"] = df["url"].apply(lambda x: int(x.split("/")[-2].split("-")[1]))
        clean_df["house_type"] = df["url"].apply(lambda x: x.split("/")[-2].split("-")[0])

        # price
        clean_df["price"] = df["price"].apply(preprocess.clean_price)
        clean_df = clean_df[clean_df["price"] != 0]

        # house layout
        clean_df["room"] = df["num_of_rooms"].apply(preprocess.find_n_room)
        clean_df["bedroom"] = df["num_of_rooms"].apply(preprocess.find_n_bedroom)
        clean_df["bathroom"] = df["num_of_bathrooms"].apply(preprocess.find_n_bathroom)
        clean_df["energy_label"] = df["energy_label"].apply(preprocess.clean_energy_label)

        # translations
        # clean_parking = df[df["parking"] != "na"]
        # clean_df["parking"] = clean_parking.apply(translator.translate)

        clean_df["address"] = df["address"]
        clean_df["zip_code"] = df["zip_code"]
        clean_df["year_built"] = df["year"]
        clean_df["url"] = df["url"]

        # time
        clean_df["log_id"] = df["log_id"].apply(self.extract_log_datetime)
        clean_df = clean_df.set_index('house_id').sort_index(ascending=False)

        return clean_df

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
    def clean_up_ymere(self, old_listings):
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
    def extract_listings_funda(self, area:str, want_to:str='rent', n_pages:int=1, raw_listings:bool=True) -> pd.DataFrame:
        """
        Extract listings from Funda scraping library.

        Args:
            area:               (string)    area that you want to search in
            want_to:            (string)    'rent' or 'buy'
            n_pages:            (int)       number of listings to show
            raw_listings:       (bool)      return raw listings scraped or clean them

        Return:
            (pandas.DataFrame) containing the desirable filtered listings from the scraped data.
        """

        scraper = FundaScraper(area="breda", want_to="rent", find_past=False, page_start=1, n_pages=1)
        houses = scraper.run(raw_data=raw_listings)

        return houses

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
        
        dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"Extraction time: {dt_string}")

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

        title = f"[HOUSE LISTINGS | {settings.AREA_TO_SEARCH.upper()}] {len(new_listings)} found!"

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
                        New houses in {settings.AREA_TO_SEARCH.upper()} just dropped!
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
    def send_email(self, content, to_email=settings.EMAIL_SEND_TO):
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
