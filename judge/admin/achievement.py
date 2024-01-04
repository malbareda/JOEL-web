from django.contrib import admin
from django.forms import ModelForm, ModelMultipleChoiceField
from django.utils.translation import gettext_lazy as _

from django.urls import reverse_lazy

from judge.models import Profile
from judge.widgets import AdminHeavySelect2MultipleWidget, AdminHeavySelect2Widget, AdminMartorWidget


class AchievementForm(ModelForm):
    class Meta:
        widgets = {
            'desc': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('organization_preview')}),
        }


class AchievementAdmin(admin.ModelAdmin):
    fields = ('name', 'desc', 'rarity', 'quality', 'category', 'logo_override_image',)
    form = AchievementForm
