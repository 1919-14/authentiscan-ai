import uuid

from django.db import models


def scan_upload_path(instance, filename):
    ext = filename.split(".")[-1].lower()
    return f"uploads/{instance.id}.{ext}"


class ScanResult(models.Model):
    """A single image authenticity scan and its forensic findings."""

    VERDICT_CHOICES = [
        ("likely_human", "Likely Authentic (Human-Captured)"),
        ("uncertain", "Inconclusive"),
        ("likely_ai", "Likely AI-Generated / Manipulated"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(upload_to=scan_upload_path)
    ela_heatmap = models.ImageField(upload_to="ela/", blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)

    # Forensic signal scores (0-100 scale, higher = more suspicious)
    ela_score = models.FloatField(default=0.0)
    noise_score = models.FloatField(default=0.0)
    metadata_score = models.FloatField(default=0.0)
    ai_likelihood = models.FloatField(default=0.0)
    verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES, default="uncertain")

    metadata_json = models.JSONField(default=dict, blank=True)
    explanation_text = models.TextField(blank=True)
    explanation_generated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Scan {self.id} — {self.get_verdict_display()} ({self.ai_likelihood:.1f}%)"

    @property
    def confidence_label(self):
        if self.ai_likelihood >= 75 or self.ai_likelihood <= 25:
            return "High"
        if 40 <= self.ai_likelihood <= 60:
            return "Low"
        return "Moderate"
