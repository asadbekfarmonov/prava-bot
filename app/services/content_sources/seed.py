"""Manual/seed ContentSource: ORIGINAL demo questions for the v1 build.

These are original, demo questions authored for development — clearly marked
``ai_assisted`` with a demo source note. They are NEVER labelled as official exam
questions (docs/spec/00, 06, 11). A licensed bank, if obtained, feeds the SAME
ingestion path via a different adapter without any architecture change.
"""

from __future__ import annotations

from datetime import date

from app.domain.enums import Category, SourceKind, Topic
from app.services.content_source import (
    ContentSource,
    OptionDraft,
    QuestionDraft,
    RuleDraft,
    SourceRefDraft,
)

_VERIFIED = date(2026, 8, 31)
_DEMO_NOTE = "Original demo content authored for prava-bot v1 development — not an official exam question."


def _demo_source() -> list[SourceRefDraft]:
    return [SourceRefDraft(url="", note=_DEMO_NOTE, kind=SourceKind.OTHER)]


_RULES: list[RuleDraft] = [
    RuleDraft("YHQ:2.1", "Haydovchi yo'lda haydovchilik guvohnomasi va transport hujjatlarini olib yurishi shart.", title="Haydovchi majburiyatlari", verified_at=_VERIFIED),
    RuleDraft("YHQ:2.9", "Xavfsizlik kamari bilan jihozlangan avtomobilda haydovchi va yo'lovchilar kamarni taqishlari shart.", title="Xavfsizlik kamari", verified_at=_VERIFIED),
    RuleDraft("YHQ:3.1", "Ko'k rangdagi doira ichidagi belgilar buyuruvchi (majburiy) belgilardir.", title="Buyuruvchi belgilar", verified_at=_VERIFIED),
    RuleDraft("YHQ:3.2", "Uchburchak shaklidagi qizil hoshiyali belgilar ogohlantiruvchi belgilardir.", title="Ogohlantiruvchi belgilar", verified_at=_VERIFIED),
    RuleDraft("YHQ:4.1", "Uzluksiz chiziq qatorlarni ajratadi va uni kesib o'tish taqiqlanadi.", title="Yo'l belgilanishlari", verified_at=_VERIFIED),
    RuleDraft("YHQ:5.1", "Svetoforning qizil signali harakatni taqiqlaydi.", title="Svetofor signallari", verified_at=_VERIFIED),
    RuleDraft("YHQ:5.7", "Regulirovshchikning qo'llari yon tomonga yoyilgan bo'lsa, ko'krak va orqa tomondan harakat taqiqlanadi.", title="Regulirovshchik signallari", verified_at=_VERIFIED),
    RuleDraft("YHQ:13.9", "Teng ahamiyatli bo'lmagan chorrahada bosh yo'lda ketayotgan haydovchi imtiyozga ega.", title="Chorrahalarda imtiyoz", verified_at=_VERIFIED),
    RuleDraft("YHQ:13.11", "Teng ahamiyatli chorrahada o'ngdan kelayotgan transportga yo'l berish kerak.", title="Teng chorraha o'ng qoida", verified_at=_VERIFIED),
    RuleDraft("YHQ:8.1", "Manevrdan oldin haydovchi tegishli tomonga burilish ko'rsatkichini yoqishi shart.", title="Manevr va signal berish", verified_at=_VERIFIED),
    RuleDraft("YHQ:10.2", "Aholi punktlarida ruxsat etilgan maksimal tezlik soatiga 70 km.", title="Tezlik cheklovi", verified_at=_VERIFIED),
    RuleDraft("YHQ:11.5", "Yo'l belgilari yoki chiziqlar taqiqlagan joylarda quvib o'tish mumkin emas.", title="Quvib o'tish", verified_at=_VERIFIED),
    RuleDraft("YHQ:12.4", "Piyodalar o'tish joyida to'xtash va to'xtab turish taqiqlanadi.", title="To'xtash taqiqlari", verified_at=_VERIFIED),
    RuleDraft("YHQ:14.1", "Belgilanmagan piyodalar o'tish joyida haydovchi piyodaga yo'l berishi shart.", title="Piyodalarga imtiyoz", verified_at=_VERIFIED),
    RuleDraft("YHQ:15.3", "Temir yo'l kesishmasida shlagbaum tushayotgan bo'lsa, harakatni davom ettirish taqiqlanadi.", title="Temir yo'l kesishmasi", verified_at=_VERIFIED),
    RuleDraft("YHQ:16.1", "Avtomagistralda orqaga yurish va to'xtash (maxsus joylardan tashqari) taqiqlanadi.", title="Avtomagistral qoidalari", verified_at=_VERIFIED),
    RuleDraft("YHQ:2.3", "Tormoz tizimi nosoz bo'lsa transport vositasini boshqarish taqiqlanadi.", title="Transport holati", verified_at=_VERIFIED),
    RuleDraft("YHQ:22.9", "12 yoshgacha bolalarni old o'rindiqda maxsus qurilmasiz tashish taqiqlanadi.", title="Bolalarni tashish", verified_at=_VERIFIED),
    RuleDraft("YHQ:2.5", "Yo'l-transport hodisasida haydovchi to'xtab, jabrlanganlarga birinchi yordam ko'rsatishi shart.", title="Favqulodda vaziyat", verified_at=_VERIFIED),
]


