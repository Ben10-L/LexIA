import os
import logging

from google import genai
from openai import OpenAI


logger = logging.getLogger(__name__)


def is_llm_enabled():
    return os.getenv("LEXIA_USE_LLM", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_llm_provider():
    return os.getenv("LEXIA_LLM_PROVIDER", "gemini").strip().lower()


def get_llm_model(provider):
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or (
            "gemini-2.5-flash"
        )
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    return "unknown"


def _safe_exception_message(exception, api_key=""):
    message = str(exception)
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


def log_llm_failure(provider, model, exception, api_key=""):
    logger.warning(
        "LLM generation failed: provider=%s model=%s exception=%s message=%s",
        provider,
        model,
        exception.__class__.__name__,
        _safe_exception_message(exception, api_key),
    )


def build_legal_prompt(question, context, language="fr"):
    if language == "darija":
        language_instruction = (
            "Réponds en darija marocaine écrite en caractères latins, comme les "
            "Marocains l’écrivent en ligne. Tu peux conserver les termes juridiques "
            "en français lorsqu’ils sont utiles ou plus précis. N’utilise pas "
            "l’écriture arabe, sauf si elle est strictement nécessaire. Cite les "
            "sources naturellement, par exemple : « 7sab Article 10 mn Code Général "
            "des Impôts 2024... ». "
        )
    elif language == "ar":
        language_instruction = (
            "أجب بلغة عربية فصحى حديثة وواضحة. يمكنك الاحتفاظ بالعناوين القانونية "
            "الرسمية وأسماء المواد باللغة الفرنسية عندما يكون ذلك أدق. اذكر المصادر "
            "بشكل طبيعي، مثلا: « حسب المادة Article 10 من Code Général des Impôts "
            "2024... ». "
        )
    else:
        language_instruction = (
            "Réponds clairement en français. Cite les articles naturellement dans "
            "le texte, par exemple : « Selon l’article 10 du Code Général des Impôts "
            "2024... ». "
        )
    return (
        "Tu es LexIA, un assistant d’orientation juridique marocaine. "
        f"{language_instruction} Utilise uniquement le contexte fourni. "
        "Indique explicitement que la réponse repose sur les sources LexIA récupérées. "
        "Si le contexte est insuffisant, dis-le clairement. "
        "Retourne uniquement du texte brut, sans syntaxe Markdown. "
        "N’utilise ni texte en gras avec des astérisques, ni titres Markdown, ni "
        "puces avec des astérisques, ni tableaux. Tu peux utiliser des lignes "
        "numérotées simples comme « 1. ... », « 2. ... », « 3. ... ». "
        "N’ajoute aucun avertissement juridique dans la réponse : le backend LexIA "
        "l’affiche déjà séparément. "
        "N’invente aucun article, procédure, institution, délai ou montant.\n\n"
        f"Question :\n{question}\n\n"
        f"Contexte juridique LexIA :\n{context}"
    )


def generate_answer_with_openai(question, context, language="fr"):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=get_llm_model("openai"),
        input=build_legal_prompt(question, context, language),
    )
    answer = response.output_text
    return answer.strip() if answer and answer.strip() else None


def generate_answer_with_gemini(question, context, language="fr"):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=get_llm_model("gemini"),
        contents=build_legal_prompt(question, context, language),
    )
    answer = response.text
    return answer.strip() if answer and answer.strip() else None


def generate_answer_or_fallback(question, context, fallback_answer, language="fr"):
    if not is_llm_enabled() or not context:
        return fallback_answer

    provider = get_llm_provider()
    model = get_llm_model(provider)
    try:
        if provider == "openai":
            answer = generate_answer_with_openai(question, context, language)
        elif provider == "gemini":
            answer = generate_answer_with_gemini(question, context, language)
        else:
            return fallback_answer
        return answer or fallback_answer
    except Exception as exception:
        api_key = (
            os.getenv("GEMINI_API_KEY", "").strip()
            if provider == "gemini"
            else os.getenv("OPENAI_API_KEY", "").strip()
        )
        log_llm_failure(provider, model, exception, api_key)
        return fallback_answer
