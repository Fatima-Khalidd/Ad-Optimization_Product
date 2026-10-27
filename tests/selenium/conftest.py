"""Fixture wiring for the CSC418 Selenium suite.

The suite runs inside a container, so both the address under test and the Selenium hub come from
environment variables instead of a hardcoded localhost. That is what lets the same image be pointed
at the instance on port 3000 and at the AWS load balancer on port 80 without editing the test.
"""

from __future__ import annotations

import os
import time

import pytest
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

APP_URL = os.environ.get("APP_URL", "http://frontend:3000").rstrip("/")
SELENIUM_URL = os.environ.get("SELENIUM_URL", "http://selenium-hub:4444/wd/hub")
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo-password-123")


def _chrome_options() -> Options:
    options = Options()
    # Headless because the instance has no display; the other two because a container's /dev/shm
    # is small enough to make Chrome crash mid-page-load without them.
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options


@pytest.fixture(scope="session")
def app_url() -> str:
    return APP_URL


@pytest.fixture(scope="session")
def demo_credentials() -> tuple[str, str]:
    return DEMO_EMAIL, DEMO_PASSWORD


@pytest.fixture(scope="session")
def driver():
    # The browser container may still be coming up when pytest starts, so a refused connection is
    # retried rather than reported as a failed test.
    session = None
    last_error: Exception | None = None
    for _ in range(30):
        try:
            session = webdriver.Remote(command_executor=SELENIUM_URL, options=_chrome_options())
            break
        except WebDriverException as error:
            last_error = error
            time.sleep(2)

    if session is None:
        raise RuntimeError(f"Selenium hub never became reachable at {SELENIUM_URL}") from last_error

    session.set_page_load_timeout(45)
    try:
        yield session
    finally:
        session.quit()
