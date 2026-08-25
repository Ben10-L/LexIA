import logging
import re

from django.conf import settings

from .hybrid_search import search_knowledge_hybrid
from .intent import (
    ARABIC_GREETING_ANSWER,
    ARABIC_OFF_TOPIC_ANSWER,
    ARABIC_OUT_OF_SCOPE_ANSWER,
    ARABIC_THANKS_ANSWER,
    DARJA_GREETING_ANSWER,
    DARJA_OFF_TOPIC_ANSWER,
    DARJA_OUT_OF_SCOPE_ANSWER,
    DARJA_THANKS_ANSWER,
    GREETING_ANSWER,
    OFF_TOPIC_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    THANKS_ANSWER,
    detect_basic_intent,
    detect_knowledge_scope,
    detect_unclear_legal_domain,
    get_unclear_legal_answer,
)
from .llm import generate_answer_or_fallback, is_llm_enabled


logger = logging.getLogger(__name__)


FALLBACK_ANSWER = (
    "Je n’ai pas trouvé d’information suffisamment pertinente dans la base "
    "de connaissances actuelle."
)
DARJA_FALLBACK_ANSWER = (
    "Ma l9itch ma3louma kafiya w mnasba f base dyal LexIA daba."
)
ARABIC_FALLBACK_ANSWER = (
    "لم أجد معلومات كافية ومرتبطة بالسؤال في قاعدة معرفة LexIA الحالية."
)


def get_fallback_answer(language="fr"):
    if language == "darija":
        return DARJA_FALLBACK_ANSWER
    if language == "ar":
        return ARABIC_FALLBACK_ANSWER
    return FALLBACK_ANSWER


def _source_from_entry(entry):
    return {
        "document_title": entry.document_title,
        "article_number": entry.article_number,
        "title": entry.title,
        "category": entry.category.name,
        "page_start": entry.page_start,
        "page_end": entry.page_end,
        "excerpt": entry.content[:400],
        "content": entry.content[:500],
    }


def _public_source(source):
    public_fields = (
        "document_title",
        "article_number",
        "category",
        "page_start",
        "page_end",
        "excerpt",
    )
    return {key: source.get(key) for key in public_fields}


def build_context_from_sources(sources):
    context_parts = []
    for index, source in enumerate(sources[:3], start=1):
        page = source.get("page_start")
        page_text = str(page) if page is not None else "non renseignée"
        content = source.get("content") or source.get("excerpt") or ""
        content_language = detect_text_language(content)
        context_parts.append(
            f"Source {index}\n"
            f"Document : {source.get('document_title', '')}\n"
            f"Article : {source.get('article_number', '')}\n"
            f"Catégorie : {source.get('category', '')}\n"
            f"Page : {page_text}\n"
            f"Langue du contenu : {content_language}\n"
            f"Contenu : {content}"
        )
    return "\n\n".join(context_parts)


def detect_text_language(text):
    """Detect the dominant script used by legal text without translating it."""
    arabic_count = len(re.findall(r"[\u0600-\u06ff]", text or ""))
    latin_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text or ""))
    if arabic_count == latin_count == 0:
        return "unknown"
    return "ar" if arabic_count > latin_count else "latin"


def _display_article_reference(article_number, language):
    """Keep cross-language references concise while preserving their identifier."""
    if language in {"ar", "darija"} and detect_text_language(article_number) == "latin":
        match = re.match(r"\s*(Article\s+(?:\d+[A-Za-z-]*|Premier))", article_number, re.I)
        if match:
            return match.group(1)
    return article_number


