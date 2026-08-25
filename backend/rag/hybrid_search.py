import re

from django.db.models import Q

from .semantic_search import search_knowledge_semantic

STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "des",
    "du",
    "un",
    "une",
    "et",
    "ou",
    "à",
    "a",
    "en",
    "dans",
    "pour",
    "par",
    "sur",
    "avec",
    "au",
    "aux",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "est",
    "sont",
    "comment",
    "fonctionne",
    "règle",
    "règles",
    "relatif",
    "relative",
    "relatifs",
    "relatives",
    "peut",
    "son",
    "sa",
    "ses",
}
SEARCH_FIELDS = (
    "article_number",
    "content",
    "title",
    "chapter",
    "section",
    "document_title",
)
SYNONYMS = {
    "tva": ("taxe sur la valeur ajoutée", "valeur ajoutée"),
    "القيمة المضافة": ("taxe sur la valeur ajoutée", "TVA", "valeur ajoutée"),
    "الضريبة على الشركات": ("impôt sur les sociétés",),
    "الضريبة على الدخل": ("impôt sur le revenu", "revenu global"),
    "frais": ("charges", "charges déductibles"),
    "retirer": ("déduire", "déductible", "déductibles"),
    "bénéfice imposable": (
        "résultat fiscal",
        "bénéfice net",
        "impôt sur les sociétés",
    ),
    "entreprise": ("société",),
    "créer": ("constituer", "constitution"),
    "paiement vers l'étranger": (
        "règlement à destination de l'étranger",
        "virement à destination de l'étranger",
    ),
    "actionnaires": (
        "droits des actionnaires",
        "assemblée générale",
        "assemblées d'actionnaires",
    ),
    "virement international": (
        "virement à destination de l'étranger",
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
        "transfert à l'étranger",
    ),
    "masarif": ("charges", "charges déductibles"),
    "charjat": ("charges", "charges déductibles"),
    "ribh": ("bénéfice imposable", "résultat fiscal"),
    "charika": ("société", "entreprise"),
    "charikat": ("société", "entreprise"),
    "mo9awala": ("société", "entreprise"),
    "mosahimin": ("actionnaires", "assemblées d'actionnaires"),
    "ra2smal": ("capital",),
    "lflos lbarra": (
        "paiement vers l'étranger",
        "virement international",
        "règlement à destination de l'étranger",
    ),
    "paiement lbarra": (
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
    ),
    "virement lbarra": (
        "virement à destination de l'étranger",
        "règlement à destination de l'étranger",
    ),
    "srf": ("opérations de change", "devises"),
    "المصاريف": ("charges", "charges déductibles"),
    "التكاليف": ("charges", "charges déductibles"),
    "المصاريف القابلة للخصم": ("charges déductibles",),
    "التكاليف القابلة للخصم": ("charges déductibles",),
    "الربح الخاضع للضريبة": ("bénéfice imposable", "résultat fiscal"),
    "النتيجة الجبائية": ("résultat fiscal",),
    "شركة مساهمة": ("société", "société anonyme"),
    "شركة مجهولة الاسم": ("société", "société anonyme"),
    "شركة": ("société", "entreprise"),
    "الشركة": ("société", "entreprise"),
    "تأسيس": ("constitution", "constituer"),
    "المساهمون": ("actionnaires", "assemblées d'actionnaires"),
    "المساهمين": ("actionnaires", "assemblées d'actionnaires"),
    "رأس المال": ("capital",),
    "تحويل دولي": (
        "virement international",
        "virement à destination de l'étranger",
        "transfert à l'étranger",
    ),
    "تحويل إلى الخارج": (
        "virement à destination de l'étranger",
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
        "règlements au profit de non-résidents",
        "non-résidents",
        "transfert à l'étranger",
    ),
    "التحويل إلى الخارج": (
        "virement à destination de l'étranger",
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
        "règlements au profit de non-résidents",
        "non-résidents",
        "transfert à l'étranger",
    ),
    "الحوالة إلى الخارج": (
        "virement à destination de l'étranger",
        "transfert à l'étranger",
        "règlements au profit de non-résidents",
    ),
    "الدفع إلى الخارج": (
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
        "règlements au profit de non-résidents",
    ),
    "الأداء إلى الخارج": (
        "paiement vers l'étranger",
        "règlement à destination de l'étranger",
        "règlements au profit de non-résidents",
    ),
    "إرسال الأموال إلى الخارج": (
        "transfert à l'étranger",
        "virement à destination de l'étranger",
        "règlements au profit de non-résidents",
    ),
    "تحويل الأموال إلى الخارج": (
        "transfert à l'étranger",
        "virement à destination de l'étranger",
        "règlements au profit de non-résidents",
    ),
    "الصرف": ("opérations de change", "devises"),
    "عمليات الصرف": ("opérations de change", "devises"),
    "العملات الأجنبية": ("opérations de change", "devises"),
    "غير مقيم": ("non-résident", "non-résidents"),
    "غير المقيمين": ("non-résident", "non-résidents"),
    "الجريمة": ("مجموعة القانون الجنائي", "جريمة", "عقوبة", "يعاقب"),
    "المحكمة المختصة": ("قانون المسطرة المدنية", "المحكمة", "الاختصاص"),
    "الرسم العقاري": ("التحفيظ العقاري", "الرسم العقاري", "التقييد"),
    "البائع": ("حماية المستهلك", "المورد", "المستهلك"),
    "divorce": ("مدونة الأسرة", "طلاق"),
    "بغيت نطلق": ("مدونة الأسرة", "طلاق", "divorce"),
    "نطلق": ("مدونة الأسرة", "طلاق", "divorce"),
    "طلاق": ("مدونة الأسرة", "divorce"),
    "الطلاق": ("مدونة الأسرة", "طلاق", "divorce"),
    "tla9": ("مدونة الأسرة", "طلاق", "divorce"),
    "licenciement": (
        "مدونة الشغل",
        "rupture du contrat de travail",
        "contrat de travail",
        "indemnité",
        "préavis",
        "faute grave",
        "الفصل من الشغل",
        "إنهاء عقد الشغل",
        "التعويض عن الفصل",
    ),
    "طردوني من الخدمة": (
        "مدونة الشغل",
        "licenciement",
        "rupture du contrat de travail",
        "contrat de travail",
        "indemnité",
        "préavis",
        "faute grave",
        "الفصل من الشغل",
        "إنهاء عقد الشغل",
        "التعويض عن الفصل",
    ),
    "طردوني": (
        "مدونة الشغل",
        "licenciement",
        "rupture du contrat de travail",
        "الفصل من الشغل",
        "إنهاء عقد الشغل",
        "التعويض عن الفصل",
    ),
    "فصل من العمل": (
        "مدونة الشغل",
        "licenciement",
        "rupture du contrat de travail",
        "الفصل من الشغل",
        "إنهاء عقد الشغل",
        "التعويض عن الفصل",
    ),
    "الخدمة": (
        "مدونة الشغل",
        "عقد الشغل",
        "الفصل من الشغل",
        "إنهاء عقد الشغل",
        "التعويض عن الفصل",
    ),
    "شنو عقوبة السرقة": ("القانون الجنائي", "سرقة", "عقوبة"),
    "عقوبة السرقة": ("القانون الجنائي", "سرقة", "عقوبة"),
    "سرقة": ("القانون الجنائي", "عقوبة"),
    "كيفاش ندير شكاية": ("المسطرة الجنائية", "plainte", "النيابة العامة"),
    "شكاية": ("المسطرة الجنائية", "plainte", "النيابة العامة"),
    "plainte": ("المسطرة الجنائية", "شكاية", "النيابة العامة"),
    "كيفاش نرفع دعوى": ("المسطرة المدنية", "دعوى", "tribunal"),
    "دعوى": ("المسطرة المدنية", "tribunal"),
    "عندي مشكل فالكراء": ("الكراء", "bail", "droit immobilier"),
    "كراء": ("الكراء", "bail", "droit immobilier"),
    "فالكراء": ("الكراء", "bail", "droit immobilier"),
    "مكتري": ("الكراء", "المكتري", "عقد الكراء", "locataire"),
    "مكري": ("الكراء", "المكري", "عقد الكراء", "bailleur"),
    "loyer": ("الكراء", "الوجيبة الكرائية", "المكتري", "المكري"),
    "bail": ("الكراء", "عقد الكراء", "locataire", "bailleur"),
    "كيفاش ندير التحفيظ العقاري": ("التحفيظ العقاري", "propriété foncière"),
    "تحفيظ عقاري": ("التحفيظ العقاري", "propriété foncière"),
    "شنو حقوق المستهلك": ("حماية المستهلك", "consommateur"),
    "مستهلك": ("حماية المستهلك", "consommateur"),
    "المستهلك": ("حماية المستهلك", "consommateur"),
    "شنو دور المحامي": ("مهنة المحاماة", "محامي", "avocat"),
    "محامي": ("مهنة المحاماة", "avocat"),
    "المحامي": ("مهنة المحاماة", "محامي", "avocat"),
    "رخصة البناء": ("التعمير", "autorisation de construire"),
}

