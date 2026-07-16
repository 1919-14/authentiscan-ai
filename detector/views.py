import os

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from common.llm import LLMConfigurationError, LLMRequestError, chat_completion, is_configured

from .forensics import analyze_image
from .forms import ImageUploadForm
from .models import ScanResult


def upload(request):
    """Landing page for the authenticator tool — image upload form."""
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["image"]

            scan = ScanResult.objects.create(
                image=uploaded,
                original_filename=uploaded.name,
            )

            ela_filename = f"{scan.id}.png"
            ela_rel_path = os.path.join("ela", ela_filename)
            ela_abs_path = os.path.join(settings.MEDIA_ROOT, ela_rel_path)
            os.makedirs(os.path.dirname(ela_abs_path), exist_ok=True)

            results = analyze_image(scan.image.path, ela_abs_path)

            scan.ela_score = results["ela_score"]
            scan.noise_score = results["noise_score"]
            scan.metadata_score = results["metadata_score"]
            scan.ai_likelihood = results["ai_likelihood"]
            scan.verdict = results["verdict"]
            scan.metadata_json = results["metadata_json"]
            scan.ela_heatmap.name = ela_rel_path
            scan.save()

            return redirect(reverse("detector:result", args=[scan.id]))
    else:
        form = ImageUploadForm()

    recent_scans = ScanResult.objects.all()[:6]
    return render(request, "detector/upload.html", {"form": form, "recent_scans": recent_scans})


def result(request, scan_id):
    scan = get_object_or_404(ScanResult, id=scan_id)

    if _needs_explanation(scan):
        _generate_explanation(scan)

    return render(request, "detector/result.html", {
        "scan": scan,
        "llm_configured": is_configured(),
    })


def _needs_explanation(scan: ScanResult) -> bool:
    text = (scan.explanation_text or "").strip()
    if not scan.explanation_generated or not text:
        return True
    if text.startswith("Could not generate an AI explanation right now"):
        return True
    if is_configured() and text.startswith("AI-generated explanations are disabled"):
        return True
    return False


def _generate_explanation(scan: ScanResult):
    """Ask the DeepSeek model (via OpenCode Zen) for a plain-English explanation."""
    if not is_configured():
        scan.explanation_text = (
            "AI-generated explanations are disabled because no OPENCODE_API_KEY "
            "is configured. Add your key to the .env file to enable this feature. "
            "The numeric forensic scores above are still fully computed locally."
        )
        scan.explanation_generated = True
        scan.save(update_fields=["explanation_text", "explanation_generated"])
        return

    raw = scan.metadata_json.get("raw_scores", {})
    prompt = (
        "You are a digital forensics assistant embedded in a college project called "
        "AuthentiScan AI. Explain the following automated image-authenticity scan "
        "result to a non-technical user in 4-6 short sentences. Be balanced, avoid "
        "overclaiming certainty, and mention this is a heuristic first-pass triage, "
        "not a legal or forensic-grade determination. Use plain text only, without "
        "Markdown formatting.\n\n"
        f"Verdict: {scan.get_verdict_display()}\n"
        f"Overall AI-generation likelihood: {scan.ai_likelihood}%\n"
        f"Error Level Analysis suspicion score: {scan.ela_score}/100 "
        f"(raw mean pixel diff: {raw.get('ela_mean_diff')})\n"
        f"Noise-uniformity suspicion score: {scan.noise_score}/100\n"
        f"Metadata suspicion score: {scan.metadata_score}/100 — "
        f"{scan.metadata_json.get('metadata_reason', 'n/a')}\n"
        f"Image dimensions: {scan.metadata_json.get('dimensions')}, "
        f"EXIF tags found: {scan.metadata_json.get('exif_tag_count')}\n"
    )

    try:
        explanation = chat_completion(
            messages=[
                {"role": "system", "content": "You explain image-forensics results clearly, concisely, and honestly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=2000,
        )
    except (LLMConfigurationError, LLMRequestError) as exc:
        explanation = (
            "Could not generate an AI explanation right now "
            f"({exc}). The numeric forensic scores above remain valid."
        )

    scan.explanation_text = explanation
    scan.explanation_generated = True
    scan.save(update_fields=["explanation_text", "explanation_generated"])


def history(request):
    scans = ScanResult.objects.all()[:50]
    return render(request, "detector/history.html", {"scans": scans})
