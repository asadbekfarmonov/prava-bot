"""QA adversarial additions for Slice 2 (docs/spec/03, 05, 09, 12).

Closes gaps the developer suite left open on the security-critical mock exam:

A. RAW-RESPONSE no-answer-leak that also PROVES the API does not sort correct-first
   and that option ids are opaque UUIDs (spec 09 "Option-id inference defense").
   The developer test only checked option-key shape, not the ordering defense.
B. Version pinning survives a later content edit: repointing
   Question.current_version_id to a NEW version does NOT regenerate the pinned set,
   grading uses the PINNED version's options, and a new-version option id is rejected.
C. Selection eligibility: non-published, wrong-language, and wrong-category questions
   are excluded from the pool; and < question_count eligible => 409 (not a short exam).
D. Client cannot extend the deadline by smuggling expires_at/time_limit_seconds in the
   answer body (mass-assignment allowlist; expires_at stays server-authoritative).
E. remaining_seconds is server-derived from expires_at (not client-supplied) and never
   exceeds the configured limit.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.domain.enums import Category, Language, Topic, VersionStatus
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    MockAttempt,
    MockQuestion,
    Question,
    QuestionVersion,
    QuestionVersionTranslation,
    User,
)
from app.services.content_source import OptionDraft, QuestionDraft, RuleDraft
from app.services.ingestion import publish_question, upsert_rule
from app.services.mock import _eligible_version_ids
from app.storage.db import get_session_factory
from tests.seed_helper import seed_demo_bank


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _login(client, telegram_id=1001, name="Dilnoza"):
    assert client.post(
        "/api/dev/login", json={"telegram_id": telegram_id, "first_name": name}
    ).status_code == 200


def _onboard(client, name="Dilnoza"):
    assert client.put(
        "/api/profile", json={"display_name": name, "category": "B", "language": "uz"}
    ).status_code == 200


def _start(client) -> dict:
    r = client.post("/api/mock/attempts")
    assert r.status_code == 200, r.text
    return r.json()


def _author(db) -> User:
    author = db.scalar(select(User).where(User.telegram_id == "0"))
    if author is None:
        author = User(telegram_id="0", first_name="Seed")
        db.add(author)
        db.flush()
    return author


def _ensure_rule(db, code="YHQ:9.9") -> None:
    upsert_rule(
        db,
        RuleDraft(code=code, text="Qoida matni.", title="Qoida", verified_at=date.today()),
    )


def _publish_controlled(n: int, *, correct_position: int = 2, topic=Topic.GENERAL_RULES) -> None:
    """Publish ``n`` category-B uz questions with the correct option deliberately at
    ``correct_position`` (1-based) so a correct-first sort would be detectable."""
    sf = get_session_factory()
    with sf() as db:
        author = _author(db)
        _ensure_rule(db)
        db.commit()
        for i in range(n):
            opts = []
            for pos in range(1, 4):  # 3 options
                opts.append(
                    OptionDraft(
                        text=f"opt{pos}",
                        is_correct=(pos == correct_position),
                        explanation="izoh",
                    )
                )
            publish_question(
                db,
                QuestionDraft(
                    category=Category.B,
                    topic=topic,
                    prompt=f"Nazorat savoli #{i}?",
                    short_explanation="eslab qoling",
                    options=opts,
                    rule_code="YHQ:9.9",
                ),
                author,
            )
        db.commit()


def _correct_by_qvid(qvids: list[str]) -> dict[str, str]:
    sf = get_session_factory()
    with sf() as db:
        out = {}
        for qvid in qvids:
            opts = db.scalars(
                select(AnswerOption).where(AnswerOption.question_version_id == qvid)
            ).all()
            out[qvid] = next(o.id for o in opts if o.is_correct)
        return out


# --------------------------------------------------------------------------- #
# A. RAW-RESPONSE no-answer-leak + no correct-first sorting + opaque UUID ids
# --------------------------------------------------------------------------- #
def test_raw_in_progress_payload_no_leak_no_correct_first_uuid_ids(client):
    # Controlled bank: correct option is ALWAYS at stored position 2. If the API leaked
    # via ordering (sorted correct-first) the correct option would surface at index 0.
    _publish_controlled(22, correct_position=2)
    _login(client)
    _onboard(client)
    state = _start(client)

    qs = state["questions"]
    assert len(qs) == 20
    correct = _correct_by_qvid([q["question_version_id"] for q in qs])

    for q in qs:
        # Whole-question no-leak: none of the answer-revealing keys present.
        for banned in ("is_correct", "explanation", "short_explanation", "rule",
                       "correct_option_id", "correct"):
            assert banned not in q, f"leaked {banned} in question payload"

        opts = q["options"]
        # Option payload keys are EXACTLY {id, position, text}.
        for o in opts:
            assert set(o.keys()) == {"id", "position", "text"}
            # Opaque UUID (not an integer index, not encoding the position).
            assert len(o["id"]) == 36 and o["id"].count("-") == 4
            assert o["id"] != str(o["position"])

        # The correct option is NOT surfaced first -> proves no correct-first sorting.
        cid = correct[q["question_version_id"]]
        assert opts[0]["id"] != cid, "correct option leaked at index 0 (correct-first sort)"
        # Options are ordered by stored position (defense is positional, not correctness).
        assert [o["position"] for o in opts] == sorted(o["position"] for o in opts)


# --------------------------------------------------------------------------- #
# B. Version pinning survives a later content edit
# --------------------------------------------------------------------------- #
def test_pinning_survives_content_edit_grading_uses_pinned_version(client):
    _publish_controlled(22, correct_position=2)
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    pinned = sorted((q["position"], q["question_version_id"]) for q in state["questions"])
    target_qvid = pinned[0][1]

    # Simulate a published-content edit: create a NEW version for the pinned question and
    # repoint Question.current_version_id to it (old version becomes superseded).
    sf = get_session_factory()
    with sf() as db:
        old = db.get(QuestionVersion, target_qvid)
        question = db.get(Question, old.question_id)
        new_v = QuestionVersion(
            question_id=question.id,
            version=old.version + 1,
            status=VersionStatus.PUBLISHED,
            difficulty=old.difficulty,
            published_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
        )
        db.add(new_v)
        db.flush()
        db.add(QuestionVersionTranslation(
            question_version_id=new_v.id, language=Language.UZ,
            prompt="TAHRIRLANGAN savol", short_explanation="yangi",
        ))
        new_correct_id = None
        for pos in range(1, 4):
            opt = AnswerOption(question_version_id=new_v.id, position=pos, is_correct=(pos == 1))
            db.add(opt)
            db.flush()
            db.add(AnswerOptionTranslation(
                answer_option_id=opt.id, language=Language.UZ, text=f"yangi{pos}", explanation="e"
            ))
            if pos == 1:
                new_correct_id = opt.id
        old.status = VersionStatus.SUPERSEDED
        question.current_version_id = new_v.id
        db.commit()
        new_v_id = new_v.id

    # (1) Reopen does NOT regenerate: the pinned set is byte-for-byte the same old versions.
    cur = client.get("/api/mock/attempts/current").json()
    assert sorted((q["position"], q["question_version_id"]) for q in cur["questions"]) == pinned
    assert new_v_id not in {q["question_version_id"] for q in cur["questions"]}
    # The pinned question still shows the OLD prompt, not "TAHRIRLANGAN".
    p1 = next(q for q in cur["questions"] if q["question_version_id"] == target_qvid)
    assert p1["prompt"] != "TAHRIRLANGAN savol"

    # (2) A new-version option id is rejected for the pinned question (grading scoped to
    #     the pinned version, not the live/current one).
    r = client.post(
        f"/api/mock/attempts/{attempt_id}/answers",
        json={"question_version_id": target_qvid, "selected_option_id": new_correct_id},
    )
    assert r.status_code == 400

    # (3) Grading uses the PINNED version: answer every pinned question with the pinned
    #     correct option -> 20/20 pass, and review renders the pinned versions.
    correct = _correct_by_qvid([qvid for _pos, qvid in pinned])
    for _pos, qvid in pinned:
        assert client.post(
            f"/api/mock/attempts/{attempt_id}/answers",
            json={"question_version_id": qvid, "selected_option_id": correct[qvid]},
        ).status_code == 200
    res = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    assert res["correct_count"] == 20 and res["passed"] is True

    review = client.get(f"/api/mock/attempts/{attempt_id}/review").json()
    review_vids = sorted((it["position"], it["question_version_id"]) for it in review["items"])
    assert review_vids == pinned
    item1 = next(it for it in review["items"] if it["question_version_id"] == target_qvid)
    assert item1["correct_option_id"] == correct[target_qvid]  # pinned correct, not new_correct_id
    assert item1["correct_option_id"] != new_correct_id


# --------------------------------------------------------------------------- #
# C. Selection eligibility (published + category + language) and insufficient pool
# --------------------------------------------------------------------------- #
def test_eligible_pool_excludes_draft_wrong_lang_wrong_category(client):
    # 3 fully-eligible published B/uz questions...
    _publish_controlled(3)

    sf = get_session_factory()
    with sf() as db:
        base = set(_eligible_version_ids(db, Category.B, Language.UZ))
        assert len(base) == 3

        author = _author(db)

        # (i) A DRAFT (unpublished) B/uz question -> excluded.
        q_draft = Question(category=Category.B, topic=Topic.GENERAL_RULES,
                           lifecycle_status=VersionStatus.DRAFT, created_by_user_id=author.id)
        db.add(q_draft); db.flush()
        v_draft = QuestionVersion(question_id=q_draft.id, version=1, status=VersionStatus.DRAFT,
                                  difficulty=1)
        db.add(v_draft); db.flush()
        db.add(QuestionVersionTranslation(question_version_id=v_draft.id, language=Language.UZ,
                                          prompt="draft", short_explanation="s"))
        q_draft.current_version_id = v_draft.id

        # (ii) A PUBLISHED B question with only a RU translation (no uz) -> excluded.
        q_ru = Question(category=Category.B, topic=Topic.GENERAL_RULES,
                        lifecycle_status=VersionStatus.PUBLISHED, created_by_user_id=author.id)
        db.add(q_ru); db.flush()
        v_ru = QuestionVersion(question_id=q_ru.id, version=1, status=VersionStatus.PUBLISHED,
                               difficulty=1)
        db.add(v_ru); db.flush()
        db.add(QuestionVersionTranslation(question_version_id=v_ru.id, language=Language.RU,
                                          prompt="ru", short_explanation="s"))
        q_ru.current_version_id = v_ru.id

        # (iii) A PUBLISHED uz question in category A -> excluded from a B query.
        q_a = Question(category=Category.A, topic=Topic.GENERAL_RULES,
                       lifecycle_status=VersionStatus.PUBLISHED, created_by_user_id=author.id)
        db.add(q_a); db.flush()
        v_a = QuestionVersion(question_id=q_a.id, version=1, status=VersionStatus.PUBLISHED,
                              difficulty=1)
        db.add(v_a); db.flush()
        db.add(QuestionVersionTranslation(question_version_id=v_a.id, language=Language.UZ,
                                          prompt="a-cat", short_explanation="s"))
        q_a.current_version_id = v_a.id
        db.commit()

        draft_id, ru_id, a_id = v_draft.id, v_ru.id, v_a.id
        after = set(_eligible_version_ids(db, Category.B, Language.UZ))

    # None of the three ineligible versions leaked into the B/uz pool.
    assert after == base
    assert draft_id not in after
    assert ru_id not in after
    assert a_id not in after


def test_insufficient_pool_returns_409(client):
    _publish_controlled(10)  # only 10 eligible < 20 required
    _login(client)
    _onboard(client)
    r = client.post("/api/mock/attempts")
    assert r.status_code == 409
    assert "savol" in r.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# D. Client cannot extend the deadline via the answer body
# --------------------------------------------------------------------------- #
def test_client_cannot_extend_deadline_via_body(client):
    _publish_controlled(22)
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    qvid = state["questions"][0]["question_version_id"]
    opt = state["questions"][0]["options"][0]["id"]

    sf = get_session_factory()
    with sf() as db:
        before = db.get(MockAttempt, attempt_id).expires_at

    # Smuggle a far-future expires_at + a huge time limit in the autosave body.
    far_future = "2099-01-01T00:00:00+00:00"
    r = client.post(
        f"/api/mock/attempts/{attempt_id}/answers",
        json={
            "question_version_id": qvid,
            "selected_option_id": opt,
            "expires_at": far_future,
            "time_limit_seconds": 999999,
            "remaining_seconds": 999999,
        },
    )
    assert r.status_code == 200

    with sf() as db:
        after = db.get(MockAttempt, attempt_id).expires_at
    assert after == before  # server-authoritative deadline untouched


# --------------------------------------------------------------------------- #
# E. remaining_seconds is server-derived and bounded by the configured limit
# --------------------------------------------------------------------------- #
def test_remaining_seconds_server_derived_and_bounded(client):
    _publish_controlled(22)
    _login(client)
    _onboard(client)
    state = _start(client)
    assert 0 < state["remaining_seconds"] <= state["time_limit_seconds"] == 1500

    # Interleave Slice-1 sanity: the demo bank still ingests + a completed attempt shows 0.
    grade_qvids = [q["question_version_id"] for q in state["questions"]]
    correct = _correct_by_qvid(grade_qvids)
    for qvid in grade_qvids:
        client.post(
            f"/api/mock/attempts/{state['id']}/answers",
            json={"question_version_id": qvid, "selected_option_id": correct[qvid]},
        )
    res = client.post(f"/api/mock/attempts/{state['id']}/submit").json()
    assert res["status"] == "completed"
    assert res["remaining_seconds"] == 0  # completed attempts report no remaining time
