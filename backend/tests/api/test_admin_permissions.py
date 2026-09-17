"""Every /api/admin route must be admin-only (docs/PLAN.md section 5, Stage 2 "Done when")."""

import pytest

from tests.api.helpers import login_as, make_admin, make_client, user_for

ROUTES = [
    ("GET", "/api/admin/clients", None),
    ("GET", "/api/admin/clients/1", None),
    ("PATCH", "/api/admin/clients/1", {"base_fee": "20000"}),
    ("GET", "/api/admin/runs", None),
    ("POST", "/api/admin/runs/1/approve", {"note": "ok"}),
    ("POST", "/api/admin/runs/1/reject", {"note": "no"}),
    ("GET", "/api/admin/invoices", None),
    (
        "POST",
        "/api/admin/invoices",
        {"client_id": 1, "period_start": "2026-08-01", "period_end": "2026-08-31"},
    ),
    ("POST", "/api/admin/invoices/1/confirm", {"confirmed_recovered_waste": "23000"}),
    ("POST", "/api/admin/invoices/1/issue", {"due_date": "2026-09-20"}),
    ("POST", "/api/admin/invoices/1/void", {"note": "wrong month"}),
    ("GET", "/api/admin/audit-log", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_a_logged_in_client_gets_403(api, db, method, path, body):
    client = make_client(db)
    db.commit()
    login_as(api, user_for(db, client))

    response = api.request(method, path, json=body)

    assert response.status_code == 403, response.text


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_an_anonymous_caller_gets_401(api, db, method, path, body):
    response = api.request(method, path, json=body)
    assert response.status_code == 401, response.text


def test_an_admin_gets_past_the_guard(api, db):
    admin = make_admin(db)
    db.commit()
    login_as(api, admin)

    assert api.get("/api/admin/clients").status_code == 200
    assert api.get("/api/admin/audit-log").status_code == 200
