"""Flat pages (static pages/guides) that only people holding a given permission may see.

django.contrib.flatpages can only require "logged in" (`registration_required`), so the rest lives
here, as a single source of truth used by both places that have to agree:

* `judge.flatpage_i18n` (the patched `render_flatpage`) refuses the page itself, and
* `judge.template_context.general_info` leaves the matching entries out of the navigation bar, so
  a guide nobody can open is not even listed in the "Altres Guies" menu.

To restrict another flat page, add `'/its-url/': 'app_label.codename'` here and give its menu entry
(`NavigationBar.path`) the same URL. No migration needed.
"""

PERMISSION_REQUIRED_FLATPAGES = {
    # "Guia de crear achievements": only for the achievement creators (group "Creador d'Achievements").
    # Superusers pass every `has_perm`, so the admins see it too.
    '/creaachievements/': 'judge.add_achievement',
}


def can_see_flatpage(user, url):
    perm = PERMISSION_REQUIRED_FLATPAGES.get(url)
    return perm is None or user.has_perm(perm)


def hidden_flatpage_paths(user):
    """URLs of the restricted flat pages this user may not see (also the paths of their menu entries)."""
    return [url for url, perm in PERMISSION_REQUIRED_FLATPAGES.items() if not user.has_perm(perm)]
