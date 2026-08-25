# LexIA — Assistant Juridique Marocain Intelligent

LexIA is a Moroccan legal-orientation chatbot. It combines a Django REST API, a React interface, hybrid ORM/ChromaDB retrieval, and optional Gemini or OpenAI answer generation. The LLM layer is disabled by default, and structured answers continue to work without an external API.

> **Legal notice:** LexIA provides information and legal orientation only. It does not replace a lawyer, judge, notary, or official legal authority.

## Tech stack

- **Backend:** Django, Django REST Framework, SQLite, ChromaDB, sentence-transformers
- **Optional LLMs:** Gemini and OpenAI through their official SDKs
- **Frontend:** React, TypeScript, Vite, TailwindCSS, Axios
- **Quality:** Django tests and a retrieval-only RAG evaluation suite

## Folder structure

```text
LexIA/
├── backend/                 Django API, RAG pipeline, tests and commands
├── frontend/                React application
├── data/
│   ├── evaluation_questions.csv
│   ├── legal_txt_core/      Shared Moroccan legal TXT corpus
│   └── *.csv                Original legal CSV datasets
├── docker-compose.yml
├── README.md
└── .gitignore
```

The knowledge base includes the Code Général des Impôts 2024, IGOC 2024, company law, and the shared Moroccan legal TXT corpus. Covered areas include taxation, companies, foreign-exchange operations, family and labour law, criminal and civil procedure, real estate, consumer protection, urbanism, and legal professions. Answers always depend on the documents actually retrieved.

## Backend setup without Docker

Requirements: Python 3.11+ (Python 3.12 recommended).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000`.

## Frontend setup without Docker

Requirements: Node.js 20+.

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Vite serves the frontend at `http://localhost:5173`.

## Environment variables

Copy the tracked examples before starting either application:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

`backend/.env` controls Django, CORS, and optional LLM settings. `LEXIA_USE_LLM=false` is the safe default. To use an external provider locally, set the provider and its API key only in `backend/.env`.

`frontend/.env.local` defines `VITE_API_BASE_URL`. The default local value is `http://127.0.0.1:8000`.

## Import legal data

Run import commands from `backend/`. CSV imports remain available:

```bash
python manage.py import_legal_csv ../data/Code_General_des_Impots_2024.csv --category "Fiscalité" --document-title "Code Général des Impôts 2024"
python manage.py import_legal_csv ../data/IGOC_2024.csv --category "Change" --document-title "Instruction Générale des Opérations de Change 2024"
python manage.py import_legal_csv ../data/Loi_17-95.csv --category "Sociétés" --document-title "Loi n°17-95 relative aux sociétés anonymes"
```

Preview the shared TXT import first, then confirm it explicitly:

```bash
python manage.py import_legal_txt_folder --path ../data/legal_txt_core/
python manage.py import_legal_txt_folder --path ../data/legal_txt_core/ --confirm
```

Importing is never performed automatically by Docker startup.

## Index ChromaDB

After importing or changing legal entries, rebuild the semantic index:

```bash
cd backend
python manage.py index_knowledge_chroma
```

The local index is stored in `backend/chroma_db/` and is intentionally excluded from Git because it can be regenerated.

## Run tests and evaluation

Backend quality checks:

```bash
cd backend
python manage.py check
python manage.py test
LEXIA_USE_LLM=false python manage.py evaluate_rag
```

Frontend production build:

```bash
cd frontend
npm run build
```

The evaluation command explicitly disables external LLM calls and audits retrieval and answer-mode behavior against `data/evaluation_questions.csv`.

## Run with Docker

Create the local backend environment file before starting:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- Frontend: `http://localhost:5174`
- Backend: `http://127.0.0.1:8000`

The backend container runs migrations and starts Django. The frontend container starts the Vite development server. Source directories are bind-mounted for development, and ChromaDB plus frontend dependencies use named volumes.

Useful container commands:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py test
docker compose exec backend python manage.py index_knowledge_chroma
```

To import the mounted TXT corpus, first preview and then confirm:

```bash
docker compose exec backend python manage.py import_legal_txt_folder --path /data/legal_txt_core/
docker compose exec backend python manage.py import_legal_txt_folder --path /data/legal_txt_core/ --confirm
```

Stop the development services with `docker compose down`. Named volumes are preserved unless explicitly removed.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/chat/` | Ask a question and create or continue a conversation |
| `GET` | `/api/conversations/` | List conversations |
| `GET` | `/api/conversations/<id>/` | Retrieve a conversation |
| `GET`, `POST` | `/api/feedback/` | List or submit feedback |
| `GET` | `/api/stats/` | Read demo statistics |
| `GET` | `/api/health/` | Check backend configuration and service status |

## Common problems

- **CORS error:** ensure the frontend origin is present in `CORS_ALLOWED_ORIGINS`. The example supports ports 5173 and 5174.
- **No semantic results:** import the data and run `index_knowledge_chroma`.
- **Model download on first index/search:** sentence-transformers may download its embedding model the first time it is used.
- **Structured answer instead of LLM:** this is expected when `LEXIA_USE_LLM=false`, a key is missing, or the provider fails.
- **Docker cannot find `backend/.env`:** copy `backend/.env.example` before running Compose.
- **Port already in use:** stop the existing Django/Vite process or change the host-side port in `docker-compose.yml`.

## Security and collaboration notes

- Never commit `.env`, `.env.local`, API keys, SQLite databases, ChromaDB indexes, or generated build artifacts.
- Keep credentials in local environment files or a trusted secret manager.
- Review `git status` before every commit.
- Legal TXT files and `data/evaluation_questions.csv` are intentionally shareable project inputs; confirm their redistribution rights before publishing a public repository.
- Do not use Django's development server or this Compose configuration as a production deployment.
