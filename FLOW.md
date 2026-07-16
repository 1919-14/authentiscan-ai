# Project Flow — AuthentiScan AI

This document walks through exactly what happens, step by step, from a user opening
the site to receiving an AI-generation likelihood verdict and chatting about it.

## 1. Landing → Authenticator

```
User opens "/"
   │
   ▼
core.views.landing()
   │  queries ScanResult.objects.count() / filter(ai_likelihood>=60).count()
   ▼
templates/core/landing.html rendered
   │  hero, "how it works" cards, 4-step flow, CTA
   ▼
User clicks "Authenticate an Image" → GET /scan/
```

## 2. Upload & Forensic Scan

```
GET /scan/  → detector.views.upload()
   │  renders empty ImageUploadForm + recent scans
   ▼
User selects/drops a file → POST /scan/  (multipart/form-data)
   │
   ▼
ImageUploadForm.clean_image()
   │  rejects if > MAX_UPLOAD_SIZE_BYTES or wrong content-type
   ▼
ScanResult.objects.create(image=uploaded, original_filename=...)
   │  Django saves the file to media/uploads/<uuid>.<ext>
   ▼
detector.forensics.analyze_image(scan.image.path, ela_output_path)
   │
   ├─ 1. _exif_dict(image)                → EXIF tag dict
   ├─ 2. _compute_ela(image)              → ELA heatmap + mean/std/max diff
   ├─ 3. _compute_noise_uniformity(image) → noise suspicion score (0-100)
   ├─ 4. _metadata_score(exif, image)     → metadata suspicion score (0-100)
   │
   └─ Weighted composite:
        ai_likelihood = 0.40*ela_score + 0.35*noise_score + 0.25*metadata_score
        verdict = likely_ai (≥60) / uncertain (36-59) / likely_human (≤35)
   ▼
scan.ela_score / noise_score / metadata_score / ai_likelihood / verdict /
metadata_json / ela_heatmap  are saved on the ScanResult row
   ▼
redirect → /scan/result/<uuid>/
```

## 3. Viewing a Result (and generating the AI explanation)

```
GET /scan/result/<uuid>/  → detector.views.result()
   │
   ├─ if not scan.explanation_generated:
   │      _generate_explanation(scan)
   │        │
   │        ├─ if OPENCODE_API_KEY missing:
   │        │     → store a clear "explanations disabled" message, return
   │        │
   │        └─ else: build a prompt with the scan's scores (not the raw image)
   │              → common.llm.chat_completion(messages=[...])
   │                    → POST https://opencode.ai/zen/v1/chat/completions
   │                      { model: deepseek-v4-flash-free, messages: [...] }
   │              → store the returned explanation text
   │              → on any network/API error: store a graceful fallback message
   │
   ▼
templates/detector/result.html rendered:
   verdict banner · original image · ELA heatmap · animated score bars ·
   likelihood meter · explanation box · expandable raw metadata table ·
   "Discuss this result" / "Scan another" actions
```

## 4. Chat Assistant

```
User clicks "Discuss this result" → GET /assistant/?scan=<uuid>
   │
   ▼
chatbot.views.chat_page()
   │  looks up the ScanResult (if a valid ?scan= param is present)
   │  creates a fresh ChatSession(scan=scan)
   ▼
templates/chatbot/chat.html rendered — chat shell + system-note about loaded context
   │
   ▼
User types a message → JS (chat.js) POSTs JSON to
   /assistant/send/<session_id>/  with X-CSRFToken header
   │
   ▼
chatbot.views.send_message()
   │  1. Validate + persist the user's ChatMessage
   │  2. Build `messages` list:
   │       [system prompt]
   │       + [scan-context system message, if session.scan is set]
   │       + [last 12 user/assistant turns from history]
   │  3. common.llm.chat_completion(messages=...)
   │  4. Persist the assistant's ChatMessage
   │  5. Return { "reply": "..." } as JSON
   ▼
chat.js appends the reply bubble, scrolls the log, re-enables the input
```

## 5. Failure Modes (by design, nothing crashes the page)

| Failure | What happens |
|---|---|
| No `OPENCODE_API_KEY` set | Explanation box / chat reply shows a clear "add your key to .env" message. Forensic scores are unaffected. |
| OpenCode Zen unreachable / rate-limited | `LLMRequestError` is caught in the view; a friendly fallback message is shown and logged. |
| Invalid/oversized upload | `ImageUploadForm` rejects it before any file touches disk; errors render inline on the upload page. |
| Image with no EXIF at all | Treated as a real (moderately strong) suspicion signal, not an error — most social-media-shared photos lack EXIF too, so it's weighted, not decisive. |

## 6. Where To Look For Each Piece

| What | Where |
|---|---|
| Forensic algorithm | `detector/forensics.py` |
| Scoring weights / verdict thresholds | `detector/forensics.py::analyze_image` |
| LLM prompt for explanations | `detector/views.py::_generate_explanation` |
| LLM prompt for chat | `chatbot/views.py::send_message` |
| Shared LLM client | `common/llm.py` |
| All environment variables | `.env.example`, consumed in `config/settings.py` |
