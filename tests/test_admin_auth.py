"""Server-side admin authorization (two-level model: ADMIN / USER).

Being in ADMIN_TELEGRAM_IDS is the sole gate: every allowlisted user is a full ADMIN
and passes every admin endpoint; a non-allowlisted user gets 403 on all of them and an
unauthenticated request gets 401. There is no role tier and no role-assignment endpoint.
"""

from __future__ import annotations

from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    valid_question_payload,
)

# (method, path, json-body) for admin endpoints — a non-admin must get 403 on all.
ADMIN_ENDPOINTS = [
    ("get", "/api/admin/overview", None),
    ("get", "/api/admin/questions", None),
    ("post", "/api/admin/questions", {"topic": "general_rules", "options": [{"text": "a"}]}),
    ("put", "/api/admin/questions/xxx", {"topic": "general_rules", "options": [{"text": "a"}]}),
    ("post", "/api/admin/questions/xxx/archive", None),
    ("post", "/api/admin/versions/xxx/submit-review", None),
    ("post", "/api/admin/versions/xxx/review", None),
    ("post", "/api/admin/versions/xxx/publish", None),
    ("get", "/api/admin/questions/xxx/qa", None),
    ("post", "/api/admin/duplicates/check", {"prompt": "p", "option_texts": []}),
    ("get", "/api/admin/rules", None),
    ("post", "/api/admin/rules", {"code": "YHQ:1.1", "text": "t"}),
    ("put", "/api/admin/rules/xxx", {"text": "t"}),
    ("post", "/api/admin/rules/xxx/supersede", {"new_status": "superseded"}),
    ("get", "/api/admin/reports", None),
    ("post", "/api/admin/reports/xxx/resolve", {"action": "resolve"}),
    ("post", "/api/admin/import", {"format": "json", "content": "[]"}),
]


def test_non_admin_blocked_from_every_admin_endpoint(client):
    c = new_client(client)
    dev_login(c, 1001, "Student")  # 1001 NOT in ADMIN_TELEGRAM_IDS
    onboard(c)
    for method, path, body in ADMIN_ENDPOINTS:
        resp = getattr(c, method)(path, json=body) if body is not None else getattr(c, method)(path)
        assert resp.status_code == 403, f"{method} {path} -> {resp.status_code} (expected 403)"


def test_unauthenticated_blocked(client):
    c = new_client(client)
    assert c.get("/api/admin/overview").status_code == 401


def test_admin_can_create_publish_and_manage_rules(client):
    """Two-level model: any allowlisted admin can create (=live), edit, and manage
    rules. Create publishes immediately; the vestigial transition endpoints are
    idempotent no-ops on the already-published version."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    # Create is live: the question is published immediately.
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule["code"]))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "published"
    version_id = body["id"]

    # Vestigial transitions are idempotent no-ops (still 200) for any admin.
    assert roles["author"].post(f"/api/admin/versions/{version_id}/submit-review").status_code == 200
    assert roles["author"].post(f"/api/admin/versions/{version_id}/review").status_code == 200
    assert roles["author"].post(f"/api/admin/versions/{version_id}/publish").status_code == 200
    # Any admin can create rules.
    assert roles["author"].post("/api/admin/rules", json={"code": "YHQ:5.5", "text": "x"}).status_code == 201


def test_only_allowlist_membership_grants_admin(client):
    """A user whose Telegram id is NOT in ADMIN_TELEGRAM_IDS is never an admin, and the
    persisted admin_role DB column is never consulted (two-level model)."""
    roles = build_admins(client)  # ensures the app/DB is initialised with admins
    assert roles["admin"].get("/api/admin/overview").status_code == 200

    outsider = new_client(client)
    dev_login(outsider, 12345, "Outsider")  # not in allowlist
    onboard(outsider)
    assert outsider.get("/api/admin/overview").status_code == 403
    me = outsider.get("/api/auth/me").json()["user"]
    assert me["is_admin"] is False
    assert me["admin_role"] is None
