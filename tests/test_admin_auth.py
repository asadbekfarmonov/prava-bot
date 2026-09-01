"""Server-side admin authorization: non-admin 403 on every admin endpoint; role
enforcement (author cannot publish/manage rules); user cannot set admin_role."""

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
    ("post", "/api/admin/users/xxx/role", {"role": "admin"}),
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


def test_author_cannot_publish_or_manage_rules(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    # Author creates a draft, submits, but cannot review/publish or create rules.
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule["code"]))
    assert r.status_code == 201, r.text
    version_id = r.json()["id"]

    assert roles["author"].post(f"/api/admin/versions/{version_id}/submit-review").status_code == 200
    # author role < reviewer: cannot review or publish
    assert roles["author"].post(f"/api/admin/versions/{version_id}/review").status_code == 403
    assert roles["author"].post(f"/api/admin/versions/{version_id}/publish").status_code == 403
    # author cannot create rules (admin-only)
    assert roles["author"].post("/api/admin/rules", json={"code": "YHQ:5.5", "text": "x"}).status_code == 403


def test_user_cannot_self_assign_role_via_role_endpoint(client):
    roles = build_admins(client)
    # A reviewer trying to assign roles (superadmin-only) is blocked.
    c = roles["reviewer"]
    me = c.get("/api/auth/me").json()["user"]
    assert c.post(f"/api/admin/users/{me['id']}/role", json={"role": "superadmin"}).status_code == 403


def test_role_resolution_requires_allowlist_membership(client):
    # A user with telegram id NOT in the allowlist can never gain a role, even if a
    # superadmin somehow set one (defense in depth: base capability required).
    roles = build_admins(client)
    outsider = new_client(client)
    u = dev_login(outsider, 12345, "Outsider")  # not in allowlist
    onboard(outsider)
    # superadmin assigns admin role to the outsider row...
    assert roles["superadmin"].post(f"/api/admin/users/{u['id']}/role", json={"role": "admin"}).status_code == 200
    # ...but the outsider still gets 403 because they are not in ADMIN_TELEGRAM_IDS.
    assert outsider.get("/api/admin/overview").status_code == 403
