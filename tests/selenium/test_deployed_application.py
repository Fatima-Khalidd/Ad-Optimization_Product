"""CSC418 Task 6: open the deployed application in a real browser and verify its elements.

Two checks, both against whatever APP_URL points at:

* /api/health reached through the frontend, which only answers if the frontend container can talk
  to the backend container — the multi-container requirement of Task 5, proved from a browser.
* the login a marker has to finish to land on the seeded client report.
"""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BODY = (By.TAG_NAME, "body")


def test_health_endpoint_answers_through_the_frontend(driver, app_url):
    driver.get(f"{app_url}/api/health")

    # The reply is the backend's JSON, forwarded by the Next.js /api/:path* rewrite.
    assert '"status"' in driver.page_source
    assert '"ok"' in driver.page_source


def test_demo_login_reaches_the_approved_report(driver, app_url, demo_credentials):
    email, password = demo_credentials
    wait = WebDriverWait(driver, 30)

    driver.get(f"{app_url}/login")
    heading = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))
    assert heading.text == "Welcome back."

    driver.find_element(By.ID, "email").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

    wait.until(EC.url_contains("/dashboard"))
    hero = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="hero-band"]')))
    assert hero.is_displayed()

    # The report footer carries the run number, so this fails if the page is the "nothing to show
    # yet" empty state rather than a finished analysis.
    assert "Run #" in driver.find_element(*BODY).text
