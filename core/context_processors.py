"""Template context available on every page."""

from django.conf import settings


def platform(request):
    return {"version": settings.VERSION}
