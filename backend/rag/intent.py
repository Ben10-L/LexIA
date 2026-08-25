import re
import unicodedata

GREETING_ANSWER = (
    "Bonjour, je suis LexIA, un assistant d’orientation juridique marocaine. "
    "Posez-moi une question juridique, par exemple sur la fiscalité, les sociétés "
    "ou les opérations de change."
)
THANKS_ANSWER = (
    "Je vous en prie. Vous pouvez me poser une autre question juridique si vous "
    "le souhaitez."
)
OFF_TOPIC_ANSWER = (
    "Je suis LexIA, un assistant d’orientation juridique marocaine. Je peux vous "
    "aider uniquement avec des questions juridiques couvertes par ma base de "
    "connaissances, notamment la fiscalité, les sociétés et les opérations de change."
)
OUT_OF_SCOPE_ANSWER = (
    "Cette question semble juridique, mais elle ne fait pas encore partie des "
    "domaines couverts par la base de connaissances actuelle de LexIA. Pour le "
    "moment, LexIA couvre principalement la fiscalité, les sociétés anonymes et "
    "les opérations de change."
)
DARJA_GREETING_ANSWER = (
    "Ssalamu 3alaykum, ana LexIA, assistant dyal tawjih qanouni mghribi. "
    "T9der tswelni 3la fiscalité, sociétés anonymes, ola opérations de change."
)
DARJA_THANKS_ANSWER = (
    "Bla jmil. T9der tswelni 3la chi soual qanouni akhor ila bghiti."
)
DARJA_OFF_TOPIC_ANSWER = (
    "N9der n3awnek ghir f l’as2ila qanouniya li kaynin f base dyal LexIA, "
    "b7al fiscalité, sociétés anonymes, w opérations de change."
)
DARJA_OUT_OF_SCOPE_ANSWER = (
    "Had soual kayban qanouni, walakin mazal ma kaynch f domaines li "
    "katghatihom base dyal LexIA daba. Daba LexIA katghati bzzaf fiscalité, "
    "sociétés anonymes, w opérations de change."
)
ARABIC_GREETING_ANSWER = (
    "مرحبا، أنا LexIA، مساعد للتوجيه القانوني المغربي. يمكنك أن تسألني حول "
    "الضرائب، الشركات المساهمة، أو عمليات الصرف."
)
ARABIC_THANKS_ANSWER = "على الرحب والسعة. يمكنك طرح سؤال قانوني آخر إذا أردت."
ARABIC_OFF_TOPIC_ANSWER = (
    "يمكنني مساعدتك فقط في الأسئلة القانونية الموجودة في قاعدة معرفة LexIA، "
    "خصوصا الضرائب، الشركات المساهمة، وعمليات الصرف."
)
ARABIC_OUT_OF_SCOPE_ANSWER = (
    "يبدو أن هذا السؤال قانوني، لكنه لا يدخل بعد ضمن المجالات التي تغطيها قاعدة "
    "معرفة LexIA حاليا. في الوقت الحالي، تغطي LexIA أساسا الضرائب، الشركات "
    "المساهمة، وعمليات الصرف."
)

