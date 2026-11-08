# Run locally (default ports)

Needs Python 3.11+ and Node 22. Windows: use `py -m venv .venv` and `.venv\Scripts\activate`.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install && npm --prefix frontend install
cp .env.local.example .env      # then fill in the blanks
npm run dev                     # API http://localhost:8000, web http://localhost:5173
```

Open http://localhost:5173. Without Azure keys the app starts, but extraction and chat will not work.

- **Mode 1 (AUTH_MODE=off):** no login, no database; data stays in local folders. Only for your own machine.
- **Mode 2 (Supabase):** use the commented block in `.env.local.example`, then `npm run build && npm run serve` and open http://localhost:8000.
  In Supabase > Authentication > URL Configuration add `http://localhost:8000/**` to Redirect URLs.
  Confirmation emails still need working email delivery in Supabase (see docs/supabase-setup.md).
- **Scanned PDFs:** set QWEN_* (see docs/ocr.md). Optional local OCR tests: `apt install tesseract-ocr`.
- Tests: `python -m pytest -q`. Database tests skip unless a local PostgreSQL is on 127.0.0.1:54329.
