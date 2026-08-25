# LexIA frontend

First React interface for LexIA, the Moroccan legal assistant.

## Stack

- React 18
- TypeScript
- Vite
- TailwindCSS
- Axios

## Run locally

```bash
cd /Users/mac/Documents/LexIA/frontend
npm install
npm run dev
```

Open `http://localhost:5173/`. The Django backend must be running at `http://127.0.0.1:8000/`.

To use another backend URL, copy `.env.example` to `.env` and edit `VITE_API_BASE_URL`.

## Production build

```bash
npm run build
```

Feedback buttons submit positive or negative ratings to `/api/feedback/` using the saved assistant message ID returned by `/api/chat/`.
