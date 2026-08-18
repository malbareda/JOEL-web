from django.db.models import Count
from django.http import Http404, HttpResponsePermanentRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import DetailView, ListView

from judge.models import Institution
from judge.utils.views import TitleMixin, generic_message

__all__ = ['InstitutionList', 'InstitutionHome']


class InstitutionMixin(object):
    context_object_name = 'institution'
    model = Institution

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(InstitutionMixin, self).dispatch(request, *args, **kwargs)
        except Http404:
            key = kwargs.get(self.slug_url_kwarg, None)
            if key:
                return generic_message(request, gettext_lazy('No such institution'),
                                       gettext_lazy('Could not find an institution with the key "%s".') % key)
            else:
                return generic_message(request, gettext_lazy('No such institution'),
                                       gettext_lazy('Could not find such institution.'))


class InstitutionList(TitleMixin, ListView):
    model = Institution
    context_object_name = 'institutions'
    template_name = 'institution/list.html'
    title = gettext_lazy('Institutions')

    def get_queryset(self):
        return (super(InstitutionList, self).get_queryset()
                .annotate(member_count=Count('organizations__member', distinct=True))
                .prefetch_related('organizations'))


class InstitutionHome(InstitutionMixin, DetailView):
    template_name = 'institution/home.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.slug != kwargs['slug']:
            return HttpResponsePermanentRedirect(reverse('institution_home', args=(self.object.id, self.object.slug)))
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(InstitutionHome, self).get_context_data(**kwargs)
        context['title'] = self.object.name
        context['organizations'] = self.object.organizations.annotate(member_count=Count('member'))
        return context
