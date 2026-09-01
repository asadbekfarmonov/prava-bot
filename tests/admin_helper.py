"""Helpers for admin/media tests: build role-scoped logged-in clients over one app/DB."""

from __future__ import annotations

from fastapi.testclient import TestClient


def new_client(client) -> TestClient:
    """A fresh client (isolated cookie jar) bound to the same app + DB engine."""
    return TestClient(client.app)


def dev_login(c: TestClient, telegram_id: int, first_name: str = "U") -> dict:
    r = c.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": first_name})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def onboard(c: TestClient) -> None:
    r = c.put("/api/profile", json={"display_name": "X", "category": "B", "language": "uz"})
    assert r.status_code == 200, r.text


def build_admins(client) -> dict[str, TestClient]:
    """Return role -> logged-in client. 9010 is env-seeded superadmin; it assigns roles."""
    superadmin = new_client(client)
    su = dev_login(superadmin, 9010, "Super")
    onboard(superadmin)
    assert su["admin_role"] == "superadmin", su

    def make(telegram_id: int, role: str, name: str) -> TestClient:
        c = new_client(client)
        u = dev_login(c, telegram_id, name)
        onboard(c)
        r = superadmin.post(f"/api/admin/users/{u['id']}/role", json={"role": role})
        assert r.status_code == 200, r.text
        return c

    return {
        "superadmin": superadmin,
        "admin": make(9003, "admin", "Admin"),
        "reviewer": make(9002, "content_reviewer", "Reviewer"),
        "author": make(9001, "content_author", "Author"),
    }


def make_rule(admin: TestClient, code: str = "YHQ:99.1", text: str = "Test qoida matni") -> dict:
    r = admin.post("/api/admin/rules", json={"code": code, "text": text, "title": "Test"})
    assert r.status_code == 201, r.text
    return r.json()


def valid_question_payload(rule_code: str, prompt: str = "Test savol?") -> dict:
    return {
        "category": "B",
        "topic": "general_rules",
        "prompt": prompt,
        "short_explanation": "Eslab qoling: test.",
        "difficulty": 1,
        "rule_codes": [rule_code],
        "options": [
            {"text": "To'g'ri", "explanation": "Chunki to'g'ri.", "is_correct": True},
            {"text": "Noto'g'ri", "explanation": "Chunki noto'g'ri.", "is_correct": False},
        ],
    }


def question_id_for_version(version_id: str) -> str:
    from app.domain.models import QuestionVersion
    from app.storage.db import session_scope

    with session_scope() as db:
        v = db.get(QuestionVersion, version_id)
        return v.question_id
