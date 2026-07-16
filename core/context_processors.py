from django.conf import settings


def site_meta(request):
    """Expose project/institute metadata to every template."""
    return {
        "PROJECT_NAME": settings.PROJECT_NAME,
        "PROJECT_TAGLINE": settings.PROJECT_TAGLINE,
        "INSTITUTE_NAME": settings.INSTITUTE_NAME,
        "COURSE_NAME": settings.COURSE_NAME,
    }