LABOUR_QUERY_TERMS = (
    "طردوني",
    "فصل",
    "licenciement",
    "rupture",
    "service",
    "الخدمة",
)
LABOUR_CONTENT_TERMS = (
    "الفصل من الشغل",
    "الطرد",
    "إنهاء عقد الشغل",
    "التعويض عن الفصل",
    "أجل الإخطار",
    "الخطأ الجسيم",
    "licenciement",
    "rupture du contrat de travail",
    "indemnité",
    "préavis",
    "faute grave",
)
LABOUR_TRANSITIONAL_TERMS = (
    "يسري مفعول هذا القانون",
    "يدخل حيز التنفيذ",
    "نشره في الجريدة الرسمية",
)
THEFT_QUERY_TERMS = ("سرقة", "سرق", "اختلس", "vol")
THEFT_CONTENT_TERMS = (
    "السرقة",
    "سرق",
    "اختلس",
    "عقوبة السرقة",
    "vol",
    "soustraction frauduleuse",
    "emprisonnement",
    "amende",
)
RENT_QUERY_TERMS = ("كراء", "مكري", "مكتري", "loyer", "bail")
RENT_CONTENT_TERMS = (
    "الكراء",
    "المكتري",
    "المكري",
    "الوجيبة الكرائية",
    "وجيبة الكراء",
    "المحل المكترى",
    "عقد الكراء",
    "bail",
    "loyer",
    "locataire",
    "bailleur",
)
URBANISM_QUERY_TERMS = (
    "التعمير",
    "البناء",
    "رخصة البناء",
    "urbanisme",
    "construction",
)