def _french_simple_explanation(question, source):
    """Build a cautious French orientation without translating legal content."""
    searchable = " ".join(
        str(value or "")
        for value in (
            question,
            source.get("category"),
            source.get("document_title"),
            source.get("title"),
            source.get("article_number"),
        )
    ).casefold()

    if any(term in searchable for term in ("divorc", "طلاق", "مدونة الأسرة")):
        return (
            "LexIA a retrouvé une disposition de la مدونة الأسرة liée au droit "
            "de la famille et aux règles applicables au mariage ou à sa "
            "dissolution. Pour les détails précis, consultez le texte original "
            "dans les sources ci-dessous."
        )
    if any(
        term in searchable
        for term in ("licenciement", "rupture", "مدونة الشغل", "فصل من العمل")
    ):
        return (
            "LexIA a retrouvé des dispositions de la مدونة الشغل liées à la "
            "rupture du contrat de travail et aux droits du salarié. Le texte "
            "source précise les règles applicables à la situation examinée."
        )
    if any(
        term in searchable
        for term in ("droit pénal", "القانون الجنائي", "مجموعة القانون الجنائي")
    ):
        return (
            "LexIA a retrouvé des dispositions du droit pénal marocain liées "
            "à l’infraction et à la sanction mentionnées dans la question. Le "
            "texte original doit être consulté pour connaître leur portée exacte."
        )
    if any(term in searchable for term in ("consommateur", "حماية المستهلك")):
        return (
            "LexIA a retrouvé des dispositions relatives à l’information et "
            "à la protection du consommateur, notamment selon le sujet évoqué : "
            "garantie, défaut du produit ou obligations du vendeur."
        )
    if any(term in searchable for term in ("location", "loyer", "bail", "كراء")):
        return (
            "LexIA a retrouvé des dispositions relatives au contrat de location, "
            "aux rapports entre bailleur et locataire ou au paiement du loyer."
        )
    if any(term in searchable for term in ("procédure", "procedure", "المسطرة", "دعوى", "محكمة", "شكاية")):
        return (
            "LexIA a retrouvé des dispositions de procédure liées à la démarche "
            "judiciaire mentionnée. Le texte source doit être consulté pour "
            "identifier les règles applicables à la situation précise."
        )
    if any(term in searchable for term in ("urbanisme", "التعمير", "رخصة البناء", "construction")):
        return (
            "LexIA a retrouvé des dispositions d’urbanisme liées à la construction, "
            "aux autorisations ou à l’aménagement mentionné dans la question."
        )
    if any(term in searchable for term in ("avocat", "notaire", "محامي", "موثق", "المحاماة", "التوثيق")):
        return (
            "LexIA a retrouvé des dispositions relatives à la profession juridique "
            "mentionnée et à son rôle. Le texte source en précise les missions et "
            "les obligations."
        )
    if any(term in searchable for term in ("société", "societe", "شركة", "الشركاء", "actionnaire")):
        return (
            "LexIA a retrouvé des dispositions du droit des sociétés liées à la "
            "forme sociale, à sa constitution ou aux droits des associés évoqués."
        )
    if any(term in searchable for term in ("fiscal", "impôt", "impot", "ضريب", "tva")):
        return (
            "LexIA a retrouvé des dispositions fiscales liées à l’impôt ou à "
            "l’opération mentionnée. Le texte source contient les règles précises "
            "applicables à ce sujet."
        )
    return (
        "LexIA a retrouvé une disposition juridique liée à votre question "
        "dans le document indiqué. Le contenu détaillé du texte source est "
        "disponible dans les sources consultées ci-dessous."
    )


