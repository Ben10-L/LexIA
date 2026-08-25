import os

from django.core.management.base import BaseCommand, CommandError

from rag.llm import (
    generate_answer_with_gemini,
    get_llm_model,
    log_llm_failure,
)


class Command(BaseCommand):
    help = "Test the configured Gemini model without displaying the API key."

    def handle(self, *args, **options):
        provider = "gemini"
        model = get_llm_model(provider)
        api_key = os.getenv("GEMINI_API_KEY", "").strip()

        self.stdout.write(f"Provider: {provider}")
        self.stdout.write(f"Model: {model}")
        self.stdout.write(f"API key configured: {'yes' if api_key else 'no'}")

        try:
            answer = generate_answer_with_gemini(
                "Réponds simplement que le test LexIA fonctionne.",
                "Ceci est un test technique de connexion au fournisseur Gemini.",
            )
        except Exception as exception:
            log_llm_failure(provider, model, exception, api_key)
            raise CommandError(
                "Gemini test failed: "
                f"{exception.__class__.__name__}: "
                f"{str(exception).replace(api_key, '[REDACTED]') if api_key else exception}"
            ) from exception

        if not answer:
            raise CommandError("Gemini returned an empty answer.")

        self.stdout.write(self.style.SUCCESS("Gemini test succeeded."))
        self.stdout.write(f"Response preview: {answer[:200]}")
