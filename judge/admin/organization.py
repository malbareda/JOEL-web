from django.contrib import admin
from django.db.models import Q
from django.forms import ModelForm
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _
from reversion.admin import VersionAdmin

from judge.models import Organization
from judge.widgets import AdminHeavySelect2MultipleWidget, AdminHeavySelect2Widget, AdminMartorWidget


class OrganizationForm(ModelForm):
    class Meta:
        widgets = {
            'admins': AdminHeavySelect2MultipleWidget(data_view='profile_select2'),
            'registrant': AdminHeavySelect2Widget(data_view='profile_select2'),
            'about': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('organization_preview')}),
        }


class OrganizationAdmin(VersionAdmin):
    readonly_fields = ('creation_date',)
    fields = ('name', 'slug', 'short_name', 'institution', 'is_open', 'about', 'logo_override_image', 'slots',
              'registrant', 'creation_date', 'admins')
    list_display = ('name', 'short_name', 'institution', 'is_open', 'slots', 'registrant', 'show_public')
    list_filter = ('institution',)
    prepopulated_fields = {'slug': ('name',)}
    actions_on_top = True
    actions_on_bottom = True
    form = OrganizationForm

    def show_public(self, obj):
        return format_html('<a href="{0}" style="white-space:nowrap;">{1}</a>',
                           obj.get_absolute_url(), gettext('View on site'))

    show_public.short_description = ''

    def get_readonly_fields(self, request, obj=None):
        fields = self.readonly_fields
        if not request.user.has_perm('judge.organization_admin'):
            return fields + ('registrant', 'admins', 'is_open', 'slots', 'institution')
        return fields

    def get_queryset(self, request):
        queryset = Organization.objects.all()
        if request.user.has_perm('judge.edit_all_organization'):
            return queryset
        # An "institute lead" -- someone who is a member of at least one team under a given
        # institute -- can administer every team under that same institute, not just teams they
        # were separately made an admin of.
        institution_ids = request.profile.administered_institution_ids
        return queryset.filter(Q(admins=request.profile.id) | Q(institution_id__in=institution_ids)).distinct()

    def has_change_permission(self, request, obj=None):
        if not request.user.has_perm('judge.change_organization'):
            return False
        if request.user.has_perm('judge.edit_all_organization') or obj is None:
            return True
        if obj.admins.filter(id=request.profile.id).exists():
            return True
        return obj.institution_id is not None and obj.institution_id in request.profile.administered_institution_ids


class OrganizationRequestAdmin(admin.ModelAdmin):
    list_display = ('username', 'organization', 'state', 'time')
    readonly_fields = ('user', 'organization')

    def username(self, obj):
        return obj.user.user.username
    username.short_description = _('username')
    username.admin_order_field = 'user__user__username'