def _arabic_simple_explanation(question, source):
    """Build a cautious Arabic orientation without translating legal content."""
    searchable = " ".join(
        str(value or "")
        for value in (
            question,
            source.get("category"),
            source.get("document_title"),
            source.get("title"),
            source.get("article_number"),
        )
    ).casefold()
    source_evidence = " ".join(
        str(value or "")
        for value in (
            source.get("article_number"),
            source.get("title"),
            source.get("content"),
            source.get("excerpt"),
        )
    ).casefold()

    is_deductible_expenses = (
        "code général des impôts" in searchable
        and any(
            term in source_evidence
            for term in ("charges déductibles", "المصاريف القابلة للخصم", "التكاليف القابلة للخصم")
        )
    )
    if is_deductible_expenses:
        return (
            "المصاريف القابلة للخصم هي المصاريف المرتبطة بنشاط المقاولة والتي "
            "يسمح القانون بأخذها بعين الاعتبار عند حساب الربح الخاضع للضريبة، "
            "بشرط أن تكون مبررة ومرتبطة بالاستغلال.\n\n"
            "بشكل مبسط، قد تشمل:\n"
            "- مصاريف شراء السلع أو المواد المستعملة في النشاط.\n"
            "- بعض المصاريف الخارجية الضرورية للاستغلال.\n"
            "- مصاريف أخرى يقبلها القانون وفق الشروط المنصوص عليها في النص الجبائي.\n\n"
            "للتفاصيل الدقيقة، راجع النص الأصلي في المصادر أسفله."
        )
    if any(
        term in searchable
        for term in (
            "ضريب",
            "المصاريف",
            "التكاليف",
            "code général des impôts",
            "fiscalité",
        )
    ):
        return (
            "عثرت LexIA على مقتضيات ضريبية مرتبطة بالمصاريف أو التكاليف "
            "القابلة للخصم."
        )
    if any(term in searchable for term in ("مدونة الأسرة", "الطلاق", "الأسرة")):
        return (
            "عثرت LexIA على مقتضيات من مدونة الأسرة مرتبطة بالطلاق وقواعد "
            "الأسرة. لا تكفي الإشارة إلى هذا النص وحدها لشرح المسطرة أو آثارها، "
            "لذلك يرجى الرجوع إلى النص الأصلي في المصادر."
        )
    if any(
        term in searchable
        for term in ("مدونة الشغل", "علاقات الشغل", "الأجير", "licenciement")
    ):
        return (
            "عثرت LexIA على مقتضيات مرتبطة بإنهاء علاقة الشغل وحقوق الأجير. "
            "ويحدد النص الأصلي القواعد المرتبطة بالفصل أو التعويض أو الإخطار "
            "بحسب الحالة."
        )
    if any(
        term in searchable
        for term in ("مجموعة القانون الجنائي", "القانون الجنائي", "جريمة", "عقوبة")
    ):
        return (
            "عثرت LexIA على مقتضيات من القانون الجنائي مرتبطة بالفعل أو "
            "الجريمة والعقوبة المذكورتين في السؤال. ويجب الرجوع إلى النص الأصلي "
            "لمعرفة الوصف والعقوبة بدقة."
        )
    if any(term in searchable for term in ("حماية المستهلك", "المستهلك")):
        return (
            "عثرت LexIA على مقتضيات مرتبطة بحماية المستهلك، وقد تتعلق بحسب "
            "السؤال بالإعلام أو الضمان أو عيب المنتوج أو التزامات البائع."
        )
    if any(term in searchable for term in ("الكراء", "المكتري", "المكري", "loyer", "bail")):
        return (
            "عثرت LexIA على مقتضيات مرتبطة بالكراء وبحقوق أو التزامات المكري "
            "والمكتري وأداء الوجيبة الكرائية."
        )
    if any(term in searchable for term in ("المسطرة", "دعوى", "محكمة", "شكاية", "تبليغ", "استئناف")):
        return (
            "عثرت LexIA على مقتضيات مسطرية مرتبطة بالإجراء القضائي المذكور. "
            "ويجب الرجوع إلى النص الأصلي لمعرفة القواعد المناسبة للحالة بدقة."
        )
    if any(term in searchable for term in ("التعمير", "رخصة البناء", "البناء", "urbanisme")):
        return (
            "عثرت LexIA على مقتضيات مرتبطة بالتعمير أو البناء أو الترخيص المذكور "
            "في السؤال."
        )
    if any(term in searchable for term in ("محامي", "موثق", "المحاماة", "التوثيق", "avocat", "notaire")):
        return (
            "عثرت LexIA على مقتضيات مرتبطة بالمهنة القانونية المذكورة ودورها، "
            "ويبين النص الأصلي مهامها والتزاماتها."
        )
    if any(term in searchable for term in ("شركة", "الشركاء", "المساهم", "société", "societe")):
        return (
            "عثرت LexIA على مقتضيات من قانون الشركات مرتبطة بنوع الشركة أو "
            "تأسيسها أو حقوق الشركاء المذكورة في السؤال."
        )
    return (
        "عثرت LexIA على نص قانوني مرتبط بموضوع سؤالك في المصدر المذكور. "
        "يمكنك الاطلاع على النص القانوني الأصلي في قسم المصادر المسترجعة أسفله."
    )