def _q(topic, prompt, short, rule, options, *, sign=False, difficulty=1, subtopic=None):
    return QuestionDraft(
        category=Category.B,
        topic=topic,
        prompt=prompt,
        short_explanation=short,
        options=[OptionDraft(text=t, is_correct=c, explanation=e) for (t, c, e) in options],
        rule_code=rule,
        is_sign_question=sign,
        difficulty=difficulty,
        subtopic=subtopic,
        ai_assisted=True,
        sources=_demo_source(),
    )


_QUESTIONS: list[QuestionDraft] = [
    _q(Topic.GENERAL_RULES,
       "Haydovchi yo'lda qanday hujjatlarni olib yurishi shart?",
       "Guvohnoma va transport hujjatlarini doim yoningizda saqlang.",
       "YHQ:2.1",
       [("Faqat pasport", False, "Pasport transport hujjati emas."),
        ("Haydovchilik guvohnomasi va transport hujjatlari", True, "YHQ 2.1 aynan shu hujjatlarni talab qiladi."),
        ("Hech qanday hujjat shart emas", False, "Hujjatsiz boshqarish taqiqlanadi.")]),
    _q(Topic.GENERAL_RULES,
       "Xavfsizlik kamari qachon taqilishi kerak?",
       "Kamar hayotni saqlaydi — har doim taqing.",
       "YHQ:2.9",
       [("Faqat magistralda", False, "Kamar barcha yo'llarda majburiy."),
        ("Kamar bilan jihozlangan avtomobilda har doim", True, "YHQ 2.9 ga ko'ra kamar majburiy."),
        ("Faqat tezlik 60 km/soatdan oshganda", False, "Tezlikka bog'liq emas.")]),
    _q(Topic.ROAD_SIGNS,
       "Ko'k doira ichidagi belgi qanday turga kiradi?",
       "Ko'k doira = buyuruvchi (majburiy) belgi.",
       "YHQ:3.1",
       [("Buyuruvchi belgi", True, "Ko'k doira buyuruvchi belgidir."),
        ("Ogohlantiruvchi belgi", False, "Ogohlantiruvchilar uchburchak shaklda."),
        ("Axborot belgisi", False, "Axborot belgilari to'rtburchak.")],
       sign=True, subtopic="belgilar turlari"),
    _q(Topic.ROAD_SIGNS,
       "Qizil hoshiyali uchburchak belgi nimani bildiradi?",
       "Uchburchak = ogohlantirish, ehtiyot bo'ling.",
       "YHQ:3.2",
       [("Harakat taqiqlangan", False, "Taqiq belgilari doira shaklida."),
        ("Ogohlantirish", True, "Uchburchak ogohlantiruvchi belgidir."),
        ("Majburiy yo'nalish", False, "Majburiy belgilar ko'k doira.")],
       sign=True),
    _q(Topic.ROAD_SIGNS,
       "Doira ichidagi qizil belgi asosan nimani anglatadi?",
       "Qizil doira ko'pincha taqiqni bildiradi.",
       "YHQ:3.1",
       [("Taqiqlovchi belgi", True, "Qizil doira taqiqlovchi belgidir."),
        ("Servis belgisi", False, "Servis belgilari ko'k to'rtburchak."),
        ("Ustunlik belgisi", False, "Ustunlik belgilari boshqa shaklda.")],
       sign=True),
    _q(Topic.ROAD_MARKINGS,
       "Uzluksiz bo'ylama chiziq nimani bildiradi?",
       "Uzluksiz chiziqni kesib o'tmang.",
       "YHQ:4.1",
       [("Uni kesib o'tish mumkin", False, "Uzluksiz chiziqni kesish taqiqlanadi."),
        ("Uni kesib o'tish taqiqlanadi", True, "YHQ 4.1: uzluksiz chiziq kesilmaydi."),
        ("Faqat tunda amal qiladi", False, "Vaqtga bog'liq emas.")]),
    _q(Topic.SIGNALS,
       "Svetoforning qizil signali nimani bildiradi?",
       "Qizil = to'xta.",
       "YHQ:5.1",
       [("Harakatni davom ettirish", False, "Qizilda harakat taqiqlanadi."),
        ("Harakatni taqiqlaydi", True, "YHQ 5.1: qizil signal harakatni taqiqlaydi."),
        ("Ehtiyotkorlik bilan o'tish", False, "Bu sariq signalga taalluqli emas.")]),
    _q(Topic.SIGNALS,
       "Regulirovshchik qo'llarini yon tomonga yoygan. Ko'krak tomonidan harakat mumkinmi?",
       "Yon tomonga yoyilgan qo'l — ko'krak/orqadan to'xtang.",
       "YHQ:5.7",
       [("Ha, mumkin", False, "Ko'krak tomonidan harakat taqiqlanadi."),
        ("Yo'q, taqiqlanadi", True, "YHQ 5.7: bu holatda harakat taqiqlanadi."),
        ("Faqat chapga burilish mumkin", False, "Harakat umuman taqiqlanadi.")]),
    _q(Topic.INTERSECTIONS,
       "Teng ahamiyatli bo'lmagan chorrahada kim imtiyozga ega?",
       "Bosh yo'lda ketgan haydovchi o'tadi.",
       "YHQ:13.9",
       [("Ikkilamchi yo'ldagi haydovchi", False, "Ikkilamchi yo'l yo'l beradi."),
        ("Bosh yo'ldagi haydovchi", True, "YHQ 13.9: bosh yo'l imtiyozga ega."),
        ("Chapdan kelgan haydovchi", False, "Bu teng chorraha qoidasi emas.")]),
    _q(Topic.INTERSECTIONS,
       "Teng ahamiyatli chorrahada kimga yo'l berish kerak?",
       "Teng chorrahada o'ngdagiga yo'l bering.",
       "YHQ:13.11",
       [("O'ngdan kelayotganga", True, "YHQ 13.11: o'ng qoidasi amal qiladi."),
        ("Chapdan kelayotganga", False, "Chap emas, o'ng qoidasi."),
        ("Hech kimga", False, "Teng chorrahada imtiyoz beriladi.")]),
    _q(Topic.MANOEUVRING,
       "Qatorni almashtirishdan oldin haydovchi nima qilishi shart?",
       "Manevrdan oldin signal bering.",
       "YHQ:8.1",
       [("Tezlikni oshirish", False, "Tezlik bilan bog'liq emas."),
        ("Burilish ko'rsatkichini yoqish", True, "YHQ 8.1: signal berish majburiy."),
        ("Signalsiz burilish", False, "Signalsiz manevr taqiqlanadi.")]),
    _q(Topic.SPEED_DISTANCE,
       "Aholi punktlarida ruxsat etilgan umumiy maksimal tezlik qancha?",
       "Shaharda odatda 70 km/soat.",
       "YHQ:10.2",
       [("60 km/soat", False, "Belgilangan umumiy chegara 70."),
        ("70 km/soat", True, "YHQ 10.2: aholi punktida 70 km/soat."),
        ("90 km/soat", False, "Bu shahardan tashqari yo'lga taalluqli.")]),
    _q(Topic.OVERTAKING,
       "Quvib o'tish qachon taqiqlanadi?",
       "Belgilar/chiziqlar taqiqlagan joyda quvmang.",
       "YHQ:11.5",
       [("Yo'l ravon bo'lganda", False, "Bu quvib o'tishni taqiqlamaydi."),
        ("Belgilar yoki chiziqlar taqiqlaganda", True, "YHQ 11.5: taqiq joylarida quvmaslik."),
        ("Kunduzi", False, "Vaqt o'zi taqiq emas.")]),
    _q(Topic.STOPPING_PARKING,
       "Piyodalar o'tish joyida to'xtash mumkinmi?",
       "O'tish joyida to'xtamang.",
       "YHQ:12.4",
       [("Ha, 5 daqiqagacha", False, "Vaqtdan qat'i nazar taqiqlanadi."),
        ("Yo'q, taqiqlanadi", True, "YHQ 12.4: o'tish joyida to'xtash taqiqlanadi."),
        ("Faqat tunda mumkin", False, "Vaqtga bog'liq emas.")]),
    _q(Topic.VULNERABLE_USERS,
       "Belgilanmagan piyoda o'tish joyida piyoda yo'lni kesmoqda. Haydovchi nima qiladi?",
       "Piyodaga yo'l bering.",
       "YHQ:14.1",
       [("Signal berib o'tib ketadi", False, "Piyodaga imtiyoz beriladi."),
        ("Piyodaga yo'l beradi", True, "YHQ 14.1: piyodaga yo'l berish shart."),
        ("Tezlikni oshiradi", False, "Bu xavfli va taqiqlangan.")]),
    _q(Topic.RAILWAY_CROSSINGS,
       "Temir yo'l kesishmasida shlagbaum tusha boshladi. Nima qilasiz?",
       "Shlagbaum tushsa — to'xtang.",
       "YHQ:15.3",
       [("Tez o'tib olaman", False, "Bu juda xavfli va taqiqlangan."),
        ("To'xtayman", True, "YHQ 15.3: shlagbaum tushayotganda to'xtash shart."),
        ("Signal beraman", False, "Signal berish o'tishga ruxsat bermaydi.")]),
    _q(Topic.MOTORWAYS_SPECIAL,
       "Avtomagistralda nima taqiqlanadi?",
       "Magistralda orqaga yurmang, to'xtamang.",
       "YHQ:16.1",
       [("Orqaga yurish", True, "YHQ 16.1: magistralda orqaga yurish taqiqlanadi."),
        ("Belgilangan tezlikda harakat", False, "Bu ruxsat etilgan."),
        ("Qatorni saqlash", False, "Bu to'g'ri harakat.")]),
    _q(Topic.VEHICLE_CONDITION,
       "Qaysi nosozlikda transport vositasini boshqarish taqiqlanadi?",
       "Nosoz tormoz bilan yo'lga chiqmang.",
       "YHQ:2.3",
       [("Radio ishlamasa", False, "Bu xavfsizlikka ta'sir qilmaydi."),
        ("Tormoz tizimi nosoz bo'lsa", True, "YHQ 2.3: nosoz tormoz bilan boshqarish taqiqlanadi."),
        ("Konditsioner buzilsa", False, "Bu harakat xavfsizligiga taalluqli emas.")]),
    _q(Topic.TRANSPORT_OF_PEOPLE_CARGO,
       "Necha yoshgacha bolani old o'rindiqda maxsus qurilmasiz tashish taqiqlanadi?",
       "12 yoshgacha — maxsus qurilma kerak.",
       "YHQ:22.9",
       [("7 yosh", False, "Chegara 12 yosh."),
        ("12 yosh", True, "YHQ 22.9: 12 yoshgacha maxsus qurilma talab qilinadi."),
        ("16 yosh", False, "Chegara 12 yosh.")]),
    _q(Topic.EMERGENCIES_FIRST_AID,
       "Yo'l-transport hodisasi sodir bo'ldi. Haydovchining birinchi majburiyati nima?",
       "To'xtang va yordam ko'rsating.",
       "YHQ:2.5",
       [("Voqea joyidan ketish", False, "Bu jinoyat hisoblanadi."),
        ("To'xtab, jabrlanganlarga yordam ko'rsatish", True, "YHQ 2.5: to'xtab yordam berish shart."),
        ("Avtomobilni yo'ldan olib qochish", False, "Avval yordam va joyni saqlash muhim.")]),
]


class SeedContentSource(ContentSource):
    name = "seed-demo"

    def rules(self) -> list[RuleDraft]:
        return list(_RULES)

    def questions(self) -> list[QuestionDraft]:
        return list(_QUESTIONS)
