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

## Scanned PDFs with Docling (runs on your machine, nothing leaves it)

Needs about 6 GB free disk, 8 GB RAM recommended, and internet access once to download the models from Hugging Face.

```bash
pip install -r requirements-ocr.txt
docling-tools models download      # one-time model download (skip it and the first scan downloads them instead)
```

In `.env` set `OCR_ENGINE=docling` and `OCR_VERIFY=0` (a single reader). Then check it:

```bash
python scripts/check_ocr.py --pages 2
```

You want PASS on "an OCR engine is available", "read the scanned pages" and "line positions are usable". The first run is slow
(models load); later runs are faster. `GET http://localhost:8000/api/health` should show `"ocr":{"enabled":true,"engine":"docling",...}`.

With one reader, every value taken from a scanned page is sent to the review queue by design. For a cross-check add a second
reader (Qwen or an LM Studio vision model, see docs/ocr.md) and remove `OCR_VERIFY=0`.

**Not verified:** a full Docling run. It was built and tested against Docling's own classes, but its models could not be
downloaded in the build sandbox. If `check_ocr.py` fails, send me its output (it prints no secrets or page text).