def _darija_simple_explanation(question, source):
    """Build a useful Latin-character Darija orientation without raw excerpts."""
    searchable = " ".join(
        str(value or "")
        for value in (
            question,
            source.get("category"),
            source.get("document_title"),
            source.get("title"),
            source.get("article_number"),
        )
    ).casefold()

    if any(term in searchable for term in ("charges déductibles", "masarif", "takalif")):
        return (
            "LexIA l9at qawa3id daribiya 3la les charges déductibles li "
            "mertabta b nchat dyal lmo9awala w b 7ssab bénéfice imposable. "
            "Tafasil w chourout kaynin f nass l2asli ta7t."
        )
    if any(term in searchable for term in ("divorc", "tla9", "طلاق", "مدونة الأسرة")):
        return (
            "LexIA l9at moqtadayat mn Modawwanat lOusra 3la tla9 w qawa3id "
            "l2osra. Lmasطرة w natayej kay7tajou rjou3 l nass l2asli."
        )
    if any(term in searchable for term in ("licenciement", "طرد", "فصل", "مدونة الشغل")):
        return (
            "LexIA l9at moqtadayat 3la nihayat contrat de travail w 7ou9ou9 "
            "l2ajir, b7al licenciement, ta3wid ola préavis 7sab l7ala."
        )
    if any(term in searchable for term in ("سرقة", "vol", "عقوبة", "القانون الجنائي")):
        return (
            "LexIA l9at moqtadayat mn l9anoun jina2i 3la ljarima w l3o9ouba "
            "lmadkourin. Khass rjou3 l nass l2asli bach tban tafasil b da9a."
        )
    if any(term in searchable for term in ("مستهلك", "consommateur", "ضمان", "عيب")):
        return (
            "LexIA l9at moqtadayat 3la 7imayat lmostahlik, b7al lma3loumat, "
            "daman, 3ib f produit ola wajibat lba2i3 7sab soualek."
        )
    if any(term in searchable for term in ("كراء", "bail", "loyer", "مكتري", "مكري")):
        return (
            "LexIA l9at moqtadayat 3la lkra, 7ou9ou9 w wajibat lmokri w "
            "lmoktari, ola lwajiba lkara2iya."
        )
    if any(term in searchable for term in ("مسطرة", "دعوى", "محكمة", "شكاية", "procedure")):
        return (
            "LexIA l9at moqtadayat 3la lmassara qanouniya li glti. Khass "
            "tchouf nass l2asli bach t3ref l9awa3id li katnasb l7ala dyalek."
        )
    if any(term in searchable for term in ("التعمير", "البناء", "urbanisme", "construction")):
        return (
            "LexIA l9at moqtadayat 3la ta3mir, bina ola rokhsat li kayhder "
            "3liha soualek."
        )
    if any(term in searchable for term in ("محامي", "موثق", "avocat", "notaire")):
        return (
            "LexIA l9at moqtadayat 3la lmehna qanouniya li dkerti w dawr dyalha."
        )
    if any(term in searchable for term in ("شركة", "الشركاء", "société", "societe", "actionnaire")):
        return (
            "LexIA l9at moqtadayat mn qanoun charikat 3la naw3 charika, "
            "ta2sis dyalha ola 7ou9ou9 choraka."
        )
    return (
        "LexIA l9at nass qanouni mertabet b soualek f had document. "
        "T9der tchouf nass l2asli kamel f lmasadir li lte7t."
    )


