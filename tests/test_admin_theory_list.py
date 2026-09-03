"""Admin Theory *list* endpoints (docs/spec/19 Gap 2).

Security invariants under test:
- anonymous -> 401; non-admin student -> 403 (server-side role gate is the source of truth).
- an author/admin sees DRAFT (non-published) rows via ?include_unpublished=true.
- the student reader (/api/theory/*) stays published-only: a draft never leaks there.
"""

from __future__ import annotations

from tests.admin_helper import build_admins
from tests.theory_helper import create_sign, new_client, student_client


def _draft_sign(roles, *, code="DRAFT-W9", family="warning", name="Qoralama belgi"):
    """Create + edit a sign but DO NOT publish -> stays lifecycle_status=draft."""
    r = roles["author"].post(
        "/api/admin/theory/signs",
        json={"official_code": code, "family": family, "position": 9},
    )
    assert r.status_code == 201, r.text
    sign_id = r.json()["road_sign_id"]
    e = roles["author"].put(
        f"/api/admin/theory/signs/{sign_id}",
        json={
            "name": name, "meaning": "Ma'no", "driver_action": "Harakat",
            "rule_codes": [], "question_ids": [],
        },
    )
    assert e.status_code == 200, e.text
    return {"sign_id": sign_id, "code": code, "name": name}


def _draft_marking(roles, *, code="DM-1", group="horizontal", name="Qoralama chiziq"):
    r = roles["author"].post(
        "/api/admin/theory/markings", json={"group": group, "code": code, "position": 9}
    )
    assert r.status_code == 201, r.text
    mid = r.json()["road_marking_id"]
    e = roles["author"].put(
        f"/api/admin/theory/markings/{mid}",
        json={"name": name, "meaning": "Ma'no", "rule_codes": []},
    )
    assert e.status_code == 200, e.text
    return {"marking_id": mid, "code": code, "name": name}


def _draft_gesture(roles, *, code="DG-1", name="Qoralama ishora"):
    r = roles["author"].post("/api/admin/theory/gestures", json={"code": code, "position": 9})
    assert r.status_code == 201, r.text
    gid = r.json()["gesture_id"]
    e = roles["author"].put(
        f"/api/admin/theory/gestures/{gid}",
        json={
            "name": name, "position_desc": "Tik turibdi", "allowed": "Yur",
            "forbidden": "To'xta", "rule_codes": [],
        },
    )
    assert e.status_code == 200, e.text
    return {"gesture_id": gid, "code": code, "name": name}


def _draft_light(roles, *, kind="main", title="Qoralama svetofor"):
    r = roles["author"].post("/api/admin/theory/lights", json={"kind": kind, "position": 9})
    assert r.status_code == 201, r.text
    lid = r.json()["light_id"]
    e = roles["author"].put(
        f"/api/admin/theory/lights/{lid}",
        json={"title": title, "meaning": "Ma'no", "rule_codes": []},
    )
    assert e.status_code == 200, e.text
    return {"light_id": lid, "title": title}


# --------------------------------------------------------------------------- #
# Role gating
# --------------------------------------------------------------------------- #
def test_admin_theory_lists_require_auth_401(client):
    anon = new_client(client)
    for path in ("signs", "markings", "gestures", "lights", "sections", "articles"):
        r = anon.get(f"/api/admin/theory/{path}")
        assert r.status_code == 401, (path, r.status_code, r.text)


def test_admin_theory_lists_forbidden_for_non_admin_403(client):
    student = student_client(client, telegram_id=1234, name="Talaba")
    for path in ("signs", "markings", "gestures", "lights", "sections", "articles"):
        r = student.get(f"/api/admin/theory/{path}")
        assert r.status_code == 403, (path, r.status_code, r.text)


# --------------------------------------------------------------------------- #
# Admin sees drafts; students never do
# --------------------------------------------------------------------------- #
def test_admin_sees_draft_sign_but_student_reader_does_not(client):
    roles = build_admins(client)
    draft = _draft_sign(roles)

    # Admin list (include_unpublished default true) contains the draft, with lifecycle keys.
    r = roles["admin"].get("/api/admin/theory/signs")
    assert r.status_code == 200, r.text
    signs = r.json()["signs"]
    match = [s for s in signs if s["code"] == draft["code"]]
    assert match, signs
    row = match[0]
    assert row["lifecycle_status"] == "draft"
    assert row["current_version_id"] is None
    assert row["latest_version_id"] is not None
    assert row["name"] == draft["name"]  # resolved from the latest (draft) version

    # Student reader is published-only: the draft is absent.
    student = student_client(client, telegram_id=1001, name="Dilnoza")
    sr = student.get("/api/theory/signs")
    assert sr.status_code == 200, sr.text
    codes = [s["code"] for s in sr.json()["signs"]]
    assert draft["code"] not in codes, codes


def test_admin_list_excludes_drafts_when_flag_false(client):
    """include_unpublished=false makes the admin route match the student invariant."""
    roles = build_admins(client)
    draft = _draft_sign(roles, code="DRAFT-W8")
    r = roles["admin"].get("/api/admin/theory/signs?include_unpublished=false")
    assert r.status_code == 200, r.text
    codes = [s["code"] for s in r.json()["signs"]]
    assert draft["code"] not in codes, codes


def test_admin_sees_drafts_across_entities(client):
    roles = build_admins(client)
    m = _draft_marking(roles)
    g = _draft_gesture(roles)
    light = _draft_light(roles)

    mr = roles["admin"].get("/api/admin/theory/markings").json()["markings"]
    assert any(x["code"] == m["code"] and x["lifecycle_status"] == "draft" for x in mr), mr

    gr = roles["admin"].get("/api/admin/theory/gestures").json()["gestures"]
    assert any(x["code"] == g["code"] and x["lifecycle_status"] == "draft" for x in gr), gr

    lr = roles["admin"].get("/api/admin/theory/lights").json()["lights"]
    assert any(x["title"] == light["title"] and x["lifecycle_status"] == "draft" for x in lr), lr

    # Student readers stay published-only across all three.
    student = student_client(client, telegram_id=1001, name="Dilnoza")
    assert m["code"] not in [x["code"] for x in student.get("/api/theory/markings").json()["markings"]]
    assert g["code"] not in [x["code"] for x in student.get("/api/theory/gestures").json()["gestures"]]
    assert light["title"] not in [x["title"] for x in student.get("/api/theory/lights").json()["lights"]]


def test_published_sign_visible_to_both(client):
    """Sanity: a published sign appears in both the admin list and the student reader."""
    roles = build_admins(client)
    from tests.admin_helper import make_rule
    make_rule(roles["admin"], code="YHQ:19.1")
    pub = create_sign(roles, code="PUB-W1", rule_code="YHQ:19.1", name="Nashr belgi")

    admin_codes = [s["code"] for s in roles["admin"].get("/api/admin/theory/signs").json()["signs"]]
    assert pub["code"] in admin_codes

    student = student_client(client, telegram_id=1001, name="Dilnoza")
    student_codes = [s["code"] for s in student.get("/api/theory/signs").json()["signs"]]
    assert pub["code"] in student_codes
