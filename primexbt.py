"""
fill_google_form.py

Fills a Google Form with a fixed set of answers, N times in a row.
N and the answers are configurable by the user.

Usage:
    python fill_google_form.py --times 5
    python fill_google_form.py            # will prompt for the count

Requirements:
    pip install selenium
    A matching chromedriver must be on PATH (or use webdriver-manager, see note below).
"""

import argparse
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLScqWxj8OTBWpf3aJGV5frfPrZ0W3vINkPKcbt1_XdHAcyPE3w/viewform"
)

# Map: a substring of the question's visible label -> the answer to type in.
# Matching is case-insensitive substring matching, so partial labels are fine.
# All three set to the same value so you can confirm every column is landing
# correctly in your DB/Excel export.
FIELD_VALUES = {
    "Your name": "Madhuri Kumari",
    "Prime XBT UID": "2608577",
    "Prime XBT USDT BEP-20 Wallet Address": "0x10930AeBB57E853714ab7A7cEaa3d2a566F98Fd1",
}


def set_field_value(driver, element, value):
    """
    Set an input/textarea's value via JS instead of .clear()/.send_keys().

    Google Forms lazy-renders question blocks, which can leave an element
    technically present in the DOM but not yet interactable, causing
    Selenium's InvalidElementStateException. Setting the value through the
    native property setter and dispatching input/change events sidesteps
    that, while still updating Google Forms' internal form state correctly.
    """
    proto = "HTMLTextAreaElement" if element.tag_name.lower() == "textarea" else "HTMLInputElement"
    driver.execute_script(
        f"""
        const el = arguments[0];
        const value = arguments[1];
        el.scrollIntoView({{block: 'center'}});
        const setter = Object.getOwnPropertyDescriptor(window.{proto}.prototype, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """,
        element,
        value,
    )


def fill_form_once(driver, field_values, wait_seconds=15):
    """Load a fresh copy of the form, fill it in, and submit it."""
    driver.get(FORM_URL)
    wait = WebDriverWait(driver, wait_seconds)

    # Wait until the questions have rendered.
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']")))
    questions = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")

    for question in questions:
        try:
            title = question.find_element(By.CSS_SELECTOR, "div[role='heading']").text.strip()
        except Exception:
            continue

        value = next(
            (val for key, val in field_values.items() if key.lower() in title.lower()),
            None,
        )
        if value is None:
            continue  # question we don't have an answer configured for

        try:
            input_el = question.find_element(By.CSS_SELECTOR, "input[type='text']")
        except Exception:
            try:
                input_el = question.find_element(By.CSS_SELECTOR, "textarea")
            except Exception:
                continue  # not a plain text question, skip

        set_field_value(driver, input_el, value)

    submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Submit']")))
    submit_btn.click()

    # Confirm the submission actually went through before moving on.
    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'recorded') or contains(text(),'another response')]")
        )
    )


def main():
    parser = argparse.ArgumentParser(description="Submit a Google Form N times.")
    parser.add_argument("--times", type=int, default=None, help="Number of submissions to make")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to wait between submissions")
    args = parser.parse_args()

    times = args.times
    if times is None:
        times = int(input("How many times should the form be submitted? ").strip())

    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")  # uncomment to run without opening a visible window
    driver = webdriver.Chrome(options=options)

    try:
        for i in range(times):
            print(f"Submitting response {i + 1}/{times}...")
            fill_form_once(driver, FIELD_VALUES)
            time.sleep(args.delay)
    finally:
        driver.quit()

    print(f"Done — submitted {times} response(s).")


if __name__ == "__main__":
    main()
