# Selenium specs (Section A, task 6)

Five checks against the running stack: two browser-free API assertions through the
frontend's `/api/*` proxy, and three browser assertions on real web elements.

| Test | What it proves |
| --- | --- |
| `test_landing_page_hero_call_to_action_is_visible` | The deployed page renders and the hero CTA element exists with the right label and link |
| `test_health_endpoint_answers_through_the_frontend_proxy` | frontend container → backend container → Postgres are wired; names the serving instance |
| `test_protected_api_route_rejects_an_anonymous_caller` | Auth is enforced through the proxy, not just in code |
| `test_login_renders_the_approved_report` | Logging in as the seeded client shows the approved report hero band |
| `test_upload_panel_renders_its_drop_zone` | The upload screen's drop zone element is present and visible |

## Run it from your machine (local Chrome)

```bash
pip install -r tests/selenium/requirements.txt
docker compose --profile seed run seed          # one time, creates demo@example.com
pytest tests/selenium -v
```

`webdriver-manager` downloads the ChromeDriver that matches your installed Chrome, so
nothing else has to be set up. Export `APP_BASE_URL` if you publish the frontend on a
port other than 3000.

## Run it in a container (no Chrome needed)

```bash
docker compose --profile selenium up -d --build
docker compose --profile selenium run --rm selenium
```

The `selenium` service talks to `chrome:4444` (selenium/standalone-chrome) and to
`frontend:3000` over the Compose network. Point it at a deployed URL instead by
exporting `APP_BASE_URL` before the `run`.

## Useful variables

| Name | Default | Purpose |
| --- | --- | --- |
| `APP_BASE_URL` | `http://localhost:3000` | Origin under test |
| `REMOTE_WEBDRIVER_URL` | unset | Set it to use a grid instead of a local driver |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | `demo@example.com` / empty | Seeded login; the dashboard tests skip if the password is empty |
| `SELENIUM_TIMEOUT` | `20` | Explicit wait seconds per element |

## Notes for the demo

* Login is rate-limited to 5 attempts per minute per IP. Re-running the whole file a few
  times in a row can therefore return 429 and fail `test_login_renders_the_approved_report`
  - wait a minute, and that itself is worth showing in the viva.
* Behind the AWS load balancer, add `INSTANCE_LABEL` evidence with
  `scripts/verify-load-balancing.sh`, which polls `/api/health` and prints the distinct
  instance ids it sees.
