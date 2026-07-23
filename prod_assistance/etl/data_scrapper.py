import csv
import time
import re
import os
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait


class FlipkartScraper:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _close_popup(self, driver):
        try:
            driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
            time.sleep(1)
        except Exception:
            pass  # no popup present, that's fine

    def get_top_reviews(self, product_url, count=2):
        """Get the top reviews for a product by visiting its page directly."""
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=150)

        if not product_url.startswith("http"):
            driver.quit()  # was missing before -> leaked a Chrome process on every invalid URL
            return "No reviews found"

        try:
            driver.get(product_url)
            time.sleep(4)
            self._close_popup(driver)
            reviews = self._extract_reviews_from_current_page(driver, count=count)
        except Exception as e:
            print(f"[get_top_reviews] Error: {e}")
            reviews = "No reviews found"
        finally:
            driver.quit()
        return reviews

    def _extract_reviews_from_current_page(self, driver, count=2):
        for _ in range(4):
            ActionChains(driver).send_keys(Keys.END).perform()
            time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        review_blocks = soup.select("div._27M-vq, div.col.EPCmJX, div._6K-7Co")
        seen = set()
        reviews = []

        for block in review_blocks:
            text = block.get_text(separator=" ", strip=True)
            if text and text not in seen:
                reviews.append(text)
                seen.add(text)
            if len(reviews) >= count:
                break

        if not reviews:
            print("  [_extract_reviews] no review blocks matched the current selectors "
                  "-> Flipkart's review-card classes may have changed too")
        return " || ".join(reviews) if reviews else "No reviews found"

    def _safe_text(self, item, selector, label):
        """Extract text from a sub-element, logging exactly which selector failed
        instead of silently swallowing it inside one big try/except."""
        try:
            return item.find_element(By.CSS_SELECTOR, selector).text.strip()
        except Exception as e:
            print(f"  [skip reason] couldn't find '{label}' with selector '{selector}': {type(e).__name__}")
            return None

    def scrape_flipkart_products(self, query, max_products=1, review_count=2):
        """Scrape Flipkart products based on a search query."""
        options = uc.ChromeOptions()
        driver = uc.Chrome(options=options, use_subprocess=True, version_main=150)
        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(4)
        self._close_popup(driver)
        time.sleep(2)

        products = []
        items = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")[:max_products]
        print(f"Found {len(items)} candidate item(s) on search page.")

        for idx, item in enumerate(items):
            title = self._safe_text(item, "div.KzDlHZ", "title")
            price = self._safe_text(item, "div.Nx9bqj", "price")
            rating = self._safe_text(item, "div.XQDdHH", "rating")
            reviews_text = self._safe_text(item, "span.Wphh3N", "reviews_text")

            if title is None:
                # This is almost certainly why "nothing" comes back: the selector is stale.
                # Print the card's raw HTML so you can find the *current* class names.
                print(f"  [item {idx}] raw HTML snippet: {item.get_attribute('outerHTML')[:300]}")
                continue

            match = re.search(r"\d+(,\d+)?(?=\s+Reviews)", reviews_text or "")
            total_reviews = match.group(0) if match else "N/A"

            try:
                link_el = item.find_element(By.CSS_SELECTOR, "a[href*='/p/']")
                href = link_el.get_attribute("href")
                product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                m = re.findall(r"/p/(itm[0-9A-Za-z]+)", href)
                product_id = m[0] if m else "N/A"
            except Exception as e:
                print(f"  [item {idx}] no product link found: {e}")
                continue

            top_reviews = "No reviews found"
            try:
                before_url = driver.current_url
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_el)
                time.sleep(0.5)
                # JS click sidesteps ElementClickIntercepted from overlays/sticky headers,
                # which is a common reason a plain .click() silently fails and falls
                # straight into the except block below.
                driver.execute_script("arguments[0].click();", link_el)

                WebDriverWait(driver, 10).until(lambda d: d.current_url != before_url)
                time.sleep(2)
                self._close_popup(driver)

                print(f"  [item {idx}] navigated to: {driver.current_url}")
                top_reviews = self._extract_reviews_from_current_page(driver, count=review_count)
                driver.back()
                time.sleep(3)
            except Exception as e:
                print(f"  [item {idx}] click-through failed ({e}), falling back to direct URL fetch")
                top_reviews = (
                    self.get_top_reviews(product_link, count=review_count)
                    if "flipkart.com" in product_link
                    else "Invalid product URL"
                )

            products.append([product_id, title, rating, total_reviews, price, top_reviews])

        driver.quit()
        return products

    def save_to_csv(self, data, filename="product_reviews.csv"):
        """Save the scraped product reviews to a CSV file."""
        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "product_title", "rating", "total_reviews", "price", "top_reviews"])
            writer.writerows(data)