DOMAIN_PROFILES = (
    {
        "triggers": ("غير مقيم", "غير المقيمين", "non-résident", "non resident"),
        "titles": ("Instruction Générale des Opérations de Change",),
        "content": ("non-résident", "non-résidents", "résident", "résidence"),
    },
    {
        "triggers": (
            "tva",
            "القيمة المضافة",
            "الضريبة على الشركات",
            "الضريبة على الدخل",
            "impôt sur les sociétés",
            "impôt sur le revenu",
        ),
        "titles": ("Code Général des Impôts",),
        "content": (
            "taxe sur la valeur ajoutée",
            "valeur ajoutée",
            "impôt sur les sociétés",
            "impôt sur le revenu",
            "revenu global",
        ),
    },
    {
        "triggers": ("نفقة", "حضانة", "طلاق", "الزوجة", "الأطفال", "الاطفال"),
        "titles": ("مدونة الأسرة",),
        "content": ("النفقة", "الحضانة", "احلضانة", "الطلاق", "التطليق", "الزوجة", "المحضون", "احملضون"),
    },
    {
        "triggers": ("طردوني", "الطرد", "الفصل", "licenciement", "التعويض", "الإخطار", "الاخطار", "الخطأ الجسيم", "الخطا الجسيم"),
        "titles": ("مدونة الشغل",),
        "content": ("الفصل", "إنهاء عقد الشغل", "التعويض", "أجل الإخطار", "الخطأ الجسيم", "licenciement", "indemnité", "préavis", "faute grave"),
        "forbidden_content": LABOUR_TRANSITIONAL_TERMS + ("أحكام انتقالية",),
    },
    {
        "triggers": ("الجريمة", "جريمة", "السرقة", "سرقة", "النصب", "الضرب", "الجرح", "التزوير", "vol"),
        "titles": ("مجموعة القانون الجنائي",),
        "content": ("السرقة", "سرق", "اختلاس", "النصب", "الاحتيال", "الضرب", "الجرح", "التزوير", "زور", "عقوبة", "يعاقب"),
        "forbidden_titles": ("المسطرة الجنائية",),
    },
    {
        "triggers": ("دعوى", "المحكمة المختصة", "مختصة", "التبليغ", "تبليغ", "الحكم", "استئناف", "نستأنف", "نستانف"),
        "titles": ("قانون المسطرة المدنية",),
        "content": ("الدعوى", "دعوى", "التبليغ", "الحكم", "الاستئناف", "المستأنف", "المحكمة"),
        "forbidden_titles": ("المسطرة الجنائية",),
    },
    {
        "triggers": ("شكاية", "النيابة العامة", "الشرطة القضائية", "المتابعة", "متابعة"),
        "titles": ("قانون المسطرة الجنائية",),
        "content": ("الشكاية", "شكاية", "النيابة العامة", "الشرطة القضائية", "المتابعة", "البحث التمهيدي"),
    },
    {
        "triggers": ("الكراء", "فالكراء", "المكري", "المكتري", "الوجيبة", "الإفراغ", "loyer", "bail"),
        "titles": ("الكراء",),
        "content": ("الكراء", "الوجيبة الكرائية", "المكري", "المكتري", "الإفراغ", "عقد الكراء"),
        "forbidden_titles": ("التعمير",),
    },
    {
        "triggers": ("التحفيظ العقاري", "الرسم العقاري", "الملكية", "الحقوق العينية", "نحافظ على عقار"),
        "titles": ("التحفيظ العقاري", "مدونة الحقوق العينية"),
        "content": ("التحفيظ العقاري", "الرسم العقاري", "الملكية", "حق عيني", "العقار", "التقييد"),
        "forbidden_titles": ("التعمير", "مدونة التجارة"),
    },
    {
        "triggers": ("عيب", "ضمان", "منتوج", "البائع", "المستهلك", "كمستهلك"),
        "titles": ("حماية المستهلك",),
        "content": ("الضمان", "العيب", "المنتوج", "البائع", "المستهلك", "الشروط التعسفية"),
        "forbidden_titles": ("مدونة الأسرة",),
    },
    {
        "triggers": ("محامي", "المحامي", "المحاماة"),
        "titles": ("مهنة المحاماة",),
        "content": ("المحامي", "المحاماة", "استشارة", "النيابة عن الأطراف"),
        "forbidden_titles": ("مدونة الحقوق العينية", "مدونة التجارة"),
    },
    {
        "triggers": ("موثق", "الموثق", "التوثيق"),
        "titles": ("تنظيم مهنة التوثيق",),
        "content": ("الموثق", "التوثيق", "عقد رسمي", "العقود الرسمية"),
        "forbidden_titles": ("مهنة المحاماة", "مدونة الحقوق العينية", "مدونة التجارة"),
    },
    {
        "triggers": ("شركة المساهمة", "المساهمون"),
        "titles": ("شركات المساهمة",),
        "content": ("شركة المساهمة", "المساهمون", "المسؤولية", "رأس المال"),
    },
    {
        "triggers": ("شركة التضامن", "شركة التوصية", "الشركاء"),
        "titles": ("شركة التضامن وشركة التوصية البسيطة", "شركات المساهمة"),
        "content": ("الشركاء", "المساهمون", "شركة المساهمة", "شركة التضامن", "شركة التوصية", "المسؤولية", "رأس المال"),
    },
    {
        "triggers": ("التعمير", "رخصة البناء", "البناء", "التجزئة العقارية"),
        "titles": ("التعمير",),
        "content": ("التعمير", "رخصة البناء", "البناء", "التجزئة العقارية", "التجزئات"),
    },
)


