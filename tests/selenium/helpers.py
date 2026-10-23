"""Small Selenium helpers and the shared timeout, used by conftest.py and the specs."""

from __future__ import annotations

import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = int(os.environ.get("SELENIUM_TIMEOUT", "20"))


def wait_for(driver, css: str, timeout: int = TIMEOUT):
    """Return the first visible element matching `css`, or fail after `timeout` seconds."""
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CSS_SELECTOR, css)))


def login(driver, base_url: str, credentials: dict[str, str], timeout: int = TIMEOUT) -> None:
    """Sign in through the real /login form, the way a client would."""
    driver.get(f"{base_url}/login")
    wait_for(driver, 'input[name="email"]', timeout).send_keys(credentials["email"])
    driver.find_element(By.CSS_SELECTOR, 'input[name="password"]').send_keys(credentials["password"])
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    WebDriverWait(driver, timeout).until(EC.url_contains("/dashboard"))
