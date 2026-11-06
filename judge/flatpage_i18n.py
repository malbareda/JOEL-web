"""Adds translation support to django.contrib.flatpages (used for the "About" static pages),
mirroring how ProblemDetail resolves a ProblemTranslation for the current request's language.

FlatPage is a third-party model with no hook of its own to override, and this project serves flat
pages exclusively through FlatpageFallbackMiddleware -> django.contrib.flatpages.views.flatpage()
-> render_flatpage(). Monkeypatching render_flatpage() here (called from JudgeAppConfig.ready())
means every one of those code paths picks up FlatPageTranslation automatically, without having to
swap the middleware or reimplement the URL/redirect/site-lookup logic in flatpage() itself.
"""
from django.contrib.auth.views import redirect_to_login
from django.contrib.flatpages import views as flatpages_views
from django.http import Http404

from judge.flatpage_permissions import can_see_flatpage

_original_render_flatpage = flatpages_views.render_flatpage


def _translated_render_flatpage(request, f):
    from judge.models import FlatPageTranslation

    # Pages restricted to a permission (judge/flatpage_permissions.py). Not logged in: send them to
    # log in, as `registration_required` does. Logged in without the permission: a plain 404, so the
    # page doesn't even show up as existing (FlatpageFallbackMiddleware turns the Http404 into the
    # site's normal 404 page).
    if not can_see_flatpage(request.user, f.url):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        raise Http404('No such page.')

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
