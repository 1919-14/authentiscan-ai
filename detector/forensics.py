"""
Forensic "Proof-of-Human" image analysis engine.

This module implements the lightweight, no-training-required approach
described in the project brief:

1. Error Level Analysis (ELA) — resave the image at a known JPEG quality
   and measure how much each region "moves". Regions that were edited or
   synthetically generated tend to compress differently than the rest of
   a genuine, single-generation photograph, producing brighter/uneven
   patches in the ELA difference map.

2. Noise-consistency analysis — genuine camera photos carry a fairly
   uniform sensor-noise signature across the frame. AI-generated images
   are frequently "too clean" or show unnaturally uniform local variance.

3. Metadata heuristics — real camera photos usually carry EXIF data
   (Make, Model, ExposureTime, FNumber, GPS, etc). Images produced or
   processed by generative tools/editors often have missing EXIF, or a
   Software/Processing tag naming a known AI/editing tool.

None of this is a trained deep model — it is a transparent, explainable
heuristic pipeline, combined at the end into a single 0-100
"AI-generation likelihood" score. This mirrors real, lightweight
forensic techniques used as a first-pass triage layer, not a legal
verdict.
"""

import io
import os

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ExifTags

AI_SOFTWARE_HINTS = [
    "midjourney", "dall-e", "dalle", "stable diffusion", "stability",
    "adobe firefly", "firefly", "runway", "leonardo", "nightcafe",
    "playground ai", "ideogram", "flux", "comfyui", "automatic1111",
    "diffusers", "generative", "synthetic",
]

CAMERA_EXIF_TAGS = {"Make", "Model", "FNumber", "ExposureTime", "ISOSpeedRatings", "FocalLength"}


def _exif_dict(pil_image):
    """Return a friendly {tag_name: value} dict from an image's EXIF, if any."""
    raw = {}
    try:
        exif = pil_image.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    try:
                        value = value.decode(errors="ignore")
                    except Exception:
                        value = str(value)
                raw[tag] = value
    except Exception:
        pass
    return raw


def _compute_ela(pil_image, quality=90, scale=18):
    """
    Resave the image at a fixed JPEG quality and diff against the original.
    Returns (ela_image, mean_diff, std_diff, max_diff) where mean/std/max
    are 0-255 scale intensity statistics of the amplified difference map.
    """
    rgb = pil_image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    diff = ImageChops.difference(rgb, resaved)
    arr = np.asarray(diff).astype(np.float32)

    mean_diff = float(arr.mean())
    std_diff = float(arr.std())
    max_diff = float(arr.max())

    # Amplify for a viewable heatmap
    amplify = 255.0 / max(max_diff, 1.0) * (scale / 10.0)
    amplify = min(max(amplify, 1.0), 40.0)
    ela_display = ImageEnhance.Brightness(diff).enhance(amplify)

    return ela_display, mean_diff, std_diff, max_diff


def _compute_noise_uniformity(pil_image, tile=32):
    """
    Split the image into tiles, compute local variance (a crude noise proxy)
    per tile, then measure the *variance of those variances*. Real camera
    noise tends to vary moderately and organically across a frame; overly
    uniform local variance is a soft signal of synthetic or heavily
    smoothed/denoised content.

    Returns a 0-100 suspicion score (higher = more suspicious/uniform).
    """
    gray = np.asarray(pil_image.convert("L")).astype(np.float32)
    h, w = gray.shape
    if h < tile * 2 or w < tile * 2:
        return 40.0  # image too small to judge reliably — neutral-ish score

    local_vars = []
    for y in range(0, h - tile, tile):
        for x in range(0, w - tile, tile):
            patch = gray[y:y + tile, x:x + tile]
            local_vars.append(patch.var())

    local_vars = np.array(local_vars)
    if local_vars.mean() < 1e-6:
        return 85.0  # essentially flat/noiseless image — quite suspicious

    coeff_of_variation = local_vars.std() / (local_vars.mean() + 1e-6)

    # Empirically, genuine photos have a healthy spread of local variance
    # (CoV roughly 0.6-1.6). Very low CoV (too uniform) or extremely high
    # CoV (patchwork/inpainted) both push the suspicion score up.
    if 0.6 <= coeff_of_variation <= 1.6:
        score = 20.0
    elif coeff_of_variation < 0.6:
        score = 90.0 - (coeff_of_variation / 0.6) * 40.0
    else:
        score = min(90.0, 30.0 + (coeff_of_variation - 1.6) * 25.0)

    return float(max(0.0, min(100.0, score)))


def _metadata_score(exif, pil_image):
    """
    Score 0-100 (higher = more suspicious) based on EXIF presence/content.
    """
    if not exif:
        return 75.0, {"reason": "No EXIF metadata found (common in AI-generated or re-exported images)."}

    software = str(exif.get("Software", "")).lower()
    for hint in AI_SOFTWARE_HINTS:
        if hint in software:
            return 95.0, {"reason": f"Software tag references a known generative/AI tool: '{exif.get('Software')}'."}

    camera_tags_present = CAMERA_EXIF_TAGS.intersection(exif.keys())
    if len(camera_tags_present) >= 2:
        return 10.0, {"reason": f"Camera EXIF fields present ({', '.join(sorted(camera_tags_present))}), consistent with a real capture device."}

    return 55.0, {"reason": "Partial or generic EXIF present, but no strong camera-capture fields found."}


def analyze_image(pil_image_path, ela_output_path):
    """
    Run the full forensic pipeline on an image file path.

    Writes an ELA heatmap PNG to `ela_output_path` and returns a dict of
    scores + metadata suitable for storing on a ScanResult and for
    feeding into the LLM explanation prompt.
    """
    pil_image = Image.open(pil_image_path)
    exif = _exif_dict(pil_image)

    ela_image, mean_diff, std_diff, max_diff = _compute_ela(pil_image)
    ela_image.save(ela_output_path, "PNG")

    # Normalise ELA mean/std into a 0-100 suspicion score.
    # These thresholds are empirical/heuristic, tuned for typical photo JPEGs.
    ela_score = min(100.0, (mean_diff / 25.0) * 100.0)
    noise_score = _compute_noise_uniformity(pil_image)
    metadata_score, metadata_reason = _metadata_score(exif, pil_image)

    # Weighted composite. Metadata is a strong but sometimes-absent signal
    # (many legitimately shared photos are stripped of EXIF by social apps),
    # so it carries less weight than the two pixel-level forensic signals.
    ai_likelihood = (
        0.40 * ela_score
        + 0.35 * noise_score
        + 0.25 * metadata_score
    )
    ai_likelihood = float(max(0.0, min(100.0, ai_likelihood)))

    if ai_likelihood >= 60:
        verdict = "likely_ai"
    elif ai_likelihood <= 35:
        verdict = "likely_human"
    else:
        verdict = "uncertain"

    width, height = pil_image.size

    metadata_json = {
        "dimensions": f"{width}x{height}",
        "format": pil_image.format,
        "exif_tag_count": len(exif),
        "exif_sample": {k: str(v)[:120] for k, v in list(exif.items())[:12]},
        "metadata_reason": metadata_reason.get("reason", ""),
        "raw_scores": {
            "ela_mean_diff": round(mean_diff, 3),
            "ela_std_diff": round(std_diff, 3),
            "ela_max_diff": round(max_diff, 3),
        },
    }

    return {
        "ela_score": round(ela_score, 2),
        "noise_score": round(noise_score, 2),
        "metadata_score": round(metadata_score, 2),
        "ai_likelihood": round(ai_likelihood, 2),
        "verdict": verdict,
        "metadata_json": metadata_json,
    }
