"""Adds translation support to django.contrib.flatpages (used for the "About" static pages),
mirroring how ProblemDetail resolves a ProblemTranslation for the current request's language.

FlatPage is a third-party model with no hook of its own to override, and this project serves flat
pages exclusively through FlatpageFallbackMiddleware -> django.contrib.flatpages.views.flatpage()
-> render_flatpage(). Monkeypatching render_flatpage() here (called from JudgeAppConfig.ready())
means every one of those code paths picks up FlatPageTranslation automatically, without having to
swap the middleware or reimplement the URL/redirect/site-lookup logic in flatpage() itself.
"""
from django.contrib.flatpages import views as flatpages_views

_original_render_flatpage = flatpages_views.render_flatpage


def _translated_render_flatpage(request, f):
    from judge.models import FlatPageTranslation

    try:
        translation = f.translations.get(language=request.LANGUAGE_CODE)
    except FlatPageTranslation.DoesNotExist:
        pass
    else:
        f.title = translation.title
        f.content = translation.content or f.content
    return _original_render_flatpage(request, f)


def patch():
    flatpages_views.render_flatpage = _translated_render_flatpage
