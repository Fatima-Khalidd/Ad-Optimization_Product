def test_health_reports_ok_and_env(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    # The load balancer demo tells the two Auto Scaling targets apart with this field.
    assert body["instance"]