def _matching_profiles(question):
    return [
        profile
        for profile in DOMAIN_PROFILES
        if _contains_fragment(question, profile["triggers"])
    ]
COMBINED_INTENTS = {
    frozenset(("frais", "retirer")): "charges déductibles",
}
LEGAL_PHRASE_BOOSTS = {
    "assemblées d'actionnaires": 25,
    "droits des actionnaires": 20,
    "virement à destination de l'étranger": 45,
    "à destination de l'étranger": 45,
    "règlements au profit de non-résidents": 55,
    "paiement vers l'étranger": 40,
    "opérations de change": 35,
    "règlement à destination de l'étranger": 30,
    "transfert à l'étranger": 25,
    "مدونة الأسرة": 55,
    "مدونة الشغل": 55,
    "القانون الجنائي": 55,
    "المسطرة الجنائية": 55,
    "المسطرة المدنية": 55,
    "التحفيظ العقاري": 55,
    "حماية المستهلك": 55,
    "مهنة المحاماة": 55,
    "التعمير": 45,
    "rupture du contrat de travail": 35,
    "الفصل من الشغل": 40,
    "إنهاء عقد الشغل": 45,
    "التعويض عن الفصل": 45,
    "faute grave": 30,
    "préavis": 25,
    "indemnité": 25,
}


