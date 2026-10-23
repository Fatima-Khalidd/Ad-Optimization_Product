# Shared Selenium fixtures. Run against a local Chrome (webdriver-manager fetches the
# matching driver) or against the Chrome container in docker-compose.yml by exporting
# REMOTE_WEBDRIVER_URL - see tests/selenium/README.md.

from __future__ import annotations

import os

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from helpers import login as _login

BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3000").rstrip("/")
REMOTE_WEBDRIVER_URL = os.environ.get("REMOTE_WEBDRIVER_URL")
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: element-level checks against the deployed app")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def credentials() -> dict[str, str]:
    return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}


@pytest.fixture(scope="session")
def seeded(credentials):
    """The dashboard tests need the demo client, so say so instead of failing obscurely."""
    if not credentials["password"]:
        pytest.skip(
            "DEMO_PASSWORD is empty - seed the demo client first: "
            "docker compose --profile seed run seed"
        )


def _chrome_options() -> Options:
    options = Options()
    options.add_argument("--headless=new")
    # Chrome inside a container gets a small /dev/shm; without this the page crashes on
    # the three.js landing hero.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    return options


@pytest.fixture
def driver():
    if REMOTE_WEBDRIVER_URL:
        instance = webdriver.Remote(command_executor=REMOTE_WEBDRIVER_URL, options=_chrome_options())
    else:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        instance = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=_chrome_options()
        )
    # No implicit wait: an explicit wait reports which selector timed out.
    instance.implicitly_wait(0)
    yield instance
    instance.quit()


@pytest.fixture
def open_app(driver, base_url):
    """Navigate anywhere in the app and hand back the live driver."""

    def _open(path: str = "/"):
        driver.get(f"{base_url}{path}")
        return driver

    return _open


@pytest.fixture
def logged_in(driver, base_url, credentials, seeded):
    _login(driver, base_url, credentials)
    return driver