UNCLEAR_LEGAL_ANSWERS = {
    "fr": {
        "corporate_tax": (
            "Votre question concerne l’impôt sur les sociétés, mais elle n’est "
            "pas assez précise. Parlez-vous du taux, de la déclaration, du "
            "paiement, d’une exonération, de la cotisation minimale ou des "
            "charges déductibles ?"
        ),
        "fiscal": (
            "Votre question semble liée à la fiscalité, mais elle n’est pas assez "
            "précise. Précisez si vous parlez de TVA, d’impôt sur les sociétés, "
            "d’impôt sur le revenu ou d’une situation fiscale particulière ?"
        ),
        "family": (
            "Votre question semble liée au droit de la famille, mais elle n’est "
            "pas assez précise. Précisez si elle concerne le mariage, le divorce, "
            "la pension alimentaire ou la garde des enfants ?"
        ),
        "labour": (
            "Votre question semble liée au droit du travail, mais elle n’est pas "
            "assez précise. Précisez si elle concerne le contrat, le salaire, le "
            "licenciement ou une indemnité ?"
        ),
        "court": (
            "Votre question semble liée à une procédure judiciaire, mais elle "
            "n’est pas assez précise. Précisez si elle concerne une plainte, une "
            "action civile, un recours ou une notification ?"
        ),
        "general": (
            "Votre question semble juridique, mais elle n’est pas assez précise. "
            "Concerne-t-elle la fiscalité, la famille, le travail, une entreprise "
            "ou une procédure judiciaire ?"
        ),
    },
    "ar": {
        "corporate_tax": (
            "سؤالك مرتبط بالضريبة على الشركات، لكنه غير محدد بما يكفي. هل تقصد "
            "نسبة الضريبة، التصريح، الأداء، الإعفاء، الحد الأدنى للضريبة، أو "
            "المصاريف القابلة للخصم؟"
        ),
        "fiscal": (
            "سؤالك مرتبط بالضرائب، لكنه غير محدد بما يكفي. هل تقصد TVA، الضريبة "
            "على الشركات، الضريبة على الدخل، أو نسبة ضريبية مرتبطة بحالة معينة؟"
        ),
        "family": (
            "سؤالك مرتبط بقانون الأسرة، لكنه غير محدد بما يكفي. هل تقصد الزواج، "
            "الطلاق، النفقة، أو الحضانة؟"
        ),
        "labour": (
            "سؤالك مرتبط بقانون الشغل، لكنه غير محدد بما يكفي. هل تقصد عقد الشغل، "
            "الأجر، الفصل من العمل، أو التعويض؟"
        ),
        "court": (
            "سؤالك مرتبط بإجراء قضائي، لكنه غير محدد بما يكفي. هل تقصد شكاية، "
            "دعوى مدنية، استئنافا، أو تبليغا؟"
        ),
        "general": (
            "سؤالك يبدو قانونيا، لكنه غير محدد بما يكفي. يرجى تحديد المجال ووصف "
            "الحالة باختصار: هل يتعلق بالضرائب، الأسرة، الشغل، الشركات، أو إجراء قضائي؟"
        ),
    },
    "darija": {
        "corporate_tax": (
            "Soualek 3la daribat charikat, walakin ma wade7ch bzzaf. Wach "
            "katqsed taux, déclaration, paiement, exonération, cotisation "
            "minimale, wla charges déductibles?"
        ),
        "fiscal": (
            "Soualek kayban 3ando 3ala9a b dariba, walakin ma wade7ch bzzaf. "
            "Wach katqsed TVA, daribat charikat, daribat dakhl, wla chi 7ala mo3ayana?"
        ),
        "family": (
            "Soualek kayban 3la l2osra, walakin ma wade7ch bzzaf. Wach katqsed "
            "zwaj, tla9, nafa9a, wla 7adana?"
        ),
        "labour": (
            "Soualek kayban 3la choghl, walakin ma wade7ch bzzaf. Wach katqsed "
            "contrat, salaire, licenciement, wla ta3wid?"
        ),
        "court": (
            "Soualek kayban 3la chi massara qanouniya, walakin ma wade7ch bzzaf. Wach "
            "katqsed chikaya, da3wa madaniya, isti2naf, wla tabligh?"
        ),
        "general": (
            "Soualek kayban qanouni, walakin ma wade7ch bzzaf. 7edded domaine "
            "w chre7 lina l7ala dyalek b ikhtisar: dariba, l2osra, choghl, "
            "charika, wla massara qanouniya?"
        ),
    },
}

UNCLEAR_LEGAL_PATTERNS = {
    "corporate_tax": {
        "الضريبة على الشركات",
        "ما هي الضريبة على الشركات",
        "impot sur les societes",
        "is",
    },
    "fiscal": {
        "نسبة الضريبة", "ثمن الضرائب", "ثمن الضرايب", "شحال الضريبة",
        "الضرائب", "الضرايب", "الضريبة",
        "taux d impot", "impot", "taxes", "fiscalite", "tva",
        "ch7al dariba", "chno dariba", "dariba",
    },
    "family": {"الاسرة", "الزواج", "الطلاق", "famille", "mariage", "divorce"},
    "labour": {"الخدمة", "الشغل", "travail", "khdma", "lkhdma", "choghl"},
    "court": {"المحكمة", "دعوى", "tribunal", "proces", "da3wa", "lmahkama"},
    "general": {
        "القانون", "شنو القانون", "عندي مشكل قانوني", "بغيت نسول على القانون",
        "droit", "j ai un probleme juridique", "probleme juridique",
        "bghit nsowel 3la l9anoun", "3andi mochkil qanouni", "l9anoun",
        "chno ndir",
    },
}

