# Architecture — AuthentiScan AI

## 1. High-Level Overview

AuthentiScan AI is a monolithic Django application (no separate frontend build step)
split into three focused apps, plus a shared LLM client module:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Django Project (config)                     │
│                                                                       │
│   ┌────────────┐   ┌───────────────┐   ┌───────────────┐             │
│   │    core    │   │   detector    │   │   chatbot     │             │
│   │────────────│   │───────────────│   │───────────────│             │
│   │ landing    │   │ upload form   │   │ chat page     │             │
│   │ about      │   │ forensics.py  │   │ ChatSession   │             │
│   │ contributors│  │ ScanResult    │   │ ChatMessage   │             │
│   └─────┬──────┘   └───────┬───────┘   └───────┬───────┘             │
│         │                  │                   │                     │
│         └──────────────────┼───────────────────┘                     │
│                            ▼                                         │
│                    ┌───────────────┐                                 │
│                    │  common/llm.py │  ← reads OPENCODE_* from .env   │
│                    └───────┬───────┘                                 │
└────────────────────────────┼─────────────────────────────────────────┘
                             ▼
                 OpenCode Zen API (OpenAI-compatible)
                 https://opencode.ai/zen/v1/chat/completions
                 model = deepseek-v4-flash-free
```

## 2. App Responsibilities

### `core`
- Landing page (marketing/pitch + methodology teaser + CTA)
- `/about/` — detailed methodology write-up (ELA, noise analysis, EXIF forensics)
- `/contributors/` — team page, institute branding, reads `settings.CONTRIBUTORS`
- `core/context_processors.py` — injects project/institute name into every template

### `detector`
- `models.ScanResult` — one row per uploaded image: scores, verdict, metadata JSON,
  paths to the original image and generated ELA heatmap, and the cached LLM explanation
- `forensics.py` — the actual forensic pipeline (pure functions, no Django dependency
  beyond file paths), see [`FLOW.md`](FLOW.md) for the detailed algorithm walkthrough
- `forms.ImageUploadForm` — validates file type/size before it touches disk
- `views.upload` — handles GET (show form) / POST (save file → run forensics → redirect)
- `views.result` — displays a `ScanResult`; lazily triggers the LLM explanation on
  first view and caches it (`explanation_generated` flag) so repeat visits don't
  re-call the LLM
- `views.history` — lists recent scans

### `chatbot`
- `models.ChatSession` — optionally linked to a `ScanResult` (via `?scan=<uuid>`)
- `models.ChatMessage` — role (`user`/`assistant`/`system`) + content, ordered by time
- `views.chat_page` — creates a fresh session per visit and renders the chat shell
- `views.send_message` — AJAX (JSON) endpoint: persists the user message, builds a
  bounded conversation history (last 12 messages) plus optional scan context, calls
  the shared LLM client, persists and returns the assistant's reply

### `common/llm.py`
- The **only** place that talks to the network for AI inference.
- Reads `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `OPENCODE_MODEL`,
  `OPENCODE_TIMEOUT_SECONDS` from Django settings (which read them from `.env`).
- Exposes `is_configured()` and `chat_completion(messages, ...)`.
- Raises typed exceptions (`LLMConfigurationError`, `LLMRequestError`) that calling
  views catch and turn into friendly, non-crashing UI messages.

## 3. Data Model

```
ScanResult
├── id (UUID, PK)
├── image (ImageField)              — original upload
├── ela_heatmap (ImageField)        — generated ELA difference map
├── original_filename
├── ela_score, noise_score,
│   metadata_score, ai_likelihood   (floats, 0-100)
├── verdict                         (likely_human / uncertain / likely_ai)
├── metadata_json                   (dict: dimensions, EXIF sample, raw ELA stats)
├── explanation_text, explanation_generated
└── created_at

ChatSession
├── id (UUID, PK)
├── scan → ScanResult (nullable FK)
└── created_at

ChatMessage
├── session → ChatSession (FK)
├── role (user / assistant / system)
├── content
└── created_at
```

SQLite is used by default for zero-configuration grading/submission; swapping to
PostgreSQL/MySQL only requires changing `DATABASES` in `config/settings.py`.

## 4. Frontend Architecture

- **No JS framework / build step.** Templates are server-rendered Django templates
  extending a single `templates/base.html` (navbar, footer, font/icon CDN includes).
- **Design system** lives entirely in `static/css/style.css` as CSS custom properties
  (`:root` tokens for color, radius, shadow, font) — one file to re-theme the whole app.
- **Scroll animations**: `static/js/main.js` uses `IntersectionObserver` to add an
  `is-visible` class to any element with `.reveal` (with `.reveal-delay-*` stagger
  variants) — no external animation library, respects `prefers-reduced-motion`.
- **Score bars / likelihood meter**: animated via a `data-fill-width` attribute that
  `main.js` applies as the element's `width` shortly after page load, producing a
  "counting up" fill animation.
- **Chat**: `static/js/chat.js` does a plain `fetch()` POST to the session's send-URL
  with the Django CSRF cookie attached, appends messages to the log, and shows an
  animated "typing" indicator while waiting for the reply.
- **Icons**: [Lucide](https://lucide.dev) loaded via CDN (`<script src="unpkg.com/lucide">`)
  and initialized with `lucide.createIcons()` — icons are plain `<i data-lucide="...">`
  tags anywhere in the templates.

## 5. Configuration & Secrets

All environment-dependent values live in `.env` (see `.env.example`), loaded via
`python-dotenv` in `config/settings.py`:

- `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `OPENCODE_MODEL`, `OPENCODE_TIMEOUT_SECONDS`
- `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `MAX_UPLOAD_SIZE_MB`

No secret or model name is hard-coded anywhere in the Python source — everything
funnels through `settings.py`, which is the single source of truth read from `.env`.

## 6. Security & Validation Notes

- Uploads are validated for content-type and size (`ImageUploadForm.clean_image`)
  before being saved to disk.
- CSRF protection is enabled globally; the chat AJAX endpoint reads the CSRF cookie
  from JS rather than disabling protection.
- The LLM client never receives the raw image — only numeric scores and metadata
  text — keeping the blast radius of any prompt-injection-via-filename concerns low
  (filenames are stored but not interpolated into LLM prompts).
- `ScanResult` and `ChatMessage` records are read-only in the Django admin
  (fields listed as `readonly_fields`) to preserve scan integrity for review.
