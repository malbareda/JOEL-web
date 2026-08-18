from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class InstitutionAdmin(admin.ModelAdmin):
    fields = ('name', 'slug', 'short_name', 'image', 'creation_date')
    readonly_fields = ('creation_date',)
    list_display = ('name', 'short_name', 'organization_count', 'creation_date')
    search_fields = ('name', 'short_name')
    prepopulated_fields = {'slug': ('name',)}

    def organization_count(self, obj):
        return obj.organizations.count()
    organization_count.short_description = _('teams')
