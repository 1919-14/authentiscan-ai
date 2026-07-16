from django import forms
from django.conf import settings

ACCEPTED_TYPES = ("image/jpeg", "image/png", "image/webp")


class ImageUploadForm(forms.Form):
    image = forms.ImageField(
        label="Image to authenticate",
        widget=forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
    )

    def clean_image(self):
        image = self.cleaned_data["image"]

        if image.size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise forms.ValidationError(f"Image is too large. Maximum size is {max_mb} MB.")

        content_type = getattr(image, "content_type", "")
        if content_type and content_type not in ACCEPTED_TYPES:
            raise forms.ValidationError("Unsupported file type. Please upload a JPEG, PNG, or WEBP image.")

        return image
