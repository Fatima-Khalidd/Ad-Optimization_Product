"""Task 6 (Selenium): drives the deployed app in a real browser and verifies web elements.

Run with the stack up:

    pip install -r tests/selenium/requirements.txt
    pytest tests/selenium -v

The browser-level tests need the seeded demo client (docker compose --profile seed run
seed); without DEMO_PASSWORD they skip rather than fail, so the suite still proves the
deployment is reachable.
"""

from __future__ import annotations

import pytest
import requests
from selenium.webdriver.common.by import By

from helpers import wait_for

pytestmark = pytest.mark.smoke


def test_landing_page_hero_call_to_action_is_visible(open_app):
    """The element under test is the hero CTA link on the public landing page."""
    driver = open_app("/")
    cta = wait_for(driver, '[data-testid="hero-cta"]')

    assert cta.text.strip() == "Create account"
    assert cta.get_attribute("href").endswith("/signup")
    assert "Find the money leaking out of your ads" in driver.find_element(By.TAG_NAME, "h1").text


def test_health_endpoint_answers_through_the_frontend_proxy(base_url):
    """Browser-free check that the Next -> FastAPI -> Postgres path is wired in Compose.

    `/api/health` is reached on the frontend's origin, so this only passes when the
    rewrite to the backend container resolves and the API is serving.
    """
    response = requests.get(f"{base_url}/api/health", timeout=15)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # ENV=dev: prod forces Secure cookies, which no HTTP demo (including the ALB preview)
    # could send back. The container stack deliberately runs the dev profile.
    assert body["env"] == "dev"
    assert body["instance"], "health must name the serving instance for the LB demo"


def test_protected_api_route_rejects_an_anonymous_caller(base_url):
    response = requests.get(f"{base_url}/api/auth/me", timeout=15)

    assert response.status_code == 401


def test_login_renders_the_approved_report(logged_in):
    """Seeded demo client -> dashboard -> the report hero band is in the DOM."""
    hero_band = wait_for(logged_in, '[data-testid="hero-band"]')

    assert "/dashboard" in logged_in.current_url
    assert len(hero_band.text.strip()) > 0


def test_upload_panel_renders_its_drop_zone(logged_in, base_url):
    logged_in.get(f"{base_url}/dashboard/upload")
    drop_zone = wait_for(logged_in, '[data-testid="drop-zone"]')

    assert drop_zone.is_displayed()
