from django.contrib import admin
from django.forms import ModelForm, ModelMultipleChoiceField
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from django.urls import reverse_lazy

from judge.models import Achievement, Profile
from judge.widgets import AdminHeavySelect2MultipleWidget, AdminHeavySelect2Widget, AdminMartorWidget


class AchievementForm(ModelForm):
    class Meta:
        widgets = {
            'desc': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('organization_preview')}),
        }


class AchievementAdmin(admin.ModelAdmin):
    # 'category' and 'quality' both have `choices` on the model, so the admin changelist already
    # renders their human-readable labels (sticker/icon/... and common/rare/epic/legendary)
    # automatically instead of the raw stored integers.
    list_display = ('name', 'category', 'image_preview', 'quality', 'created_by')
    fields = ('name', 'desc', 'rarity', 'quality', 'category', 'logo_override_image', 'mega_fanfare')
    form = AchievementForm

    def image_preview(self, obj):
        # Django's default list_display rendering for an ImageField links through `.url`, which
        # mangles the ~258 pre-existing achievements whose raw value is still an external URL
        # (see Achievement.get_image_url) -- use that instead so the link actually works for both
        # old and newly-uploaded images.
        url = obj.get_image_url()
        return format_html('<a href="{0}">{0}</a>', url) if url else ''
    image_preview.short_description = _('achievement image')

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if not request.user.is_superuser:
            # Only real admins decide whether an achievement gets the "mega fanfare" treatment
            # (extra confetti/ducks/rainbow + an email to the admins every time someone gets it),
            # and only real admins can raise an achievement's rarity above the normal odds for its
            # quality tier -- a student with limited access to create stickers/icons never sees
            # either field, so their achievements always keep the default rarity of 1.
            fields = [f for f in fields if f not in ('mega_fanfare', 'rarity')]
        return fields

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'category' and not request.user.is_superuser:
            # Students with limited access can only create stickers/icons -- colors, themes,
            # fonts, and the internal GachaPoints-bonus category stay admin-only.
            kwargs['choices'] = [
                choice for choice in Achievement.CATEGORY_CHOICES
                if choice[0] in Achievement.STUDENT_CATEGORIES
            ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.profile
        super().save_model(request, obj, form, change)

    def _owns(self, request, obj):
        return request.user.is_superuser or (obj.created_by_id == request.profile.id)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        # A student with limited access can edit only the achievements they created themselves;
        # real admins can edit any of them. obj is None for the "can access the changelist at
        # all" check, which every account with the base model permission still passes.
        if obj is not None:
            return self._owns(request, obj)
        return True

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if obj is not None:
            return self._owns(request, obj)
        return True
