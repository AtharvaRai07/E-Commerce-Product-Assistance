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
            pass

    def get_top_reviews(self, product_url, count=2):
        """Open product -> open Overall review page -> extract reviews."""

        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            version_main=150,
        )

        if not product_url.startswith("http"):
            driver.quit()
            return "No reviews found"

        try:
            driver.get(product_url)
            time.sleep(4)

            self._close_popup(driver)

            # Scroll a little so review section loads
            for _ in range(3):
                driver.execute_script("window.scrollBy(0,700);")
                time.sleep(1)

            review_url = None

            # Find Review Page URL
            links = driver.find_elements(By.TAG_NAME, "a")

            for link in links:
                href = link.get_attribute("href")

                if href and "product-reviews" in href:
                    review_url = href
                    break

            if review_url is None:
                print("Review page link not found")
                return "No reviews found"

            # -------------------------------------------------
            # Remove Flipkart review filters
            # -------------------------------------------------
            parts = urlparse(review_url)
            query = dict(parse_qsl(parts.query))

            pid = query.get("pid")

            clean_query = {}

            if pid:
                clean_query["pid"] = pid

            review_url = urlunparse(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    "",
                    urlencode(clean_query),
                    "",
                )
            )

            print("Opening Clean Review URL:")
            print(review_url)

            driver.get(review_url)
            time.sleep(5)

            self._close_popup(driver)

            # Try clicking Overall tab (if available)
            try:

                overall = WebDriverWait(driver, 8).until(
                    lambda d: d.find_element(
                        By.XPATH,
                        "//*[normalize-space()='Overall']"
                    )
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    overall,
                )

                time.sleep(1)

                driver.execute_script(
                    "arguments[0].click();",
                    overall,
                )

                print("Clicked Overall")

                time.sleep(2)

            except Exception as e:
                print("Overall tab not found:", e)

            return self._extract_reviews_from_current_page(
                driver,
                count=count,
            )

        except Exception as e:
            print("[get_top_reviews]", e)
            return "No reviews found"

        finally:
            driver.quit()

    def _extract_reviews_from_current_page(self, driver, count=2):

        # Load more reviews
        for _ in range(8):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        reviews = []
        seen = set()

        #
        # NEW REVIEW PAGE
        #
        review_blocks = soup.find_all(
            lambda tag:
            tag.name == "div"
            and tag.get_text(strip=True)
            and "Certified Buyer" in tag.get_text()
        )

        print(f"Found {len(review_blocks)} possible review blocks")

        for block in review_blocks:

            text = block.get_text(
                " ",
                strip=True,
            )

            if len(text) < 100:
                continue

            if text in seen:
                continue

            seen.add(text)

            reviews.append(text)

            if len(reviews) >= count:
                break

        #
        # Fallback
        #
        if not reviews:

            texts = soup.stripped_strings

            for t in texts:

                if (
                    len(t) > 80
                    and t not in seen
                ):
                    seen.add(t)
                    reviews.append(t)

                if len(reviews) >= count:
                    break

        return (
            " || ".join(reviews)
            if reviews
            else "No reviews found"
        )

    def _safe_text(self, item, selector, label):
        try:
            return item.find_element(By.CSS_SELECTOR, selector).text.strip()
        except Exception as e:
            print(
                f"  [skip reason] couldn't find '{label}' with selector '{selector}': {type(e).__name__}"
            )
            return None

    def scrape_flipkart_products(self, query, max_products=1, review_count=2):

        options = uc.ChromeOptions()
        driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            version_main=150,
        )

        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(search_url)

        time.sleep(4)
        self._close_popup(driver)
        time.sleep(2)

        products = []

        items = driver.find_elements(
            By.CSS_SELECTOR,
            "div[data-id]"
        )[:max_products]

        print(f"Found {len(items)} candidate item(s) on search page.")

        for idx, item in enumerate(items):

            # UPDATED SELECTORS
            title = self._safe_text(item, "div.RG5Slk", "title")
            price = self._safe_text(item, "div.hZ3P6w.DeU9vF", "price")
            rating = self._safe_text(item, "div.MKiFS6", "rating")
            reviews_text = self._safe_text(item, "span.PvbNMB", "reviews_text")

            if title is None:
                print(
                    f"[item {idx}] raw HTML snippet: "
                    f"{item.get_attribute('outerHTML')[:300]}"
                )
                continue

            rating = rating.replace("★", "").strip() if rating else "N/A"

            reviews_match = re.search(
                r"([\d,]+)\s+Reviews",
                reviews_text or "",
            )

            total_reviews = (
                reviews_match.group(1)
                if reviews_match
                else "N/A"
            )

            try:

                # Product Link
                link_el = item.find_element(
                    By.CSS_SELECTOR,
                    "a.k7wcnx"
                )

                href = link_el.get_attribute("href")

                product_link = (
                    href.split("?")[0]
                    if href.startswith("http")
                    else "https://www.flipkart.com" + href.split("?")[0]
                )

                # Product ID
                product_id = item.get_attribute("data-id") or "N/A"

            except Exception as e:
                print(f"[item {idx}] Product link not found: {e}")
                continue

            print(f"[item {idx}] {title}")
            print(f"Fetching reviews from {product_link}")

            # ------------------------------------
            # Fetch reviews directly
            # ------------------------------------
            try:

                top_reviews = self.get_top_reviews(
                    product_link,
                    count=review_count,
                )

            except Exception as e:

                print(f"[item {idx}] Review extraction failed: {e}")

                top_reviews = "No reviews found"

            products.append(
                [
                    product_id,
                    title,
                    rating,
                    total_reviews,
                    price,
                    top_reviews,
                ]
            )

        driver.quit()

        return products

    def save_to_csv(self, data, filename="product_reviews.csv"):

        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "product_id",
                    "product_title",
                    "rating",
                    "total_reviews",
                    "price",
                    "top_reviews",
                ]
            )
            writer.writerows(data)