GREETINGS = {
    "bonjour",
    "salut",
    "salam",
    "salam alaykoum",
    "السلام عليكم",
    "hello",
    "hi",
    "bonsoir",
    "slm",
    "bslama",
    "labas",
    "kif nta",
    "kif dayr",
    "wach labas",
    "مرحبا",
    "اهلا",
    "صباح الخير",
    "مساء الخير",
}
THANKS = {
    "merci",
    "merci beaucoup",
    "thanks",
    "thank you",
    "شكرا",
    "شكرا لك",
    "chokran",
    "chokran bzaf",
    "lah yhafdek",
    "barak llah fik",
    "شكرا جزيلا",
    "بارك الله فيك",
}
LEGAL_TERMS = {
    "droit",
    "juridique",
    "loi",
    "article",
    "fiscal",
    "fiscale",
    "fiscales",
    "fiscaux",
    "fiscalite",
    "impot",
    "taxe",
    "societe",
    "entreprise",
    "anonyme",
    "change",
    "paiement",
    "etranger",
    "charges",
    "deductible",
    "contrat",
    "dariba",
    "daraib",
    "charjat",
    "masarif",
    "ribh",
    "charika",
    "charikat",
    "mo9awala",
    "mosahimin",
    "ra2smal",
    "srf",
    "الضرائب",
    "الضريبة",
    "الرسم",
    "التكاليف",
    "المصاريف",
    "الربح",
    "الشركة",
    "شركة",
    "المساهمون",
    "المساهمين",
    "الصرف",
    "الاستيراد",
    "التصدير",
    "طلاق",
    "الطلاق",
    "زواج",
    "نفقة",
    "حضانة",
    "الشغل",
    "الخدمة",
    "طردوني",
    "جنائي",
    "جريمة",
    "الجريمة",
    "سرقة",
    "عقوبة",
    "شكاية",
    "دعوى",
    "محكمة",
    "المحكمة",
    "كراء",
    "الكراء",
    "فالكراء",
    "عقار",
    "العقاري",
    "مستهلك",
    "المستهلك",
    "التعمير",
    "محامي",
    "المحامي",
    "موثق",
}
OFF_TOPIC_TERMS = {
    "telephone",
    "smartphone",
    "blague",
    "recette",
    "meteo",
    "restaurant",
    "film",
    "sport",
    "nokta",
    "lmeteo",
    "nakol",
    "هاتف",
    "نكتة",
    "الطقس",
    "مطعم",
    "وصفة",
}
PERSONAL_QUESTIONS = {
    "quel age as tu",
    "quelle age a tu",
    "quel age a tu",
    "quelle age as tu",
    "tu as quel age",
    "qui es tu",
    "comment tu t appelles",
    "tu t appelles comment",
    "es tu humain",
    "tu es humain",
    "how old are you",
    "who are you",
}

