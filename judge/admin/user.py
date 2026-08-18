from django.contrib.auth.admin import UserAdmin


class RestrictedUserAdmin(UserAdmin):
    """Django's stock User admin, scoped down for non-superusers the same way ProfileAdmin is: an
    "institute lead" (Profile.administered_institution_ids) can only see/edit user accounts
    belonging to a student in a team under their own institute, never the whole site's user base.
    """

    def _profile_administered(self, request, obj):
        profile = getattr(obj, 'profile', None)
        if profile is None:
            return False
        return profile.organizations.filter(
            institution_id__in=request.profile.administered_institution_ids).exists()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        institution_ids = request.profile.administered_institution_ids
        if not institution_ids:
            return qs.none()
        return qs.filter(profile__organizations__institution_id__in=institution_ids).distinct()

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is not None and not request.user.is_superuser:
            return self._profile_administered(request, obj)
        return True

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if obj is not None and not request.user.is_superuser:
            return self._profile_administered(request, obj)
        return True
