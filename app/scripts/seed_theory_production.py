"""Populate the Theory (Nazariya) section with production-ready content (docs/spec/18).

Scope (content + wiring completion on the EXISTING schema/services — no schema/migration/
endpoint changes):
  S1  >=4 real regulirovshchik (controller) gestures.
  S2  >=5 real main traffic-light states.
  S3  >=8 real road markings (horizontal + vertical).
  S5  Normalise sections to non-demo slugs, ensure the >=12 core sections from spec 14 exist
      and are published, and author >=1 real Uzbek lesson article per core section using the
      block palette (Rule -> example -> common mistake -> practice).
  S6  Link every lesson article to the existing published questions on its Topic
      (ArticleContentInput.question_ids -> TheoryArticleQuestionLink).
  S7  Archive leftover DEMO artefacts so no DEMO-* code / "(DEMO)" title remains published;
      the first-aid article is an explicit, honest note (NOT a DEMO string).

Content policy (binding, docs/spec/18):
  * Correct by standard road-traffic norms; content is ``ai_assisted`` and review-flagged.
  * We never claim this is the official YHQ exam text.
  * FIRST AID ships legal (non-medical) post-accident obligations plus an explicit
    "tibbiy jihatdan ko'rikdan o'tkazilmoqda" note; no fabricated medical procedure.

Reuses ``app.services.theory_admin`` create/edit/submit/review/publish helpers and the ``YHQ``
rule (created via ``rules_admin`` if missing). Idempotent / prod-safe: upsert/skip existing,
never duplicate. Text-only (no network image fetch) so it also runs offline / on sqlite.

Usage:  python -m app.scripts.seed_theory_production
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AdminRole, Language, Topic, VersionStatus
from app.domain.models import (
    ControllerGesture,
    ControllerGestureTranslation,
    ControllerGestureVersion,
    Question,
    Rule,
    RoadMarking,
    RoadMarkingVersion,
    TheoryArticle,
    TheoryArticleTranslation,
    TheoryArticleVersion,
    TheorySection,
    TheorySectionTranslation,
    TrafficLightState,
    TrafficLightStateTranslation,
    TrafficLightStateVersion,
    User,
)
from app.observability.logging import configure_logging, log_event
from app.services import rules_admin, theory_admin
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"
_RULE_CODE = "YHQ"
_LANG = Language.UZ


# --------------------------------------------------------------------------- #
# Publish helpers (same pattern as seed_theory_demo.py)
# --------------------------------------------------------------------------- #
def ensure_seed_author(db: Session) -> User:
    author = db.scalar(select(User).where(User.telegram_id == SEED_AUTHOR_TELEGRAM_ID))
    if author is None:
        author = User(
            telegram_id=SEED_AUTHOR_TELEGRAM_ID, first_name="Seed", last_name="Author",
            admin_role=AdminRole.CONTENT_AUTHOR,
        )
        db.add(author)
        db.flush()
    return author


def _ensure_rule(db: Session, author: User) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.code == _RULE_CODE))
    if rule is not None:
        return rule
    return rules_admin.create_rule(
        db, author, code=_RULE_CODE,
        text="Yo'l harakati qoidalari (umumiy). Aniq bandlar rasmiy manbadan tekshirilishi kerak.",
        title="YHQ", source_url="",
    )


def _publish_article(db, author, version):
    theory_admin.submit_article_review(db, author, version.id)
    theory_admin.review_article(db, author, version.id)
    theory_admin.publish_article(db, author, version.id)


def _publish_marking(db, author, version):
    theory_admin.submit_marking_review(db, author, version.id)
    theory_admin.review_marking(db, author, version.id)
    theory_admin.publish_marking(db, author, version.id)


def _publish_gesture(db, author, version):
    theory_admin.submit_gesture_review(db, author, version.id)
    theory_admin.review_gesture(db, author, version.id)
    theory_admin.publish_gesture(db, author, version.id)


def _publish_light(db, author, version):
    theory_admin.submit_light_review(db, author, version.id)
    theory_admin.review_light(db, author, version.id)
    theory_admin.publish_light(db, author, version.id)


def _published_question_ids_for_topic(db: Session, topic: Topic, limit: int = 12) -> list[str]:
    return list(
        db.scalars(
            select(Question.id)
            .where(
                Question.topic == topic,
                Question.lifecycle_status == VersionStatus.PUBLISHED,
                Question.current_version_id.is_not(None),
            )
            .order_by(Question.created_at)
            .limit(limit)
        )
    )


# --------------------------------------------------------------------------- #
# Lesson block builder (Rule -> example -> common mistake -> memory tip -> practice)
# --------------------------------------------------------------------------- #
def _lesson_blocks(intro: str, rule_note: str, example: str, mistake: str, tip: str):
    return [
        theory_admin.BlockInput(type="text", body=intro),
        theory_admin.BlockInput(type="rule_callout", body=rule_note, rule_code=_RULE_CODE),
        theory_admin.BlockInput(type="example", body=example),
        theory_admin.BlockInput(type="warning", body="Ko'p uchraydigan xato: " + mistake),
        theory_admin.BlockInput(type="memory_tip", body=tip),
    ]


# (slug, old_demo_slug|None, title, subtitle, topic, position, article-spec)
CORE_SECTIONS = [
    {
        "slug": "yol-belgilari", "old": "demo-yol-belgilari",
        "title": "Yo'l belgilari", "subtitle": "Belgilarni shakl va rang bo'yicha o'qish",
        "topic": Topic.ROAD_SIGNS, "position": 1,
        "article": {
            "slug": "yol-belgilarini-oqish", "kind": "lesson",
            "title": "Yo'l belgilarini o'qishni o'rganish",
            "summary": "Belgilar oilalari, shakli va ranglari orqali ma'nosini tez aniqlash.",
            "blocks": _lesson_blocks(
                "Yo'l belgilari haydovchiga yo'ldagi vaziyat, cheklovlar va ruxsatlar haqida "
                "ma'lumot beradi. Har bir belgi shakli va rangi bo'yicha oilaga bo'linadi: "
                "ogohlantiruvchi, imtiyoz, taqiqlovchi, buyuruvchi, axborot-ko'rsatkich va servis.",
                "Belgilar talablariga rioya qilish majburiy. Belgi va yo'l chizig'i "
                "bir-biriga zid bo'lsa, belgi ustunlik qiladi.",
                "Uchburchak shaklidagi qizil hoshiyali belgi — ogohlantiruvchi (masalan, "
                "xavfli burilish); doira ichidagi qizil belgi — taqiqlovchi.",
                "belgining faqat rasmiga qarab, uning oilasini (shakl va rang) e'tiborsiz "
                "qoldirish.",
                "Shakl va rang ma'noni tez aytadi: uchburchak — ogohlantiradi, "
                "doira — buyuradi yoki taqiqlaydi.",
            ),
        },
    },
    {
        "slug": "svetofor-signallari", "old": "demo-svetofor",
        "title": "Svetofor signallari", "subtitle": "Qizil, sariq va yashil signallar",
        "topic": Topic.SIGNALS, "position": 2,
        "article": {
            "slug": "svetofor-signallari-asosi", "kind": "lesson",
            "title": "Svetofor signallarini tushunish",
            "summary": "Uch rangli svetofor signallarining ma'nosi va to'g'ri harakat.",
            "blocks": _lesson_blocks(
                "Svetofor uch xil rangdagi signal orqali harakatni boshqaradi: qizil, "
                "sariq va yashil.",
                "Qizil — to'xtash; sariq — harakatni taqiqlaydi va rejim o'zgarishidan "
                "ogohlantiradi; yashil — yo'l bo'sh bo'lsa harakatga ruxsat.",
                "Qizil va sariq birga yonsa, tez orada yashil yonadi — lekin hali "
                "harakatlanish taqiqlanadi.",
                "sariq chiroqda tezlashtirib o'tib ketishga urinish.",
                "Yashil ham 'majburiy o'tish' emas — avval chorraha bo'shligiga va "
                "piyodalarga ishonch hosil qiling.",
            ),
        },
    },
    {
        "slug": "regulirovshchik-ishoralari", "old": None,
        "title": "Regulirovshchik ishoralari", "subtitle": "Tartibga soluvchi qo'l ishoralari",
        "topic": Topic.SIGNALS, "position": 3,
        "article": {
            "slug": "regulirovshchik-ishoralari-asosi", "kind": "lesson",
            "title": "Regulirovshchik ishoralari",
            "summary": "Tartibga soluvchining ishoralari va ularning svetofordan ustunligi.",
            "blocks": _lesson_blocks(
                "Regulirovshchik (yo'l harakatini tartibga soluvchi) ishoralari svetofor "
                "va belgilardan ustun turadi.",
                "Tartibga soluvchining talablari svetofor, belgilar va chiziqlardan ustun; "
                "ularga so'zsiz bo'ysunish shart.",
                "Qo'llar yon tomonga uzatilganda: ko'krak va orqa tomondan harakat "
                "taqiqlanadi, yon (yelka) tomondan to'g'riga va o'ngga yurish mumkin.",
                "regulirovshchik ishorasini svetofordan past deb hisoblab, svetoforga qarab "
                "harakatlanish.",
                "Qo'l tepaga ko'tarilgan bo'lsa — hamma yo'nalishda 'to'xta' (sariqqa o'xshash).",
            ),
        },
    },
    {
        "slug": "yol-chiziqlari", "old": None,
        "title": "Yo'l chiziqlari", "subtitle": "Gorizontal va vertikal razmetka",
        "topic": Topic.ROAD_MARKINGS, "position": 4,
        "article": {
            "slug": "yol-chiziqlari-asosi", "kind": "lesson",
            "title": "Yo'l chiziqlari (razmetka)",
            "summary": "Uzluksiz va uzuq chiziqlar, to'xtash chizig'i va zebra.",
            "blocks": _lesson_blocks(
                "Yo'l chiziqlari harakat oqimlarini ajratadi, qatorlarni belgilaydi va "
                "to'xtash joylarini ko'rsatadi.",
                "Uzluksiz chiziqni kesib o'tish taqiqlanadi; uzuq-uzuq chiziqni xavfsiz "
                "bo'lganda kesish mumkin.",
                "To'xtash chizig'i (1.12) svetofor yoki 'STOP' belgisi oldida qayerda "
                "to'xtashni ko'rsatadi.",
                "uzluksiz chiziq orqali quvib o'tish yoki qator almashtirish.",
                "Uzuq chiziq — 'mumkin', uzluksiz chiziq — 'mumkin emas'.",
            ),
        },
    },
    {
        "slug": "chorrahalar-ustunlik", "old": None,
        "title": "Chorrahalar va ustunlik", "subtitle": "Kim birinchi o'tadi",
        "topic": Topic.INTERSECTIONS, "position": 5,
        "article": {
            "slug": "chorrahalar-ustunlik-asosi", "kind": "lesson",
            "title": "Chorrahalar va ustunlik qoidalari",
            "summary": "Bosh yo'l, teng chorraha va 'o'ng qo'l' qoidasi.",
            "blocks": _lesson_blocks(
                "Chorrahada kim birinchi o'tishi belgilar, svetofor yoki 'o'ng qo'l' "
                "qoidasi bilan aniqlanadi.",
                "Teng ahamiyatli chorrahada o'ngdan kelayotgan transportga yo'l beriladi; "
                "bosh yo'ldagi transport ustunlikka ega.",
                "Belgilar bo'lmagan teng chorrahada o'ngingizdagi mashinaga yo'l bering.",
                "chapga burilishda qarshidan to'g'ri ketayotgan transportga yo'l bermaslik.",
                "Ishonchingiz komil bo'lmasa — o'ngdagiga yo'l bering.",
            ),
        },
    },
    {
        "slug": "tezlik", "old": None,
        "title": "Tezlik", "subtitle": "Tezlik chegaralari va xavfsiz masofa",
        "topic": Topic.SPEED_DISTANCE, "position": 6,
        "article": {
            "slug": "tezlik-va-masofa", "kind": "lesson",
            "title": "Tezlik va masofa",
            "summary": "Tezlikni sharoitga moslash va old transport bilan masofa.",
            "blocks": _lesson_blocks(
                "Tezlik yo'l sharoiti, ko'rinish va harakat zichligiga mos bo'lishi kerak; "
                "belgilar tezlikni cheklaydi.",
                "Aholi punktlarida tezlik cheklangan; ruxsat etilgan eng katta tezlikdan "
                "oshmaslik shart.",
                "Old transport bilan xavfsiz masofani saqlang — tezlik oshgani sari "
                "masofa ham oshiriladi.",
                "ruxsat etilgan tezlikni 'hamma shunday yuradi' deb oshirib yuborish.",
                "Xavfsiz masofa — favqulodda to'xtashga yetadigan oraliq.",
            ),
        },
    },
    {
        "slug": "quvib-otish", "old": None,
        "title": "Quvib o'tish", "subtitle": "Xavfsiz quvib o'tish shartlari",
        "topic": Topic.OVERTAKING, "position": 7,
        "article": {
            "slug": "quvib-otish-asosi", "kind": "lesson",
            "title": "Quvib o'tish qoidalari",
            "summary": "Quvib o'tish qachon taqiqlanadi va qanday xavfsiz bajariladi.",
            "blocks": _lesson_blocks(
                "Quvib o'tish — eng xavfli manevrlardan biri; faqat to'liq xavfsiz "
                "bo'lganda bajariladi.",
                "Piyodalar o'tish joyi, chorraha, ko'prik va temir yo'l kesishmasi kabi "
                "joylarda quvib o'tish taqiqlanadi.",
                "Qarshi oqim va orqadagi vaziyatni baholab, yetarli joy borligiga "
                "ishonch hosil qiling.",
                "uzluksiz chiziq yoki piyodalar o'tish joyida quvib o'tishga urinish.",
                "Shubha bo'lsa — quvib o'tmang.",
            ),
        },
    },
    {
        "slug": "toxtash-toxtab-turish", "old": None,
        "title": "To'xtash va to'xtab turish", "subtitle": "Ruxsat etilgan va taqiqlangan joylar",
        "topic": Topic.STOPPING_PARKING, "position": 8,
        "article": {
            "slug": "toxtash-toxtab-turish-asosi", "kind": "lesson",
            "title": "To'xtash va to'xtab turish",
            "summary": "To'xtash taqiqlangan joylar va transportni xavfsiz qoldirish.",
            "blocks": _lesson_blocks(
                "To'xtash — qisqa muddatli, to'xtab turish — uzoqroq; ikkalasi ham faqat "
                "ruxsat etilgan joylarda amalga oshiriladi.",
                "Piyodalar o'tish joyida va unga yaqin masofada, chorrahalarda hamda "
                "ko'rinishni to'sadigan joylarda to'xtash taqiqlanadi.",
                "Transportni tark etayotganda uni o'z-o'zidan harakatlanishdan saqlang "
                "(tormoz, uzatma).",
                "o'tish joyi yoki chorraha yaqinida 'bir daqiqaga' to'xtash.",
                "To'xtashdan oldin o'zingizga savol bering: xavfsizmi, boshqalarga "
                "xalaqit bermaydimi?",
            ),
        },
    },
    {
        "slug": "piyodalar", "old": None,
        "title": "Piyodalar", "subtitle": "Piyodalar, velosipedchilar va bolalar",
        "topic": Topic.VULNERABLE_USERS, "position": 9,
        "article": {
            "slug": "piyodalar-asosi", "kind": "lesson",
            "title": "Piyodalar va himoyasiz qatnashchilar",
            "summary": "O'tish joyida yo'l berish va bolalar yonida ehtiyot.",
            "blocks": _lesson_blocks(
                "Piyodalar, velosipedchilar va bolalar yo'lning eng himoyasiz "
                "qatnashchilaridir.",
                "Belgilangan o'tish joyida piyodaga yo'l berish shart; kerak bo'lsa to'xtang.",
                "Bolalar guruhi yaqinida tezlikni pasaytiring — ular kutilmaganda yo'lga "
                "chiqishi mumkin.",
                "o'tish joyida piyodani kutmasdan signal berib o'tib ketish.",
                "Piyoda o'tayotganda — sabr qiling va yo'l bering.",
            ),
        },
    },
    {
        "slug": "temir-yol-kesishmalari", "old": None,
        "title": "Temir yo'l kesishmalari", "subtitle": "Poyezd har doim ustun",
        "topic": Topic.RAILWAY_CROSSINGS, "position": 10,
        "article": {
            "slug": "temir-yol-kesishmalari-asosi", "kind": "lesson",
            "title": "Temir yo'l kesishmalari",
            "summary": "Shlagbaum, qizil chiroq va majburiy to'xtashda harakat.",
            "blocks": _lesson_blocks(
                "Temir yo'l kesishmasi — poyezd har doim ustun bo'lgan yuqori xavfli joy.",
                "Shlagbaum yopilayotganda yoki qizil chiroq yonganda to'xtash chizig'i yoki "
                "shlagbaum oldida to'xtash shart.",
                "Kesishmada majburan to'xtab qolsangiz — avval odamlarni tushiring, "
                "so'ng ogohlantirish choralarini ko'ring.",
                "shlagbaum tushayotganda 'ulguraman' deb o'tib ketishga urinish.",
                "Poyezd bilan hech qachon bahslashmang — kuting.",
            ),
        },
    },
    {
        "slug": "favqulodda-vaziyatlar", "old": None,
        "title": "Favqulodda vaziyatlar", "subtitle": "Yo'l-transport hodisasida harakat",
        "topic": Topic.EMERGENCIES_FIRST_AID, "position": 11,
        "article": {
            "slug": "favqulodda-vaziyatlar-asosi", "kind": "lesson",
            "title": "Favqulodda vaziyatlar va yo'l-transport hodisasi",
            "summary": "YTH yuz berganda qonuniy va xavfsiz harakat tartibi.",
            "blocks": _lesson_blocks(
                "Yo'l-transport hodisasi (YTH) yuz berganda to'g'ri va tinch harakat qilish "
                "qo'shimcha xavfning oldini oladi.",
                "Hodisa ishtirokchisi transportni to'xtatishi, avariya signalizatsiyasini "
                "yoqishi, avariya to'xtash belgisini qo'yishi va hodisa joyini tark etmasligi "
                "shart; zarur bo'lsa tez yordam (103) va militsiyani (102) chaqirishi kerak.",
                "Avval hodisa joyini xavfsizlantiring (signalizatsiya va belgi), so'ng "
                "zarur xizmatlarni chaqiring.",
                "hodisa joyini tark etish yoki dalillarni o'zgartirish.",
                "Tartib: To'xta -> Ogohlantir -> Yordam chaqir -> Joyni saqla.",
            ),
        },
    },
    {
        "slug": "birinchi-yordam", "old": "demo-birinchi-yordam",
        "title": "Birinchi yordam", "subtitle": "Qonuniy majburiyatlar (tibbiy qism ko'rikda)",
        "topic": Topic.EMERGENCIES_FIRST_AID, "position": 12,
        # First-aid: legal (non-medical) obligations + explicit medically-reviewed-pending note.
        "article": {
            "slug": "birinchi-yordam-qonuniy", "kind": "reference",
            "title": "Birinchi yordam: qonuniy majburiyatlar (tibbiy qism ko'rikdan o'tkazilmoqda)",
            "summary": "YTH'dan keyingi qonuniy (notibbiy) majburiyatlar. Tibbiy amallar "
                       "malakali mutaxassis tasdig'ini kutmoqda.",
            "blocks": [
                theory_admin.BlockInput(
                    type="text",
                    body="Ushbu bo'lim yo'l-transport hodisasidan keyingi qonuniy (notibbiy) "
                         "majburiyatlarni yoritadi. Batafsil tibbiy birinchi yordam "
                         "ko'rsatmalari malakali tibbiy mutaxassis tomonidan tasdiqlanmaguncha "
                         "bu yerga kiritilmaydi.",
                ),
                theory_admin.BlockInput(
                    type="rule_callout",
                    body="Hodisa ishtirokchisi jabrlanganlarga yordam uyushtirishi, tez "
                         "yordam (103) va zarur bo'lsa militsiyani (102) chaqirishi, hodisa "
                         "joyini tark etmasligi shart.",
                    rule_code=_RULE_CODE,
                ),
                theory_admin.BlockInput(
                    type="warning",
                    body="Diqqat: bu bo'limda tibbiy amallar (bog'lash, jonlantirish va "
                         "boshqalar) bo'yicha aniq ko'rsatmalar berilmagan — ushbu kontent "
                         "tibbiy jihatdan ko'rikdan o'tkazilmoqda. Malakasiz tibbiy aralashuv "
                         "zarar yetkazishi mumkin; shubha bo'lsa, 103 ga qo'ng'iroq qilib "
                         "operator ko'rsatmalariga amal qiling.",
                ),
                theory_admin.BlockInput(
                    type="example",
                    body="Jabrlangan odamni faqat yong'in yoki portlash kabi bevosita xavf "
                         "bo'lgandagina va katta ehtiyotkorlik bilan harakatlantiring.",
                ),
                theory_admin.BlockInput(
                    type="memory_tip",
                    body="Eng muhim va eng xavfsiz qadam — tez yordamni (103) darhol chaqirish.",
                ),
            ],
        },
    },
]


# --------------------------------------------------------------------------- #
# S1 gestures
# --------------------------------------------------------------------------- #
GESTURES = [
    {
        "code": "R1", "position": 1, "name": "Qo'llar yon tomonga uzatilgan yoki tushirilgan",
        "position_desc": "Regulirovshchik qo'llarini ikki yon tomonga uzatib turadi yoki tushiradi.",
        "allowed": "Yon (yelka) tomondan: tramvayga — to'g'riga; boshqa transportga — "
                   "to'g'riga va o'ngga harakatlanish mumkin.",
        "forbidden": "Ko'krak va orqa tomondan har qanday harakat taqiqlanadi.",
        "memory_tip": "Yelka tomoni — 'yo'l ochiq', ko'krak va orqa — 'to'xta'.",
        "keywords": "regulirovshchik qo'l yon yelka ko'krak to'xta",
    },
    {
        "code": "R2", "position": 2, "name": "O'ng qo'l oldinga uzatilgan",
        "position_desc": "Regulirovshchik o'ng qo'lini oldinga uzatadi.",
        "allowed": "Chap tomondan barcha yo'nalishda; ko'krak tomondan faqat o'ngga burilish.",
        "forbidden": "O'ng tomondan va orqa tomondan harakat taqiqlanadi.",
        "memory_tip": "Chap tomondagilar uchun yo'l keng ochiladi, ko'krak tomon — faqat o'ngga.",
        "keywords": "regulirovshchik o'ng qo'l oldinga burilish",
    },
    {
        "code": "R3", "position": 3, "name": "Qo'l yuqoriga ko'tarilgan",
        "position_desc": "Regulirovshchik bir qo'lini tik yuqoriga ko'taradi.",
        "allowed": "Hech qanday yo'nalishda harakat mumkin emas (favqulodda to'xtay olmaslik "
                   "holatidan tashqari).",
        "forbidden": "Barcha yo'nalishda harakat taqiqlanadi.",
        "memory_tip": "Qo'l tepada — svetoforning sarig'iga o'xshaydi: 'to'xta va kut'.",
        "keywords": "regulirovshchik qo'l tepa yuqori to'xta",
    },
    {
        "code": "R4", "position": 4, "name": "Tayoqcha yoki qo'l bilan aniq yo'nalish ko'rsatish",
        "position_desc": "Regulirovshchik tayoqcha yoki qo'li bilan muayyan haydovchiga "
                         "yo'nalish ko'rsatadi.",
        "allowed": "Ko'rsatilgan haydovchi faqat ko'rsatilgan yo'nalishda harakatlanadi.",
        "forbidden": "Ko'rsatilgan yo'nalishdan boshqa tomonga o'zboshimchalik bilan yurish.",
        "memory_tip": "Shaxsan sizga ishora qilinsa — aynan ko'rsatilgan tomonga yuring.",
        "keywords": "regulirovshchik tayoqcha ishora yo'nalish",
    },
]


# --------------------------------------------------------------------------- #
# S2 traffic lights
# --------------------------------------------------------------------------- #
LIGHTS = [
    {
        "kind": "main", "position": 1, "title": "Qizil chiroq",
        "meaning": "Qizil chiroq harakatni taqiqlaydi.",
        "movement_permitted": "Harakat taqiqlanadi — to'xtash chizig'i oldida to'xtang.",
        "keywords": "svetofor qizil to'xta",
    },
    {
        "kind": "main", "position": 2, "title": "Qizil va sariq chiroq birga",
        "meaning": "Qizil va sariq birga yonishi tez orada yashil yonishidan xabar beradi, "
                   "lekin hali harakat taqiqlanadi.",
        "movement_permitted": "Harakat taqiqlanadi — yashil signalni kuting.",
        "keywords": "svetofor qizil sariq kutish",
    },
    {
        "kind": "main", "position": 3, "title": "Yashil chiroq",
        "meaning": "Yashil chiroq harakatga ruxsat beradi.",
        "movement_permitted": "Yo'l bo'sh va xavfsiz bo'lsa harakatlanish mumkin.",
        "direction_permitted": "Qo'shimcha strelka bo'lmasa — barcha ruxsat etilgan yo'nalishlarda.",
        "keywords": "svetofor yashil harakat ruxsat",
    },
    {
        "kind": "main", "position": 4, "title": "Yashil chiroq miltillayapti",
        "meaning": "Miltillovchi yashil harakatga ruxsat beradi, ammo tez orada taqiqlovchi "
                   "signal yonishidan ogohlantiradi.",
        "movement_permitted": "Harakat mumkin, lekin to'xtashga tayyor turing.",
        "keywords": "svetofor yashil miltillovchi ogohlantirish",
    },
    {
        "kind": "main", "position": 5, "title": "Sariq chiroq",
        "meaning": "Sariq chiroq harakatni taqiqlaydi va signal rejimi o'zgarishidan ogohlantiradi.",
        "movement_permitted": "Harakat taqiqlanadi (xavfsiz to'xtay olmaslik holatidan tashqari).",
        "keywords": "svetofor sariq taqiq ogohlantirish",
    },
    {
        "kind": "flashing", "position": 6, "title": "Sariq chiroq miltillayapti",
        "meaning": "Miltillovchi sariq chorraha svetofor bilan tartibga solinmaganini bildiradi.",
        "movement_permitted": "Ehtiyotkorlik bilan, belgilar va ustunlik qoidalariga rioya "
                              "qilib harakatlaning.",
        "typical_exam_situation": "Miltillovchi sariqda chorrahani belgilar yoki 'o'ng qo'l' "
                                  "qoidasi bo'yicha o'tasiz.",
        "keywords": "svetofor sariq miltillovchi tartibga solinmagan",
    },
]


# --------------------------------------------------------------------------- #
# S3 road markings
# --------------------------------------------------------------------------- #
MARKINGS = [
    {
        "group": "horizontal", "code": "1.1", "name": "Uzluksiz chiziq",
        "meaning": "Qarama-qarshi oqimlarni yoki qatorlarni ajratadi hamda yo'l chekkasini "
                   "belgilaydi.",
        "can_cross": "Yo'q — kesib o'tish taqiqlanadi.",
        "keywords": "uzluksiz chiziq razmetka ajratuvchi",
    },
    {
        "group": "horizontal", "code": "1.2", "name": "Yo'l chekkasi chizig'i",
        "meaning": "Yo'l qatlamining chekkasini bildiruvchi uzluksiz chiziq.",
        "can_cross": "Faqat ruxsat etilgan joyda to'xtash uchun kesish mumkin.",
        "keywords": "chekka chiziq razmetka",
    },
    {
        "group": "horizontal", "code": "1.3", "name": "Ikkita uzluksiz chiziq",
        "meaning": "To'rt va undan ortiq qatorli yo'llarda qarama-qarshi oqimlarni ajratadi.",
        "can_cross": "Yo'q — kesib o'tish taqiqlanadi.",
        "keywords": "ikkita uzluksiz chiziq razmetka",
    },
    {
        "group": "horizontal", "code": "1.5", "name": "Uzuq-uzuq chiziq",
        "meaning": "Qarama-qarshi oqimlarni yoki qatorlarni ajratadi (chiziqlar oralig'i uzun).",
        "can_cross": "Ha — xavfsiz bo'lganda kesish mumkin.",
        "keywords": "uzuq chiziq razmetka qator",
    },
    {
        "group": "horizontal", "code": "1.6", "name": "Yaqinlashuv chizig'i",
        "meaning": "Uzluksiz chiziqqa yaqinlashayotganidan ogohlantiruvchi uzun shtrixli chiziq.",
        "can_cross": "Ha, lekin tez orada uzluksiz chiziq boshlanadi.",
        "keywords": "yaqinlashuv chiziq ogohlantirish razmetka",
    },
    {
        "group": "horizontal", "code": "1.12", "name": "To'xtash chizig'i",
        "meaning": "'STOP' belgisi yoki svetofor talabida transport qayerda to'xtashini "
                   "ko'rsatadi.",
        "can_cross": "To'xtash talab qilinganda chiziq kesib o'tilmaydi.",
        "keywords": "to'xtash chizig'i stop line razmetka",
    },
    {
        "group": "horizontal", "code": "1.14.1", "name": "Piyodalar o'tish joyi (zebra)",
        "meaning": "Piyodalar yo'lni kesib o'tadigan joyni belgilaydi.",
        "can_cross": "Piyoda o'tayotganda unga yo'l berish shart.",
        "keywords": "zebra piyoda o'tish joyi razmetka",
    },
    {
        "group": "horizontal", "code": "1.18", "name": "Yo'nalish strelkalari",
        "meaning": "Har bir qatordan ruxsat etilgan harakat yo'nalishini ko'rsatadi.",
        "can_cross": "Qatordagi strelkaga mos yo'nalishda harakatlaning.",
        "keywords": "strelka yo'nalish qator razmetka",
    },
    {
        "group": "vertical", "code": "2.1", "name": "Vertikal chiziqlar (inshoot qirralari)",
        "meaning": "Yo'l inshootlari (ko'prik ustunlari, to'siqlar) qirralarini ajratib "
                   "ko'rsatadi.",
        "can_cross": "Kesib o'tishga taalluqli emas — ko'rinishni oshiradi.",
        "keywords": "vertikal razmetka to'siq ko'prik qirra",
    },
    {
        "group": "vertical", "code": "2.4", "name": "Yo'naltiruvchi ustunchalar belgilanishi",
        "meaning": "Yo'naltiruvchi ustunchalarga tushiriladigan vertikal belgilash.",
        "can_cross": "Kesib o'tishga taalluqli emas — yo'nalishni ko'rsatadi.",
        "keywords": "vertikal razmetka ustuncha yo'naltiruvchi",
    },
]


# --------------------------------------------------------------------------- #
# S5 sections + articles
# --------------------------------------------------------------------------- #
def _set_section_translation(db: Session, section_id: str, title: str, subtitle: str) -> None:
    tr = db.scalar(
        select(TheorySectionTranslation).where(
            TheorySectionTranslation.section_id == section_id,
            TheorySectionTranslation.language == _LANG,
        )
    )
    if tr is None:
        db.add(
            TheorySectionTranslation(
                section_id=section_id, language=_LANG, title=title, subtitle=subtitle
            )
        )
    else:
        tr.title = title
        tr.subtitle = subtitle
    db.flush()


def _ensure_section(db: Session, author: User, spec: dict) -> TheorySection:
    section = db.scalar(select(TheorySection).where(TheorySection.slug == spec["slug"]))
    if section is None and spec.get("old"):
        section = db.scalar(select(TheorySection).where(TheorySection.slug == spec["old"]))
        if section is not None:
            section.slug = spec["slug"]  # normalise demo-* slug -> production slug
            db.flush()
    if section is None:
        section = theory_admin.create_section(
            db, author, slug=spec["slug"], title=spec["title"], subtitle=spec["subtitle"],
            topic=spec["topic"].value, position=spec["position"],
        )
    # Normalise display text (drops any "(DEMO)" in title/subtitle) + publish.
    _set_section_translation(db, section.id, spec["title"], spec["subtitle"])
    if section.status != VersionStatus.PUBLISHED:
        theory_admin.publish_section(db, author, section.id)
    db.commit()
    return section


def _author_article(db: Session, author: User, section: TheorySection, spec: dict) -> str:
    art_spec = spec["article"]
    existing = db.scalar(
        select(TheoryArticle).where(
            TheoryArticle.section_id == section.id,
            TheoryArticle.slug == art_spec["slug"],
        )
    )
    if (
        existing is not None
        and existing.lifecycle_status == VersionStatus.PUBLISHED
        and existing.current_version_id is not None
    ):
        return "skipped"

    qids = _published_question_ids_for_topic(db, spec["topic"])
    if not qids:
        log_event("seed_theory_prod_article_no_questions", slug=art_spec["slug"],
                  topic=spec["topic"].value)

    if existing is None:
        version = theory_admin.create_article(
            db, author, section_id=section.id, slug=art_spec["slug"],
            kind=art_spec["kind"], position=1,
        )
        article_id = version.article_id
    else:
        article_id = existing.id

    blocks = list(art_spec["blocks"])
    if qids:
        blocks.append(
            theory_admin.BlockInput(
                type="practice_link",
                body="Bu mavzu bo'yicha savollar bilan mashq qiling.",
                ref_question_id=qids[0],
            )
        )
    content = theory_admin.ArticleContentInput(
        title=art_spec["title"], summary=art_spec["summary"], ai_assisted=True,
        blocks=blocks, rule_codes=[_RULE_CODE], question_ids=qids,
    )
    version = theory_admin.edit_article(db, author, article_id, content)
    _publish_article(db, author, version)
    return "created"


# --------------------------------------------------------------------------- #
# S7 archive DEMO artefacts (prod-safe: no deletes; excluded from published reads)
# --------------------------------------------------------------------------- #
def _archive_versions(db: Session, model, fk_attr: str, container_id: str) -> None:
    for v in db.scalars(select(model).where(getattr(model, fk_attr) == container_id)):
        if v.status == VersionStatus.PUBLISHED:
            v.status = VersionStatus.ARCHIVED


def _archive_demo(db: Session) -> dict:
    archived = {"articles": 0, "markings": 0, "gestures": 0, "lights": 0}

    # Articles whose (published) title carries a DEMO marker.
    for tr in db.scalars(
        select(TheoryArticleTranslation).where(
            TheoryArticleTranslation.language == _LANG,
            TheoryArticleTranslation.title.ilike("%DEMO%"),
        )
    ):
        version = db.get(TheoryArticleVersion, tr.article_version_id)
        if version is None:
            continue
        article = db.get(TheoryArticle, version.article_id)
        if article is None or article.lifecycle_status != VersionStatus.PUBLISHED:
            continue
        article.lifecycle_status = VersionStatus.ARCHIVED
        _archive_versions(db, TheoryArticleVersion, "article_id", article.id)
        archived["articles"] += 1

    # Markings with a DEMO code.
    for m in db.scalars(select(RoadMarking).where(RoadMarking.lifecycle_status == VersionStatus.PUBLISHED)):
        if m.code and "DEMO" in m.code.upper():
            m.lifecycle_status = VersionStatus.ARCHIVED
            _archive_versions(db, RoadMarkingVersion, "road_marking_id", m.id)
            archived["markings"] += 1

    # Gestures with a DEMO code.
    for g in db.scalars(select(ControllerGesture).where(ControllerGesture.lifecycle_status == VersionStatus.PUBLISHED)):
        if g.code and "DEMO" in g.code.upper():
            g.lifecycle_status = VersionStatus.ARCHIVED
            _archive_versions(db, ControllerGestureVersion, "gesture_id", g.id)
            archived["gestures"] += 1

    # Lights whose (published) title carries a DEMO marker.
    for light in db.scalars(select(TrafficLightState).where(TrafficLightState.lifecycle_status == VersionStatus.PUBLISHED)):
        if not light.current_version_id:
            continue
        tr = db.scalar(
            select(TrafficLightStateTranslation).where(
                TrafficLightStateTranslation.light_version_id == light.current_version_id,
                TrafficLightStateTranslation.language == _LANG,
            )
        )
        if tr and tr.title and "DEMO" in tr.title.upper():
            light.lifecycle_status = VersionStatus.ARCHIVED
            _archive_versions(db, TrafficLightStateVersion, "light_id", light.id)
            archived["lights"] += 1

    db.commit()
    return archived


# --------------------------------------------------------------------------- #
# S1/S2/S3 catalogue seeding (idempotent)
# --------------------------------------------------------------------------- #
def _seed_gestures(db: Session, author: User) -> int:
    created = 0
    for spec in GESTURES:
        existing = db.scalar(
            select(ControllerGesture).where(
                ControllerGesture.code == spec["code"],
                ControllerGesture.lifecycle_status == VersionStatus.PUBLISHED,
            )
        )
        if existing is not None:
            continue
        v = theory_admin.create_gesture(db, author, code=spec["code"], position=spec["position"])
        v = theory_admin.edit_gesture(
            db, author, v.gesture_id,
            theory_admin.GestureContentInput(
                name=spec["name"], position_desc=spec["position_desc"], allowed=spec["allowed"],
                forbidden=spec["forbidden"], memory_tip=spec["memory_tip"],
                keywords=spec["keywords"], ai_assisted=True, rule_codes=[_RULE_CODE],
            ),
        )
        _publish_gesture(db, author, v)
        created += 1
    return created


def _seed_lights(db: Session, author: User) -> int:
    created = 0
    for spec in LIGHTS:
        exists = db.scalar(
            select(TrafficLightStateTranslation)
            .join(
                TrafficLightState,
                TrafficLightState.current_version_id
                == TrafficLightStateTranslation.light_version_id,
            )
            .where(
                TrafficLightState.lifecycle_status == VersionStatus.PUBLISHED,
                TrafficLightStateTranslation.language == _LANG,
                TrafficLightStateTranslation.title == spec["title"],
            )
        )
        if exists is not None:
            continue
        v = theory_admin.create_light(db, author, kind=spec["kind"], position=spec["position"])
        v = theory_admin.edit_light(
            db, author, v.light_id,
            theory_admin.LightContentInput(
                title=spec["title"], meaning=spec["meaning"],
                movement_permitted=spec.get("movement_permitted"),
                direction_permitted=spec.get("direction_permitted"),
                typical_exam_situation=spec.get("typical_exam_situation"),
                keywords=spec["keywords"], ai_assisted=True, rule_codes=[_RULE_CODE],
            ),
        )
        _publish_light(db, author, v)
        created += 1
    return created


def _seed_markings(db: Session, author: User) -> int:
    created = 0
    for spec in MARKINGS:
        existing = db.scalar(
            select(RoadMarking).where(
                RoadMarking.code == spec["code"],
                RoadMarking.lifecycle_status == VersionStatus.PUBLISHED,
            )
        )
        if existing is not None:
            continue
        v = theory_admin.create_marking(db, author, group=spec["group"], code=spec["code"])
        v = theory_admin.edit_marking(
            db, author, v.road_marking_id,
            theory_admin.MarkingContentInput(
                name=spec["name"], meaning=spec["meaning"], can_cross=spec["can_cross"],
                keywords=spec["keywords"], ai_assisted=True, rule_codes=[_RULE_CODE],
            ),
        )
        _publish_marking(db, author, v)
        created += 1
    return created


def run() -> dict:
    configure_logging()
    with session_scope() as db:
        author = ensure_seed_author(db)
        _ensure_rule(db, author)
        db.commit()

        # S7 (part 1): archive leftover DEMO catalogue/article artefacts first.
        archived = _archive_demo(db)

        # S1/S2/S3 catalogues.
        gestures_created = _seed_gestures(db, author)
        lights_created = _seed_lights(db, author)
        markings_created = _seed_markings(db, author)

        # S5 sections + real lesson articles; S6 topic-matched question links.
        sections_ensured = 0
        articles_created = 0
        for spec in CORE_SECTIONS:
            section = _ensure_section(db, author, spec)
            sections_ensured += 1
            if _author_article(db, author, section, spec) == "created":
                articles_created += 1

        # S7 (part 2): re-sweep in case demo articles were (re)published between runs.
        archived2 = _archive_demo(db)
        for k in archived:
            archived[k] += archived2[k]

        result = {
            "sections_ensured": sections_ensured,
            "articles_created": articles_created,
            "gestures_created": gestures_created,
            "lights_created": lights_created,
            "markings_created": markings_created,
            "demo_archived": archived,
        }
        log_event("seed_theory_production_completed", **result)
        return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
