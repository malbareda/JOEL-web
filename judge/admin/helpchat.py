from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from judge.models import Problem


class HelpChatMessageAdmin(admin.ModelAdmin):
    """The help chat conversations ("No sé ni per on començar"), for the teachers of each problem: read-only, and
    only of the problems the user can edit. Sorted by problem and student, so one conversation reads in order."""
    list_display = ('created', 'student', 'problem_code', 'role', 'status', 'short_text', 'revision')
    list_filter = ('role', 'status')
    list_select_related = ('user__user', 'problem')
    search_fields = ('user__user__username', 'problem__code', 'text')
    ordering = ('problem__code', 'user__user__username', 'id')
    list_per_page = 100

    def student(self, obj):
        return obj.user.user.username

    student.short_description = _('user')
    student.admin_order_field = 'user__user__username'

    def problem_code(self, obj):
        return obj.problem.code

    problem_code.short_description = _('problem')
    problem_code.admin_order_field = 'problem__code'

    def short_text(self, obj):
        text = obj.text or obj.error
        return text if len(text) <= 120 else text[:117] + '...'

    short_text.short_description = _('message')

    def get_queryset(self, request):
        return super(HelpChatMessageAdmin, self).get_queryset(request) \
            .filter(problem__in=Problem.get_editable_problems(request.user))

    def has_module_permission(self, request):
        return request.user.has_perm('judge.edit_own_problem')

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('judge.edit_own_problem')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
