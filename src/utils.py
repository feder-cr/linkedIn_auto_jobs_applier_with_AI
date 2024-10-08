import logging
import os
import random
import sys
import time

from selenium import webdriver
from loguru import logger
from app_config import MINIMUM_LOG_LEVEL

log_file = "app_log.log"

if MINIMUM_LOG_LEVEL in ["DEBUG", "TRACE", "INFO", "WARNING", "ERROR", "CRITICAL"]:

    logger.remove()

    logger.add(sys.stderr, level=MINIMUM_LOG_LEVEL, format="{time} - {name} - {level} - {message}")

    logger.add(log_file, level=MINIMUM_LOG_LEVEL, format="{time} - {name} - {level} - {message}", encoding='utf-8')
else:

    logger.warning(f"Invalid log level: {MINIMUM_LOG_LEVEL}. Defaulting to DEBUG.")
    logger.remove()
    logger.add(sys.stderr, level="DEBUG", format="{time} - {name} - {level} - {message}")
    logger.add(log_file, level="DEBUG", format="{time} - {name} - {level} - {message}", encoding='utf-8')

logger.disable("urllib3.connectionpool")
logger.disable("selenium.webdriver.remote.remote_connection")


chromeProfilePath = os.path.join(os.getcwd(), "chrome_profile", "linkedin_profile")


def ensure_chrome_profile():
    logger.debug(f"Ensuring Chrome profile exists at path: {chromeProfilePath}")
    profile_dir = os.path.dirname(chromeProfilePath)
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        logger.debug(f"Created directory for Chrome profile: {profile_dir}")
    if not os.path.exists(chromeProfilePath):
        os.makedirs(chromeProfilePath)
        logger.debug(f"Created Chrome profile directory: {chromeProfilePath}")
    return chromeProfilePath


def is_scrollable(element):
    scroll_height = element.get_attribute("scrollHeight")
    client_height = element.get_attribute("clientHeight")
    scrollable = int(scroll_height) > int(client_height)
    logger.debug(f"Element scrollable check: scrollHeight={scroll_height}, clientHeight={client_height}, scrollable={scrollable}")
    return scrollable


def scroll_slow(driver, scrollable_element, start=0, end=3600, step=300, reverse=False):
    logger.debug(f"Starting slow scroll: start={start}, end={end}, step={step}, reverse={reverse}")

    if reverse:
        start, end = end, start
        step = -step

    if step == 0:
        logger.error("Step value cannot be zero.")
        raise ValueError("Step cannot be zero.")

    max_scroll_height = int(scrollable_element.get_attribute("scrollHeight"))
    current_scroll_position = int(float(scrollable_element.get_attribute("scrollTop")))
    logger.debug(f"Max scroll height of the element: {max_scroll_height}")
    logger.debug(f"Current scroll position: {current_scroll_position}")

    if reverse:

        if current_scroll_position < start:
            start = current_scroll_position
        logger.debug(f"Adjusted start position for upward scroll: {start}")
    else:

        if end > max_scroll_height:
            logger.warning(f"End value exceeds the scroll height. Adjusting end to {max_scroll_height}")
            end = max_scroll_height

    script_scroll_to = "arguments[0].scrollTop = arguments[1];"

    try:
        if scrollable_element.is_displayed():
            if not is_scrollable(scrollable_element):
                logger.warning("The element is not scrollable.")
                return

            if (step > 0 and start >= end) or (step < 0 and start <= end):
                logger.warning("No scrolling will occur due to incorrect start/end values.")
                return

            position = start
            previous_position = None  # Tracking the previous position to avoid duplicate scrolls
            while (step > 0 and position < end) or (step < 0 and position > end):
                if position == previous_position:
                    # Avoid re-scrolling to the same position
                    logger.debug(f"Stopping scroll as position hasn't changed: {position}")
                    break

                try:
                    driver.execute_script(script_scroll_to, scrollable_element, position)
                    logger.debug(f"Scrolled to position: {position}")
                except Exception as e:
                    logger.error(f"Error during scrolling: {e}")

                previous_position = position
                position += step

                # Decrease the step but ensure it doesn't reverse direction
                step = max(10, abs(step) - 10) * (-1 if reverse else 1)

                time.sleep(random.uniform(0.6, 1.5))

            # Ensure the final scroll position is correct
            driver.execute_script(script_scroll_to, scrollable_element, end)
            logger.debug(f"Scrolled to final position: {end}")
            time.sleep(0.5)
        else:
            logger.warning("The element is not visible.")
    except Exception as e:
        logger.error(f"Exception occurred during scrolling: {e}")


def chrome_browser_options():
    logger.debug("Setting Chrome browser options")
    ensure_chrome_profile()
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1200x800")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-autofill")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-animations")
    options.add_argument("--disable-cache")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

    prefs = {
        "profile.default_content_setting_values.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    }
    options.add_experimental_option("prefs", prefs)

    if len(chromeProfilePath) > 0:
        initial_path = os.path.dirname(chromeProfilePath)
        profile_dir = os.path.basename(chromeProfilePath)
        options.add_argument('--user-data-dir=' + initial_path)
        options.add_argument("--profile-directory=" + profile_dir)
        logger.debug(f"Using Chrome profile directory: {chromeProfilePath}")
    else:
        options.add_argument("--incognito")
        logger.debug("Using Chrome in incognito mode")

    return options


def printred(text):
    red = "\033[91m"
    reset = "\033[0m"
    logger.debug("Printing text in red: %s", text)
    print(f"{red}{text}{reset}")


def printyellow(text):
    yellow = "\033[93m"
    reset = "\033[0m"
    logger.debug("Printing text in yellow: %s", text)
    print(f"{yellow}{text}{reset}")


def stringWidth(text, font, font_size):
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]
