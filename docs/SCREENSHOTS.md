# Capturing Real Screenshots

The images in `docs/screenshots/` are **placeholder mockups** — they match the app's
real color palette, type, and layout so the README reads well immediately, but they
are not pixel-accurate captures of the running app. Replace them before final
submission (takes about 5 minutes):

## Steps

1. Start the app locally:
   ```bash
   python manage.py runserver
   ```
2. Open **http://127.0.0.1:8000/** in a normal browser window
   (a laptop-width window, ~1280–1440px wide, looks best).
3. Capture each of the following pages, saving over the matching placeholder file:

   | Page | URL | Save as |
   |---|---|---|
   | Landing page (hero + how it works) | `/` | `docs/screenshots/01-landing-page.png` |
   | Upload / authenticator | `/scan/` | `docs/screenshots/02-upload-page.png` |
   | Scan result (upload any test image first) | `/scan/result/<id>/` | `docs/screenshots/03-result-page.png` |
   | AI chat assistant | `/assistant/` | `docs/screenshots/04-chat-page.png` |
   | Contributors page | `/contributors/` | `docs/screenshots/05-contributors-page.png` |

4. On macOS: `Cmd+Shift+4` then drag to select the browser window/region.
   On Windows: `Win+Shift+S` (Snip & Sketch).
   On Linux: `gnome-screenshot -a` or your desktop's screenshot tool.

5. For the **result page** screenshot, upload a real photo (for a "Likely Authentic"
   result) and, separately, an AI-generated image from any generator (for a "Likely
   AI-Generated" result) if you'd like two contrasting examples — feel free to add
   `03b-result-ai-flagged.png` and reference it in the README.

That's it — no special tooling required, since the whole point of this doc is that a
plain OS screenshot tool is enough.
