"""Seed original (authored) YHQ practice questions across topics.

Content policy: these are ORIGINAL questions authored for prava-bot. Their correct answers
hold by standard road-traffic norms so they never teach anything wrong; they are still
demo/training content (ai_assisted) and should be reviewed against the current official YHQ
before a production launch. Text only (no images). Idempotent by prompt.

Usage:  python -m app.scripts.seed_invented_questions
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.domain.enums import AdminRole, Category, Language, Topic, VersionStatus
from app.domain.models import Question, QuestionVersion, QuestionVersionTranslation, User
from app.observability.logging import configure_logging, log_event
from app.services import rules_admin
from app.services.content_source import OptionDraft, QuestionDraft
from app.services.ingestion import publish_question
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"
_RULE_CODE = "YHQ"


def _o(text, correct, expl):
    return (text, correct, expl)


# (topic, prompt, [(text, is_correct, explanation)], short_explanation, difficulty)
QUESTIONS = [
    (Topic.SIGNALS, "Svetoforning qizil chirog'i yonganda haydovchi nima qilishi kerak?",
     [_o("To'xtash chizig'i oldida to'xtashi kerak", True, "Qizil chiroq harakatni taqiqlaydi — to'xtash shart."),
      _o("Ehtiyotkorlik bilan davom etishi mumkin", False, "Qizil chiroqda harakat taqiqlanadi."),
      _o("Tezlikni oshirib o'tib ketishi kerak", False, "Bu xavfli va taqiqlangan."),
      _o("Faqat signal berib o'tishi mumkin", False, "Signal qizil chiroqda o'tish huquqini bermaydi.")],
     "Qizil chiroq — to'xtash.", 1),
    (Topic.SIGNALS, "Svetoforning sariq chirog'i (qizildan keyin emas) nimani bildiradi?",
     [_o("Harakatni taqiqlaydi va rejim o'zgarishidan ogohlantiradi", True, "Sariq chiroq harakatni taqiqlaydi (favqulodda to'xtay olmaslik holatidan tashqari)."),
      _o("Harakatni ruxsat etadi", False, "Sariq chiroq ruxsat bermaydi."),
      _o("Tezlashtirishga chaqiradi", False, "Aksincha, to'xtashga tayyorlaydi."),
      _o("Hech qanday ma'noga ega emas", False, "Sariq chiroqning aniq ma'nosi bor.")],
     "Sariq — taqiq + ogohlantirish.", 2),
    (Topic.SIGNALS, "Regulirovshchik qo'llarini yon tomonga uzatib turibdi. Uning ko'kragi tomonidagi haydovchi uchun bu nimani bildiradi?",
     [_o("Harakat taqiqlanadi", True, "Regulirovshchik ko'kragi/orqasi tomondan harakat taqiqlanadi."),
      _o("To'g'riga va o'ngga harakat mumkin", False, "Bu yon (yelka) tomon uchun amal qiladi."),
      _o("Faqat o'ngga burilish mumkin", False, "Ko'krak tomondan harakat umuman taqiqlanadi."),
      _o("Tezlikni oshirish kerak", False, "Bunday ma'no yo'q.")],
     "Ko'krak/orqa tomon — to'xta.", 3),
    (Topic.INTERSECTIONS, "Teng ahamiyatli chorrahada (belgilar yo'q) o'ngdan kelayotgan transport bo'lsa, kim yo'l beradi?",
     [_o("O'ng tomonda to'siq (transport) bo'lganda unga yo'l beriladi", True, "Teng yo'llarda o'ng qo'l qoidasi amal qiladi."),
      _o("Har doim chapdagi o'tadi", False, "Aksincha — o'ngdagiga yo'l beriladi."),
      _o("Kattaroq transport o'tadi", False, "O'lcham imtiyoz bermaydi."),
      _o("Tez kelayotgan o'tadi", False, "Tezlik imtiyoz bermaydi.")],
     "Teng chorraha — o'ng qo'l qoidasi.", 2),
    (Topic.INTERSECTIONS, "Bosh yo'l va ikkilamchi yo'l kesishmasida ikkilamchi yo'ldagi haydovchi nima qiladi?",
     [_o("Bosh yo'ldagi transportga yo'l beradi", True, "Ikkilamchi yo'l bosh yo'lga yo'l beradi."),
      _o("Imtiyozga ega bo'ladi", False, "Imtiyoz bosh yo'lda."),
      _o("To'xtamasdan o'tadi", False, "Yo'l berish talab qilinadi."),
      _o("Faqat kechasi yo'l beradi", False, "Vaqtga bog'liq emas.")],
     "Ikkilamchi yo'l — bosh yo'lga yo'l beradi.", 1),
    (Topic.INTERSECTIONS, "Chorrahada chapga burilishda haydovchi kimga yo'l berishi kerak?",
     [_o("Qarama-qarshi to'g'riga va o'ngga ketayotganlarga", True, "Chapga burilishda qarshi to'g'ri/o'ng harakatga yo'l beriladi."),
      _o("Hech kimga", False, "Chapga burilishda yo'l berish talabi bor."),
      _o("Faqat piyodalarga", False, "Piyodalardan tashqari qarshi transportga ham."),
      _o("Orqadagi transportga", False, "Orqadagi transport bu holatda hal qiluvchi emas.")],
     "Chapga burilish — qarshi oqimga yo'l ber.", 2),
    (Topic.SPEED_DISTANCE, "Aholi punktlarida (agar belgi bilan boshqacha ko'rsatilmagan bo'lsa) umumiy tezlik chegarasi odatda qanday bo'ladi?",
     [_o("Pasaytirilgan shahar tezligi — belgilarga rioya qilish kerak", True, "Aholi punktida tezlik cheklangan; aniq qiymat belgilar bilan ko'rsatiladi."),
      _o("Cheklov umuman yo'q", False, "Aholi punktida har doim cheklov bor."),
      _o("Istalgan tezlik mumkin", False, "Xavfsiz va cheklangan tezlik talab qilinadi."),
      _o("Faqat kechasi cheklanadi", False, "Cheklov doimiy.")],
     "Aholi punktida tezlik cheklangan.", 1),
    (Topic.SPEED_DISTANCE, "Old transport bilan xavfsiz masofa nimaga bog'liq?",
     [_o("Tezlik va yo'l sharoitiga", True, "Tezlik oshgani sari va yo'l yomonlashgani sari masofa oshiriladi."),
      _o("Faqat mashina rangiga", False, "Rang ahamiyatsiz."),
      _o("Yo'lovchilar soniga", False, "Bevosita bog'liq emas."),
      _o("Hech narsaga", False, "Masofa tezlik/sharoitga bog'liq.")],
     "Masofa tezlik va sharoitga bog'liq.", 1),
    (Topic.OVERTAKING, "Quyidagi joylarning qaysi birida quvib o'tish taqiqlanadi?",
     [_o("Piyodalar o'tish joyida", True, "O'tish joylarida quvib o'tish taqiqlanadi."),
      _o("To'g'ri va keng yo'lda", False, "Bunday joyda ruxsat etilishi mumkin."),
      _o("Ochib berilgan yo'nalishda", False, "Ruxsat etilishi mumkin."),
      _o("Bo'sh magistralda", False, "Odatda ruxsat.")],
     "O'tish joyida quvib o'tish taqiqlanadi.", 2),
    (Topic.OVERTAKING, "Quvib o'tishdan oldin haydovchi avvalo nima qilishi kerak?",
     [_o("Qarshi va orqa vaziyatni baholab, xavfsizligiga ishonch hosil qilishi", True, "Quvib o'tish faqat xavfsiz bo'lganda amalga oshiriladi."),
      _o("Darhol chiqib ketishi", False, "Avval vaziyatni baholash shart."),
      _o("Signal berib majburlashi", False, "Signal xavfsizlikni ta'minlamaydi."),
      _o("Chiroqni o'chirishi", False, "Bu bilan bog'liq emas.")],
     "Avval xavfsizlikni baholang.", 1),
    (Topic.STOPPING_PARKING, "Piyodalar o'tish joyida to'xtab turish qoidasi qanday?",
     [_o("O'tish joyida va unga yaqin masofada to'xtash taqiqlanadi", True, "O'tish joyi ko'rinishini to'sib qo'yish xavfli."),
      _o("Istalgan vaqt to'xtash mumkin", False, "Taqiqlanadi."),
      _o("Faqat tunda mumkin", False, "Vaqtga bog'liq emas."),
      _o("Signal bersa mumkin", False, "Signal ruxsat bermaydi.")],
     "O'tish joyida to'xtash taqiqlanadi.", 2),
    (Topic.STOPPING_PARKING, "Yo'lda to'xtab turgan haydovchi transportni tark etganda nima qilishi kerak?",
     [_o("Uni o'z-o'zidan harakatlanishdan saqlash choralarini ko'rishi (tormoz)", True, "Transport g'ildiraydigan bo'lib qolmasligi kerak."),
      _o("Dvigatelni ishlab turgan holda qoldirishi", False, "Bu xavfli."),
      _o("Eshiklarni ochiq qoldirishi", False, "Xavf tug'diradi."),
      _o("Hech narsa", False, "Xavfsizlik choralari zarur.")],
     "Transportni tormozlab qoldiring.", 1),
    (Topic.VULNERABLE_USERS, "Piyodalar o'tish joyida piyoda o'tayotgan bo'lsa haydovchi nima qiladi?",
     [_o("Yo'l beradi (kerak bo'lsa to'xtaydi)", True, "Piyodaga o'tish joyida imtiyoz beriladi."),
      _o("Signal berib o'tib ketadi", False, "Piyodaga yo'l berish shart."),
      _o("Tezlikni oshiradi", False, "Xavfli."),
      _o("Piyodani kutmaydi", False, "Yo'l berish talab qilinadi.")],
     "O'tish joyida piyodaga yo'l bering.", 1),
    (Topic.VULNERABLE_USERS, "Bolalar guruhi yaqinida haydash qanday bo'lishi kerak?",
     [_o("Ayniqsa ehtiyotkor va tezlikni pasaytirgan holda", True, "Bolalar oldindan aytib bo'lmaydigan harakat qilishi mumkin."),
      _o("Odatdagidek", False, "Qo'shimcha ehtiyot zarur."),
      _o("Tezroq o'tib ketgan yaxshi", False, "Aksincha, sekinlashtiring."),
      _o("Signal berib haydash", False, "Bu yechim emas.")],
     "Bolalar yonida — extra ehtiyot.", 1),
    (Topic.RAILWAY_CROSSINGS, "Temir yo'l kesishmasida shlagbaum tushayotgan yoki qizil chiroq yonayotgan bo'lsa?",
     [_o("To'xtash chizig'i/shlagbaum oldida to'xtash shart", True, "Poyezd o'tishidan oldin harakat taqiqlanadi."),
      _o("Tez o'tib ketish kerak", False, "Juda xavfli va taqiqlangan."),
      _o("Signal berib o'tish mumkin", False, "Ruxsat etilmaydi."),
      _o("Chiroqqa e'tibor bermaslik", False, "Chiroqqa rioya shart.")],
     "Qizil/shlagbaum — to'xta.", 1),
    (Topic.RAILWAY_CROSSINGS, "Kesishmada transport to'xtab qolsa (majbliy), haydovchi birinchi navbatda nima qiladi?",
     [_o("Odamlarni tushirib, transportni bo'shatishga harakat qiladi va xavf haqida ogohlantiradi", True, "Avval odamlar xavfsizligi, keyin ogohlantirish."),
      _o("Transportda o'tirib kutadi", False, "Bu halokatli bo'lishi mumkin."),
      _o("Hech narsa qilmaydi", False, "Choralar zarur."),
      _o("Faqat suratga oladi", False, "Xavfsizlik birinchi.")],
     "Odamlarni chiqar, ogohlantir.", 3),
    (Topic.GENERAL_RULES, "Haydash paytida xavfsizlik kamari qoidasi qanday?",
     [_o("Haydovchi va yo'lovchilar taqib olishi kerak (o'rnatilgan bo'lsa)", True, "Kamar jarohat xavfini kamaytiradi."),
      _o("Faqat haydovchi taqadi", False, "Yo'lovchilar ham taqishi kerak."),
      _o("Faqat magistralda taqiladi", False, "Doimiy talab."),
      _o("Umuman shart emas", False, "Kamar taqish talab qilinadi.")],
     "Kamar — hamma uchun.", 1),
    (Topic.GENERAL_RULES, "Haydovchi spirtli ichimlik iste'mol qilgan holatda haydashi mumkinmi?",
     [_o("Yo'q, mast holda haydash qat'iyan taqiqlanadi", True, "Mastlik reaksiyani buzadi va halokatga olib keladi."),
      _o("Ozgina bo'lsa mumkin", False, "Har qanday mastlik taqiqlanadi."),
      _o("Faqat kechasi mumkin emas", False, "Har doim taqiqlanadi."),
      _o("Sekin haydasa mumkin", False, "Baribir taqiqlanadi.")],
     "Mast holda haydash taqiqlanadi.", 1),
    (Topic.MANOEUVRING, "Manevrdan (burilish, qator almashish) oldin haydovchi nima qilishi kerak?",
     [_o("Burilish ko'rsatkichi bilan signal berishi", True, "Signal boshqalarni niyatingizdan ogohlantiradi."),
      _o("Hech qanday signal bermasligi", False, "Signal berish shart."),
      _o("Faqat tovush signali berishi", False, "Burilish ko'rsatkichi kerak."),
      _o("Chiroqni o'chirishi", False, "Bu bilan bog'liq emas.")],
     "Manevrdan oldin signal bering.", 1),
    (Topic.MANOEUVRING, "Orqaga (teskari) yurishda qoida qanday?",
     [_o("Xavfsiz bo'lganda va boshqalarga xalaqit bermay bajariladi; kerak bo'lsa yordamchidan foydalaniladi", True, "Teskari yurish ko'rish cheklangani uchun ehtiyot talab qiladi."),
      _o("Chorraha va o'tish joylarida bemalol mumkin", False, "Bunday joylarda taqiqlanadi."),
      _o("Tez bajarish kerak", False, "Ehtiyotkorlik muhim."),
      _o("Signal shart emas", False, "Ehtiyot va kuzatuv zarur.")],
     "Teskari yurish — faqat xavfsiz bo'lsa.", 2),
    (Topic.ROAD_MARKINGS, "Uzluksiz (to'liq) chiziqni kesib o'tish mumkinmi?",
     [_o("Yo'q, uzluksiz chiziqni kesib o'tish taqiqlanadi", True, "Uzluksiz chiziq oqimlarni ajratadi."),
      _o("Ha, istalgan vaqt", False, "Taqiqlanadi."),
      _o("Faqat tunda", False, "Vaqtga bog'liq emas."),
      _o("Signal bersa", False, "Signal ruxsat bermaydi.")],
     "Uzluksiz chiziq — kesib o'tma.", 1),
    (Topic.ROAD_MARKINGS, "Belgi va chiziq bir-biriga zid bo'lsa, haydovchi qaysi biriga amal qiladi?",
     [_o("Yo'l belgisiga", True, "Ziddiyatda belgi ustunlikka ega."),
      _o("Chiziqqa", False, "Belgi ustun turadi."),
      _o("Ikkalasiga ham e'tibor bermaydi", False, "Belgiga amal qilinadi."),
      _o("O'zi xohlaganiga", False, "Belgi ustun.")],
     "Ziddiyatda belgi ustun.", 2),
    (Topic.VEHICLE_CONDITION, "Quyidagi nosozliklardan qaysi biri bilan harakatlanish taqiqlanadi?",
     [_o("Ishlamaydigan tormoz tizimi", True, "Tormoz nosozligi halokatli xavf tug'diradi."),
      _o("Salonda chang bo'lishi", False, "Xavfsizlikka ta'sir qilmaydi."),
      _o("Radio ishlamasligi", False, "Xavfsizlikka aloqasi yo'q."),
      _o("Rangi o'chgan bo'lishi", False, "Harakatni taqiqlamaydi.")],
     "Nosoz tormoz bilan haydash taqiq.", 1),
    (Topic.TRANSPORT_OF_PEOPLE_CARGO, "Yuk transport gabaritidan chiqib turganda haydovchi nima qiladi?",
     [_o("Uni belgilangan tartibda belgilaydi (kunduzi bayroqcha, tunda chiroq/qaytargich)", True, "Ko'rinuvchanlik xavfsizlik uchun zarur."),
      _o("Hech narsa qilmaydi", False, "Belgilash talab qilinadi."),
      _o("Tezroq yetkazadi", False, "Belgilash muhim."),
      _o("Yukni yashiradi", False, "Aksincha, ko'rinadigan qiladi.")],
     "Chiqib turgan yukni belgilang.", 2),
    (Topic.MOTORWAYS_SPECIAL, "Avtomagistralda quyidagilardan qaysi biri taqiqlanadi?",
     [_o("Piyodalar harakati va teskari yurish", True, "Magistralda piyoda va teskari yurish taqiqlanadi."),
      _o("Belgilangan tezlikda harakatlanish", False, "Bu ruxsat etiladi."),
      _o("Qatorlarni to'g'ri almashtirish", False, "Ruxsat etiladi."),
      _o("Xizmat joylarida to'xtash", False, "Maxsus joylarda mumkin.")],
     "Magistralda piyoda/teskari — taqiq.", 2),
    (Topic.EMERGENCIES_FIRST_AID, "Yo'l-transport hodisasidan so'ng haydovchining birinchi harakatlaridan biri qaysi?",
     [_o("Transportni to'xtatib, avariya signalizatsiyasini yoqib, joyni belgilash", True, "Bu qo'shimcha hodisaning oldini oladi."),
      _o("Joyni tark etib ketish", False, "Hodisa joyini tark etish taqiqlanadi."),
      _o("Dalillarni yo'q qilish", False, "Bu qonunbuzarlik."),
      _o("Hech kimni chaqirmaslik", False, "Zarur bo'lsa yordam chaqiriladi.")],
     "To'xta, ogohlantir, joyni belgila.", 2),
    (Topic.EMERGENCIES_FIRST_AID, "Birinchi yordamda dastlabki qadam nima (umumiy tamoyil)?",
     [_o("Voqea joyi xavfsizligini ta'minlash va zarur bo'lsa tez yordam chaqirish", True, "Avval xavfsizlik va yordam chaqirish."),
      _o("Jarohatlanganni darhol siltab yurgizish", False, "Bu holatni yomonlashtirishi mumkin."),
      _o("Hech narsa qilmay kutish", False, "Yordam chaqirish zarur."),
      _o("Dori berish", False, "Malakasiz dori berish tavsiya etilmaydi.")],
     "Xavfsizlik + tez yordam. (Tibbiy nazorat talab qilinadi.)", 2),
    (Topic.GENERAL_RULES, "Haydovchi qanday hujjatlarni o'zi bilan olib yurishi kerak (umumiy talab)?",
     [_o("Haydovchilik guvohnomasi va transport hujjatlari", True, "Bu hujjatlar tekshiruvda talab qilinadi."),
      _o("Faqat telefon", False, "Rasmiy hujjatlar kerak."),
      _o("Hech qanday hujjat", False, "Hujjatlar talab qilinadi."),
      _o("Faqat pasport", False, "Guvohnoma va transport hujjatlari kerak.")],
     "Guvohnoma + transport hujjatlari.", 1),
]


def ensure_seed_author(db) -> User:
    a = db.scalar(select(User).where(User.telegram_id == SEED_AUTHOR_TELEGRAM_ID))
    if a is None:
        a = User(telegram_id=SEED_AUTHOR_TELEGRAM_ID, first_name="Seed", last_name="Author",
                 admin_role=AdminRole.CONTENT_AUTHOR)
        db.add(a)
        db.flush()
    return a


def _ensure_rule(db, author):
    from app.domain.models import Rule
    r = db.scalar(select(Rule).where(Rule.code == _RULE_CODE))
    if r is not None:
        return r
    return rules_admin.create_rule(
        db, author, code=_RULE_CODE,
        text="Yo'l harakati qoidalari (umumiy). Aniq bandlar rasmiy manbadan tekshirilishi kerak.",
        title="YHQ", source_url="",
    )


def run() -> dict:
    configure_logging()
    created = 0
    skipped = 0
    with session_scope() as db:
        author = ensure_seed_author(db)
        _ensure_rule(db, author)
        existing = set(db.scalars(select(QuestionVersionTranslation.prompt)))
        for topic, prompt, opts, short, diff in QUESTIONS:
            if prompt in existing:
                skipped += 1
                continue
            draft = QuestionDraft(
                category=Category.B, topic=topic, prompt=prompt, short_explanation=short,
                options=[OptionDraft(text=t, is_correct=c, explanation=e) for (t, c, e) in opts],
                rule_code=_RULE_CODE, is_sign_question=False, difficulty=diff,
                ai_assisted=True, language=Language.UZ, sources=[],
            )
            try:
                publish_question(db, draft, author)
                created += 1
            except Exception as exc:  # noqa: BLE001
                log_event("invented_question_error", prompt=prompt[:40], error=str(exc))
    result = {"created": created, "skipped": skipped, "defined": len(QUESTIONS)}
    log_event("seed_invented_questions_completed", **result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
