# Runs the Selenium specs from inside the Compose network against the `chrome` grid
# container, so no browser or driver has to be installed on the host:
#
#   docker compose --profile selenium up -d --build chrome
#   docker compose --profile selenium run --rm selenium
#
# The client is all this image needs; Chrome itself lives in the grid container.
FROM python:3.12-slim

WORKDIR /tests

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY conftest.py helpers.py test_application.py ./

# Overridden by docker-compose.yml; these defaults match a host-side run against the
# published ports.
ENV APP_BASE_URL=http://frontend:3000 \
    REMOTE_WEBDRIVER_URL=http://chrome:4444/wd/hub

CMD ["pytest", "-v", "--tb=short"]