def build_structured_answer(question, sources, language="fr"):
    source = sources[0]
    article_number = source.get("article_number") or "article non précisé"
    displayed_article = _display_article_reference(article_number, language)
    document_title = source.get("document_title", "")
    if language == "darija":
        simple_explanation = _darija_simple_explanation(question, source)
        return (
            "7sab lmasadir li rj3athom LexIA, aqrab nass qanouni l soualek "
            f"howa {displayed_article} mn {document_title}.\n\n"
            "B tariqa bsita:\n"
            f"{simple_explanation}\n\n"
            f"Lmasdar lra2issi: {document_title}, {displayed_article}."
        )
    if language == "ar":
        simple_explanation = _arabic_simple_explanation(question, source)
        return (
            "حسب المصادر التي استرجعتها LexIA، فإن أقرب نص قانوني مرتبط بسؤالك هو "
            f"{displayed_article} من {document_title}.\n\n"
            "بشكل مبسط:\n"
            f"{simple_explanation}\n\n"
            "المصدر الرئيسي:\n"
            f"{document_title}، {displayed_article}."
        )

    simple_explanation = _french_simple_explanation(question, source)
    return (
        "Selon les sources récupérées par LexIA, le texte le plus pertinent est "
        f"{article_number} de {document_title}.\n\n"
        "En termes simples :\n"
        f"{simple_explanation}\n\n"
        f"Source principale : {document_title}, {article_number}."
    )


def run_rag_pipeline(question, language="fr", retrieval_limit=3):
    is_darija = language == "darija"
    is_arabic = language == "ar"
    intent = detect_basic_intent(question)

    if intent == "greeting":
        answer = ARABIC_GREETING_ANSWER if is_arabic else (DARJA_GREETING_ANSWER if is_darija else GREETING_ANSWER)
        return {"answer": answer, "sources": [], "answer_mode": "greeting"}
    if intent == "thanks":
        answer = ARABIC_THANKS_ANSWER if is_arabic else (DARJA_THANKS_ANSWER if is_darija else THANKS_ANSWER)
        return {"answer": answer, "sources": [], "answer_mode": "thanks"}
    if intent == "off_topic":
        return {
            "answer": ARABIC_OFF_TOPIC_ANSWER if is_arabic else (DARJA_OFF_TOPIC_ANSWER if is_darija else OFF_TOPIC_ANSWER),
            "sources": [],
            "answer_mode": "off_topic",
        }
    unclear_domain = detect_unclear_legal_domain(question)
    if unclear_domain:
        return {
            "answer": get_unclear_legal_answer(unclear_domain, language),
            "sources": [],
            "answer_mode": "unclear_legal",
        }
    if detect_knowledge_scope(question) == "out_of_scope":
        return {
            "answer": ARABIC_OUT_OF_SCOPE_ANSWER if is_arabic else (DARJA_OUT_OF_SCOPE_ANSWER if is_darija else OUT_OF_SCOPE_ANSWER),
            "sources": [],
            "answer_mode": "out_of_scope",
        }

    entries = search_knowledge_hybrid(question, limit=retrieval_limit)
    if not entries:
        return {
            "answer": get_fallback_answer(language),
            "sources": [],
            "answer_mode": "fallback",
        }

    internal_sources = [_source_from_entry(entry) for entry in entries]
    public_sources = [_public_source(source) for source in internal_sources]
    structured_answer = build_structured_answer(question, internal_sources, language)

    if is_llm_enabled():
        context = build_context_from_sources(internal_sources)
        generated_answer = generate_answer_or_fallback(
            question,
            context,
            structured_answer,
            language,
        )
        if generated_answer != structured_answer:
            return {
                "answer": generated_answer,
                "sources": public_sources,
                "answer_mode": "llm",
            }
        if settings.DEBUG:
            logger.warning(
                "LLM did not return an answer; using the structured RAG answer."
            )

    return {
        "answer": structured_answer,
        "sources": public_sources,
        "answer_mode": "structured",
}