IN_SCOPE_TERMS = {
    "fiscalite",
    "fiscal",
    "fiscale",
    "fiscales",
    "fiscaux",
    "impot",
    "impots",
    "taxe",
    "taxes",
    "tva",
    "charge",
    "charges",
    "deductible",
    "deductibles",
    "benefice",
    "imposable",
    "societe",
    "societes",
    "anonyme",
    "actionnaire",
    "actionnaires",
    "capital",
    "conseil",
    "administration",
    "assemblee",
    "constitution",
    "change",
    "paiement",
    "virement",
    "international",
    "devise",
    "devises",
    "import",
    "export",
    "resident",
    "dariba",
    "daraib",
    "tax",
    "charjat",
    "masarif",
    "ribh",
    "charika",
    "charikat",
    "mo9awala",
    "mosahimin",
    "ra2smal",
    "srf",
    "lbarra",
    "الضرائب",
    "الضريبة",
    "الرسم",
    "التكاليف",
    "المصاريف",
    "الربح",
    "الشركة",
    "شركة",
    "المساهمون",
    "المساهمين",
    "المال",
    "الصرف",
    "العملات",
    "تحويل",
    "الدفع",
    "الاستيراد",
    "التصدير",
    "مقيم",
    "الحوالة",
    "التحويل",
    "الاداء",
    "ارسال",
    "الاموال",
    "المقيمين",
    "divorce",
    "divorcer",
    "mariage",
    "pension",
    "licenciement",
    "travail",
    "salaire",
    "conge",
    "penal",
    "plainte",
    "prison",
    "tribunal",
    "bail",
    "location",
    "immobilier",
    "consommateur",
    "urbanisme",
    "avocat",
    "notaire",
    "tla9",
    "zwaj",
    "nafa9a",
    "khdma",
    "lkra",
    "طلاق",
    "الطلاق",
    "نطلق",
    "زواج",
    "نفقة",
    "حضانة",
    "الشغل",
    "الخدمة",
    "طردوني",
    "جنائي",
    "جريمة",
    "الجريمة",
    "سرقة",
    "عقوبة",
    "شكاية",
    "دعوى",
    "محكمة",
    "المحكمة",
    "حكم",
    "الحكم",
    "تبليغ",
    "الشرطة",
    "متابعة",
    "كراء",
    "الكراء",
    "فالكراء",
    "عقار",
    "العقاري",
    "ملكية",
    "مستهلك",
    "المستهلك",
    "كمستهلك",
    "ضمان",
    "الضمان",
    "منتوج",
    "عيب",
    "التعمير",
    "البناء",
    "محامي",
    "المحامي",
    "موثق",
    "الموثق",
    "توثيق",
    "عدول",
    "النفقة",
    "الحضانة",
    "الزوجة",
    "الاطفال",
    "الطرد",
    "الفصل",
    "تعويض",
    "التعويض",
    "الاخطار",
    "الجسيم",
    "نصب",
    "النصب",
    "الضرب",
    "الجرح",
    "التزوير",
    "المتابعة",
    "التبليغ",
    "استئناف",
    "نستانف",
    "المكري",
    "المكتري",
    "الوجيبة",
    "يخرجني",
    "العقارية",
    "العينية",
    "منتوج",
    "البائع",
    "البايع",
    "المحاماة",
    "التوثيق",
    "التضامن",
    "التوصية",
    "الشركاء",
}
IN_SCOPE_PHRASES = {
    "societe anonyme",
    "societes anonymes",
    "conseil d administration",
    "operations de change",
    "operation de change",
    "paiement vers l etranger",
    "virement international",
    "non resident",
    "chno n9der n9tes",
    "jam3iya 3ama",
    "lflos lbarra",
    "paiement lbarra",
    "transfert lbarra",
    "القيمة المضافة",
    "المصاريف القابلة للخصم",
    "الربح الخاضع للضريبة",
    "النتيجة الجبائية",
    "شركة مساهمة",
    "شركة مجهولة الاسم",
    "راس المال",
    "مجلس الادارة",
    "الجمعية العامة",
    "تاسيس الشركة",
    "عمليات الصرف",
    "العملات الاجنبية",
    "تحويل دولي",
    "تحويل الى الخارج",
    "الدفع الى الخارج",
    "غير مقيم",
    "الحوالة الى الخارج",
    "الاداء الى الخارج",
    "ارسال الاموال الى الخارج",
    "تحويل الاموال الى الخارج",
    "غير المقيمين",
    "pension alimentaire",
    "contrat de travail",
    "droit immobilier",
    "protection du consommateur",
    "autorisation de construire",
    "بغيت نطلق",
    "مدونة الاسرة",
    "مدونة الشغل",
    "القانون الجنائي",
    "مسطرة مدنية",
    "المسطرة المدنية",
    "مسطرة جنائية",
    "المسطرة الجنائية",
    "النيابة العامة",
    "عقد العمل",
    "الفصل من العمل",
    "تحفيظ عقاري",
    "التحفيظ العقاري",
    "حقوق عينية",
    "حماية المستهلك",
    "رخصة البناء",
    "التجزئة العقارية",
    "اجل الاخطار",
    "الخطا الجسيم",
    "الضرب والجرح",
    "الملكية العقارية",
    "الحقوق العينية",
    "الوجيبة الكرائية",
    "الرسم العقاري",
    "شركة التضامن",
    "شركة التوصية البسيطة",
    "مهنة المحاماة",
    "مهنة التوثيق",
}
OUT_OF_SCOPE_TERMS = {
    "heritage",
    "lwirta",
    "الارث",
}
OUT_OF_SCOPE_PHRASES = {
    "droit international",
    "القانون الدولي",
    "international law",
}


def normalize_text(text):
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^\w\s]", " ", without_accents, flags=re.UNICODE)
    return " ".join(normalized.split())


def detect_basic_intent(question):
    normalized = normalize_text(question)

    if normalized in GREETINGS:
        return "greeting"
    if normalized in THANKS:
        return "thanks"

    words = set(normalized.split())
    if words.intersection(LEGAL_TERMS):
        return "legal"
    if normalized in PERSONAL_QUESTIONS:
        return "off_topic"
    if words.intersection(OFF_TOPIC_TERMS):
        return "off_topic"
    return "legal"


def detect_unclear_legal_domain(question):
    """Return the vague legal domain when a question needs clarification."""
    normalized = normalize_text(question)
    for domain, patterns in UNCLEAR_LEGAL_PATTERNS.items():
        if normalized in patterns:
            return domain
    return None


def get_unclear_legal_answer(domain, language="fr"):
    answers = UNCLEAR_LEGAL_ANSWERS.get(language, UNCLEAR_LEGAL_ANSWERS["fr"])
    return answers.get(domain, answers["general"])


def detect_knowledge_scope(question):
    normalized = normalize_text(question)
    words = set(normalized.split())

    if words.intersection(OUT_OF_SCOPE_TERMS) or any(
        phrase in normalized for phrase in OUT_OF_SCOPE_PHRASES
    ):
        return "out_of_scope"
    if words.intersection(IN_SCOPE_TERMS) or any(
        phrase in normalized for phrase in IN_SCOPE_PHRASES
    ):
        return "in_scope"
    return "out_of_scope"