def normalize(text):
    return text.casefold().replace("’", "'").strip()


def extract_search_terms(question):
    normalized_question = normalize(question)
    keywords = [
        word
        for word in re.findall(r"\w+", normalized_question, flags=re.UNICODE)
        if word not in STOPWORDS and (len(word) >= 3 or word.isdigit())
    ]
    direct_phrases = [
        " ".join(keywords[index : index + 2]) for index in range(len(keywords) - 1)
    ]
    phrases = list(direct_phrases)

    for source, replacements in SYNONYMS.items():
        if source not in normalized_question:
            continue
        phrases.append(source)
        for replacement in replacements:
            if " " in replacement:
                phrases.append(replacement)
            else:
                keywords.append(replacement)

    for profile in _matching_profiles(normalized_question):
        for term in profile.get("titles", ()) + profile.get("content", ()):
            if " " in term:
                phrases.append(term)
            else:
                keywords.append(term)

    return (
        list(dict.fromkeys(keywords)),
        list(dict.fromkeys(phrases)),
        list(dict.fromkeys(direct_phrases)),
    )


def search_knowledge_keywords(terms):
    from knowledge.models import KnowledgeEntry

    query = Q()
    for term in terms:
        for field in SEARCH_FIELDS:
            query |= Q(**{f"{field}__icontains": term})
    if not query:
        return []

    return list(
        KnowledgeEntry.objects.filter(query, is_active=True)
        .select_related("category")
        .distinct()
    )


def contains_term(text, term):
    text = normalize(text or "")
    term = normalize(term)
    if " " in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _contains_fragment(text, fragments):
    normalized = normalize(text or "")
    return any(normalize(fragment) in normalized for fragment in fragments)


def _domain_score(entry, question):
    document_title = entry.document_title or ""
    content = entry.content or ""
    labour_query = _contains_fragment(question, LABOUR_QUERY_TERMS)
    theft_query = _contains_fragment(question, THEFT_QUERY_TERMS)
    rent_query = _contains_fragment(question, RENT_QUERY_TERMS)
    urbanism_query = _contains_fragment(question, URBANISM_QUERY_TERMS)
    score = 0

    generic_query_terms = {
        "شنو", "ما", "هي", "هو", "كيف", "كيفاش", "واش", "عندي", "في",
        "من", "على", "الى", "إلى", "غير", "معنى", "le", "la", "les", "de", "des",
        "quel", "quelle", "comment",
    }
    question_terms = {
        term
        for term in normalize(question).split()
        if len(term) >= 3 and term not in generic_query_terms
    }
    for term in question_terms:
        if contains_term(content[:1600], term):
            score += 25
        if contains_term(document_title, term):
            score += 40
        if any(contains_term(value, term) for value in (entry.title, entry.section, entry.chapter)):
            score += 50
    if "المتابعة" in normalize(question):
        if _contains_fragment(content[:400], ("المتابعة", "متابعة")):
            score += 1000
        elif _contains_fragment(content[:1600], ("المتابعة", "متابعة")):
            score += 250
    if _contains_fragment(question, ("virement international",)):
        if _contains_fragment(
            content,
            ("virement à destination de l'étranger", "virement à destination de l’étranger"),
        ):
            score += 500
        if _contains_fragment(content, ("transport international",)):
            score -= 220

    for profile in _matching_profiles(question):
        title_match = _contains_fragment(document_title, profile.get("titles", ()))
        content_start = content[:1200]
        content_matches = sum(
            normalize(term) in normalize(content_start)
            for term in profile.get("content", ())
        )
        if title_match:
            score += 130
        if content_matches:
            score += content_matches * 35
            if title_match:
                score += 90
        direct_matches = sum(
            normalize(trigger) in normalize(content_start)
            for trigger in profile.get("triggers", ())
        )
        score += direct_matches * 55
        if _contains_fragment(document_title, profile.get("forbidden_titles", ())):
            score -= 260
        if _contains_fragment(content_start, profile.get("forbidden_content", ())):
            score -= 300

    asks_about_effective_date = _contains_fragment(
        question,
        ("دخول حيز التنفيذ", "تاريخ النفاذ", "الجريدة الرسمية", "effective date"),
    )
    if not asks_about_effective_date and _contains_fragment(
        content[:600],
        ("يسري مفعول هذا القانون", "يدخل حيز التنفيذ", "أحكام انتقالية"),
    ):
        score -= 180

    if labour_query:
        title_match = _contains_fragment(document_title, ("مدونة الشغل",))
        content_matches = sum(
            normalize(term) in normalize(content) for term in LABOUR_CONTENT_TERMS
        )
        if title_match:
            score += 90
        if content_matches:
            score += content_matches * 30
            if title_match:
                score += 70
        if _contains_fragment(content, LABOUR_TRANSITIONAL_TERMS):
            score -= 300

    if theft_query:
        title_match = _contains_fragment(
            document_title,
            ("مجموعة القانون الجنائي",),
        )
        content_start = content[:600]
        theft_specific_terms = (
            "السرقة",
            "سرق",
            "اختلس",
            "vol",
            "soustraction frauduleuse",
        )
        sanction_terms = (
            "يعاقب",
            "عقوبة",
            "الحبس",
            "السجن",
            "غرامة",
            "emprisonnement",
            "amende",
        )
        has_theft_term = _contains_fragment(content_start, theft_specific_terms)
        has_sanction_term = _contains_fragment(content_start, sanction_terms)
        content_matches = sum(
            normalize(term) in normalize(content_start)
            for term in THEFT_CONTENT_TERMS
        )
        if title_match:
            score += 100
            if not has_theft_term:
                score -= 400
        if content_matches:
            score += content_matches * 35
            if title_match:
                score += 80
        if has_theft_term and has_sanction_term:
            score += 650
            if _contains_fragment(content_start[:260], theft_specific_terms):
                score += 250
        if _contains_fragment(
            content_start,
            ("يعد سارقا", "soustraction frauduleuse"),
        ):
            score += 260
        elif _contains_fragment(content_start, ("يعاقب على السرقة",)):
            score += 100

    if rent_query:
        title_match = _contains_fragment(document_title, ("الكراء",))
        content_matches = sum(
            normalize(term) in normalize(content) for term in RENT_CONTENT_TERMS
        )
        if title_match:
            score += 110
        if content_matches:
            score += content_matches * 25
            if title_match:
                score += 80
        if not urbanism_query and _contains_fragment(document_title, ("التعمير",)):
            score -= 250

    return score


