import asyncio
import random
import logging
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
try:
    from src.funda_scraper_wrapper import preprocess
except ImportError:
    from funda_scraper_wrapper import preprocess

class PlaywrightFundaScraper:
    def __init__(self, area="amsterdam", want_to="rent", n_pages=1, min_price=None, max_price=None):
        self.area = area
        self.want_to = want_to  # "rent" or "buy"
        self.n_pages = n_pages
        self.min_price = min_price
        self.max_price = max_price
        self.base_url = "https://www.funda.nl"
        self.results = []
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def _init_browser(self, playwright):
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/"
            }
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        return browser, page

    def _build_url(self, page_num=1):
        type_path = "huur" if self.want_to == "rent" else "koop"
        url = f"{self.base_url}/en/zoeken/{type_path}/?selected_area=%5B%22{self.area}%22%5D"
        
        if self.min_price:
            url += f"&price=%22{self.min_price}-"
            if self.max_price:
                url += f"{self.max_price}%22"
            else:
                url += "+%22"
        elif self.max_price:
            url += f"&price=%22-{self.max_price}%22"
            
        if page_num > 1:
            url += f"&search_result={page_num}"
        return url

    async def scrape(self):
        async with async_playwright() as playwright:
            browser, page = await self._init_browser(playwright)
            try:
                # 1. Start at homepage to build cookies/session
                self.logger.info("Starting at homepage...")
                await page.goto(self.base_url, wait_until="networkidle")
                await asyncio.sleep(random.uniform(2, 4))
                
                # Accept cookies if the button appears
                try:
                    cookie_button = await page.query_selector('button:has-text("Accept"), button:has-text("Accepteren")')
                    if cookie_button:
                        await cookie_button.click()
                        await asyncio.sleep(random.uniform(1, 2))
                except:
                    pass

                for p in range(1, self.n_pages + 1):
                    url = self._build_url(p)
                    self.logger.info(f"Scraping page {p}: {url}")
                    
                    # Navigate to search page
                    await page.goto(url, wait_until="networkidle")
                    await asyncio.sleep(random.uniform(2, 4))

                    # Wait for results
                    try:
                        await page.wait_for_selector('[data-testid="listingDetailsAddress"]', timeout=15000)
                    except:
                        self.logger.warning(f"No results found on page {p} or timeout.")
                        await page.screenshot(path=f"debug_page_{p}.png")
                        if "captcha" in (await page.title()).lower() or "bijna op de pagina" in (await page.content()).lower():
                            self.logger.error("Blocked by BOT DETECTION PAGE")
                        break

                    address_elements = await page.query_selector_all('[data-testid="listingDetailsAddress"]')
                    self.logger.info(f"Found {len(address_elements)} addresses on page {p}")

                    for address_el in address_elements:
                        data = await self._extract_listing_data(address_el)
                        if data:
                            self.results.append(data)
                    
                    # Random delay between pages
                    await asyncio.sleep(random.uniform(3, 7))
                    
            finally:
                await browser.close()
        
        return pd.DataFrame(self.results)

    async def _extract_listing_data(self, address_el):
        try:
            # Address & URL
            address = await address_el.inner_text()
            url = await address_el.get_attribute("href")
            if url and not url.startswith("http"):
                url = self.base_url + url

            # Find the card container (going up from address)
            # We'll look for a container that has the price
            card = address_el
            price_el = None
            for _ in range(10): # Look up to 10 levels
                card = await card.get_property("parentElement")
                card = card.as_element()
                if not card: break
                price_el = await card.query_selector('[data-testid="price-rent"], [data-testid="price-sale"]')
                if price_el: break
            
            if not price_el:
                # Fallback: Price might be a sibling or in another branch of the same card
                # Let's try to find a container that has both
                pass

            price_raw = await price_el.inner_text() if price_el else "na"
            price = preprocess.clean_price(price_raw)

            # Specs (Area, Rooms, Energy Label)
            area = 0
            rooms = 0
            energy_label = "na"

            if card:
                specs = await card.query_selector_all('li.flex.items-center')
                for spec in specs:
                    text = (await spec.inner_text()).strip()
                    if "m²" in text:
                        area_val = "".join(filter(str.isdigit, text))
                        area = int(area_val) if area_val else 0
                    elif text.isdigit():
                        rooms = int(text)
                    elif len(text) <= 5 and any(c.isalpha() for c in text):
                         energy_label = preprocess.clean_energy_label(text)

            return {
                "address": address.strip(),
                "price": price,
                "area": area,
                "rooms": rooms,
                "energy_label": energy_label,
                "url": url,
                "scraped_at": pd.Timestamp.now()
            }
        except Exception as e:
            self.logger.error(f"Error extracting listing data: {e}")
            return None

if __name__ == "__main__":
    # Quick test run
    scraper = PlaywrightFundaScraper(area="amsterdam", n_pages=1)
    df = asyncio.run(scraper.scrape())
    print(df.head())
    if not df.empty:
        df.to_csv("funda_test_results.csv", index=False)
        print(f"Saved {len(df)} results to funda_test_results.csv")