def score_entry(
    entry,
    keywords,
    phrases,
    definition_phrases=(),
    semantic_points=0,
    question="",
):
    score = semantic_points
    structured_texts = (entry.title, entry.section, entry.chapter)
    keyword_set = set(keywords)
    priority_phrases = {
        phrase
        for required_keywords, phrase in COMBINED_INTENTS.items()
        if required_keywords.issubset(keyword_set)
    }

    for keyword in keywords:
        if contains_term(entry.article_number, keyword):
            score += 18
        if any(contains_term(text, keyword) for text in structured_texts):
            score += 8
        if contains_term(entry.document_title, keyword):
            score += 3
        if contains_term(entry.content, keyword):
            score += 1

    for phrase in phrases:
        phrase_boost = LEGAL_PHRASE_BOOSTS.get(normalize(phrase), 0)
        if contains_term(entry.article_number, phrase):
            score += 40 + phrase_boost
            if phrase in priority_phrases:
                score += 15
        if any(contains_term(text, phrase) for text in structured_texts):
            score += 12 + phrase_boost
        if contains_term(entry.document_title, phrase):
            score += 6 + phrase_boost
        if contains_term(entry.content, phrase):
            score += 4 + phrase_boost
    content_start = normalize(entry.content[:250])
    for phrase in definition_phrases:
        if f"{normalize(phrase)} est" in content_start:
            score += 40

    return score + _domain_score(entry, question)


def search_knowledge_hybrid(question, limit=3):
    keywords, phrases, definition_phrases = extract_search_terms(question)
    semantic_results = search_knowledge_semantic(question, limit=10)
    keyword_results = search_knowledge_keywords(keywords + phrases)

    candidates = {}
    semantic_ranks = {}
    for position, entry in enumerate(semantic_results):
        candidates[entry.id] = entry
        semantic_ranks[entry.id] = position
    for entry in keyword_results:
        candidates.setdefault(entry.id, entry)

    scored = []
    for entry in candidates.values():
        position = semantic_ranks.get(entry.id)
        semantic_points = max(12 - (position * 2), 2) if position is not None else 0
        score = score_entry(
            entry,
            keywords,
            phrases,
            definition_phrases,
            semantic_points,
            question,
        )
        scored.append((score, position if position is not None else 9999, entry.id, entry))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in scored[:limit]]
