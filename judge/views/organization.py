from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Q
from django.forms import Form, modelformset_factory
from django.http import Http404, HttpResponsePermanentRedirect, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.html import json_script
from django.utils.translation import gettext as _, gettext_lazy, ungettext
from django.views.generic import DetailView, FormView, ListView, UpdateView, View
from django.views.generic.detail import SingleObjectMixin, SingleObjectTemplateResponseMixin
from reversion import revisions

from judge.forms import EditOrganizationForm
from judge.models import GachaPointGrant, Organization, OrganizationRequest, Problem, ProblemTask, \
    ProblemTranslation, Profile
from judge.utils.ranker import ranker
from judge.utils.views import TitleMixin, generic_message

__all__ = ['OrganizationList', 'OrganizationHome', 'OrganizationUsers', 'OrganizationMembershipChange',
           'JoinOrganization', 'LeaveOrganization', 'EditOrganization', 'RequestJoinOrganization',
           'OrganizationRequestDetail', 'OrganizationRequestView', 'OrganizationRequestLog',
           'KickUserWidgetView', 'OrganizationWheel', 'OrganizationWheelTask', 'OrganizationWheelGrant']


def can_use_organization_wheel(user, profile, org):
    """Who may spin the team's wheel and hand out GachaPoints from it: a teacher (the "Profe" permission,
    `see_extended_answers`) who is also an admin of THAT team -- or a superuser, who can use any team's wheel."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.has_perm('judge.see_extended_answers'):
        return False
    return org.registrant_id == profile.id or org.admins.filter(id=profile.id).exists()


class OrganizationMixin(object):
    context_object_name = 'organization'
    model = Organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logo_override_image'] = self.object.logo_override_image
        return context

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(OrganizationMixin, self).dispatch(request, *args, **kwargs)
        except Http404:
            key = kwargs.get(self.slug_url_kwarg, None)
            if key:
                return generic_message(request, _('No such organization'),
                                       _('Could not find an organization with the key "%s".') % key)
            else:
                return generic_message(request, _('No such organization'),
                                       _('Could not find such organization.'))

    def can_edit_organization(self, org=None):
        if org is None:
            org = self.object
        if not self.request.user.is_authenticated:
            return False
        profile_id = self.request.profile.id
        return org.admins.filter(id=profile_id).exists() or org.registrant_id == profile_id

    def can_use_wheel(self, org=None):
        if org is None:
            org = self.object
        if not self.request.user.is_authenticated:
            return False
        return can_use_organization_wheel(self.request.user, self.request.profile, org)


class OrganizationDetailView(OrganizationMixin, DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.slug != kwargs['slug']:
            return HttpResponsePermanentRedirect(reverse('organization_home', args=(self.object.id, self.object.slug)))
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)



class OrganizationList(TitleMixin, ListView):
    model = Organization
    context_object_name = 'organizations'
    template_name = 'organization/list.html'
    title = gettext_lazy('Organizations')

    #XXX calcular els punts dels membres etc etc etc 



    ############

    def get_queryset(self):
        return super(OrganizationList, self).get_queryset().annotate(member_count=Count('member'))


class OrganizationHome(OrganizationDetailView):
    template_name = 'organization/home.html'

    def get_context_data(self, **kwargs):
        context = super(OrganizationHome, self).get_context_data(**kwargs)
        context['title'] = self.object.name
        context['can_edit'] = self.can_edit_organization()
        context['can_wheel'] = self.can_use_wheel()
        return context


class OrganizationUsers(OrganizationDetailView):
    template_name = 'organization/users.html'

    def get_context_data(self, **kwargs):
        context = super(OrganizationUsers, self).get_context_data(**kwargs)
        context['title'] = _('%s Members') % self.object.name
        context['users'] = \
            ranker(self.object.members.filter(is_unlisted=False).order_by('-performance_points', '-problem_count')
                   .select_related('user').defer('about', 'user_script', 'notes'))
        context['partial'] = True
        context['is_admin'] = self.can_edit_organization()
        context['kick_url'] = reverse('organization_user_kick', args=[self.object.id, self.object.slug])
        return context


class OrganizationMembershipChange(LoginRequiredMixin, OrganizationMixin, SingleObjectMixin, View):
    def post(self, request, *args, **kwargs):
        org = self.get_object()
        response = self.handle(request, org, request.profile)
        if response is not None:
            return response
        return HttpResponseRedirect(org.get_absolute_url())

    def handle(self, request, org, profile):
        raise NotImplementedError()


class JoinOrganization(OrganizationMembershipChange):
    def handle(self, request, org, profile):
        if profile.organizations.filter(id=org.id).exists():
            return generic_message(request, _('Joining organization'), _('You are already in the organization.'))

        if not org.is_open:
            return generic_message(request, _('Joining organization'), _('This organization is not open.'))

        max_orgs = settings.DMOJ_USER_MAX_ORGANIZATION_COUNT
        if profile.organizations.filter(is_open=True).count() >= max_orgs:
            return generic_message(
                request, _('Joining organization'),
                _('You may not be part of more than {count} public organizations.').format(count=max_orgs),
            )

        profile.organizations.add(org)
        profile.save()
        cache.delete(make_template_fragment_key('org_member_count', (org.id,)))


class LeaveOrganization(OrganizationMembershipChange):
    def handle(self, request, org, profile):
        if not profile.organizations.filter(id=org.id).exists():
            return generic_message(request, _('Leaving organization'), _('You are not in "%s".') % org.short_name)
        profile.organizations.remove(org)
        cache.delete(make_template_fragment_key('org_member_count', (org.id,)))


class OrganizationRequestForm(Form):
    reason = forms.CharField(widget=forms.Textarea)


class RequestJoinOrganization(LoginRequiredMixin, SingleObjectMixin, FormView):
    model = Organization
    slug_field = 'key'
    slug_url_kwarg = 'key'
    template_name = 'organization/requests/request.html'
    form_class = OrganizationRequestForm

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(RequestJoinOrganization, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(RequestJoinOrganization, self).get_context_data(**kwargs)
        if self.object.is_open:
            raise Http404()
        context['title'] = _('Request to join %s') % self.object.name
        return context

    def form_valid(self, form):
        request = OrganizationRequest()
        request.organization = self.get_object()
        request.user = self.request.profile
        request.reason = form.cleaned_data['reason']
        request.state = 'P'
        request.save()
        return HttpResponseRedirect(reverse('request_organization_detail', args=(
            request.organization.id, request.organization.slug, request.id,
        )))


class OrganizationRequestDetail(LoginRequiredMixin, TitleMixin, DetailView):
    model = OrganizationRequest
    template_name = 'organization/requests/detail.html'
    title = gettext_lazy('Join request detail')
    pk_url_kwarg = 'rpk'

    def get_object(self, queryset=None):
        object = super(OrganizationRequestDetail, self).get_object(queryset)
        profile = self.request.profile
        if object.user_id != profile.id and not object.organization.admins.filter(id=profile.id).exists():
            raise PermissionDenied()
        return object


OrganizationRequestFormSet = modelformset_factory(OrganizationRequest, extra=0, fields=('state',), can_delete=True)


class OrganizationRequestBaseView(LoginRequiredMixin, SingleObjectTemplateResponseMixin, SingleObjectMixin, View):
    model = Organization
    slug_field = 'key'
    slug_url_kwarg = 'key'
    tab = None

    def get_object(self, queryset=None):
        organization = super(OrganizationRequestBaseView, self).get_object(queryset)
        if not (organization.admins.filter(id=self.request.profile.id).exists() or
                organization.registrant_id == self.request.profile.id):
            raise PermissionDenied()
        return organization

    def get_context_data(self, **kwargs):
        context = super(OrganizationRequestBaseView, self).get_context_data(**kwargs)
        context['title'] = _('Managing join requests for %s') % self.object.name
        context['tab'] = self.tab
        return context


class OrganizationRequestView(OrganizationRequestBaseView):
    template_name = 'organization/requests/pending.html'
    tab = 'pending'

    def get_context_data(self, **kwargs):
        context = super(OrganizationRequestView, self).get_context_data(**kwargs)
        context['formset'] = self.formset
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.formset = OrganizationRequestFormSet(
            queryset=OrganizationRequest.objects.filter(state='P', organization=self.object),
        )
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = organization = self.get_object()
        self.formset = formset = OrganizationRequestFormSet(request.POST, request.FILES)
        if formset.is_valid():
            if organization.slots is not None:
                deleted_set = set(formset.deleted_forms)
                to_approve = sum(form.cleaned_data['state'] == 'A' for form in formset.forms if form not in deleted_set)
                can_add = organization.slots - organization.members.count()
                if to_approve > can_add:
                    messages.error(request, _('Your organization can only receive %d more members. '
                                              'You cannot approve %d users.') % (can_add, to_approve))
                    return self.render_to_response(self.get_context_data(object=organization))

            approved, rejected = 0, 0
            for obj in formset.save():
                if obj.state == 'A':
                    obj.user.organizations.add(obj.organization)
                    approved += 1
                elif obj.state == 'R':
                    rejected += 1
            messages.success(request,
                             ungettext('Approved %d user.', 'Approved %d users.', approved) % approved + '\n' +
                             ungettext('Rejected %d user.', 'Rejected %d users.', rejected) % rejected)
            cache.delete(make_template_fragment_key('org_member_count', (organization.id,)))
            return HttpResponseRedirect(request.get_full_path())
        return self.render_to_response(self.get_context_data(object=organization))

    put = post


class OrganizationRequestLog(OrganizationRequestBaseView):
    states = ('A', 'R')
    tab = 'log'
    template_name = 'organization/requests/log.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(OrganizationRequestLog, self).get_context_data(**kwargs)
        context['requests'] = self.object.requests.filter(state__in=self.states)
        return context


class EditOrganization(LoginRequiredMixin, TitleMixin, OrganizationMixin, UpdateView):
    template_name = 'organization/edit.html'
    model = Organization
    form_class = EditOrganizationForm

    def get_title(self):
        return _('Editing %s') % self.object.name

    def get_object(self, queryset=None):
        object = super(EditOrganization, self).get_object()
        if not self.can_edit_organization(object):
            raise PermissionDenied()
        return object

    def get_form(self, form_class=None):
        form = super(EditOrganization, self).get_form(form_class)
        form.fields['admins'].queryset = \
            Profile.objects.filter(Q(organizations=self.object) | Q(admin_of=self.object)).distinct()
        return form

    def form_valid(self, form):
        with transaction.atomic(), revisions.create_revision():
            revisions.set_comment(_('Edited from site'))
            revisions.set_user(self.request.user)
            return super(EditOrganization, self).form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(EditOrganization, self).dispatch(request, *args, **kwargs)
        except PermissionDenied:
            return generic_message(request, _("Can't edit organization"),
                                   _('You are not allowed to edit this organization.'), status=403)


class KickUserWidgetView(LoginRequiredMixin, OrganizationMixin, SingleObjectMixin, View):
    def post(self, request, *args, **kwargs):
        organization = self.get_object()
        if not self.can_edit_organization(organization):
            return generic_message(request, _("Can't edit organization"),
                                   _('You are not allowed to kick people from this organization.'), status=403)

        try:
            user = Profile.objects.get(id=request.POST.get('user', None))
        except Profile.DoesNotExist:
            return generic_message(request, _("Can't kick user"),
                                   _('The user you are trying to kick does not exist!'), status=400)

        if not organization.members.filter(id=user.id).exists():
            return generic_message(request, _("Can't kick user"),
                                   _('The user you are trying to kick is not in organization: %s.') %
                                   organization.name, status=400)

        organization.members.remove(user)
        return HttpResponseRedirect(organization.get_users_url())


class OrganizationWheel(LoginRequiredMixin, OrganizationDetailView):
    """The team's "spin the wheel": picks a problem of a task and a student of the team to solve it on the
    blackboard, and lets the teacher reward the student with GachaPoints afterwards."""
    template_name = 'organization/wheel.html'

    def get(self, request, *args, **kwargs):
        # Not OrganizationDetailView.get: its slug check redirects to the team's home page, not to the wheel.
        self.object = self.get_object()
        if not self.can_use_wheel():
            return generic_message(request, _('No pots fer servir la roda'),
                                   _('Només els professors que administren aquest equip en poden fer servir la roda.'),
                                   status=403)
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_students(self, profile):
        """Who goes on the student wheel: the listed members of the team, minus its teachers (admins and
        registrant) and the person spinning -- nobody can reward themselves."""
        org = self.object
        excluded = set(org.admins.values_list('id', flat=True))
        excluded.update((org.registrant_id, profile.id))
        return list(org.members.filter(is_unlisted=False).exclude(id__in=excluded)
                    .select_related('user').order_by('user__username'))

    def get_context_data(self, **kwargs):
        context = super(OrganizationWheel, self).get_context_data(**kwargs)
        org = self.object
        profile = self.request.profile
        students = self.get_students(profile)
        given = GachaPointGrant.given_today(profile, [student.id for student in students])
        tasks = (ProblemTask.objects.annotate(problem_count=Count('problems')).filter(problem_count__gt=0)
                 .order_by('full_name').values_list('name', 'full_name', 'problem_count'))
        config = {
            'students': [{'id': student.id, 'name': student.user.username, 'given': given.get(student.id, 0)}
                         for student in students],
            'tasks': [{'code': code, 'name': name, 'count': count} for code, name, count in tasks],
            'unlimited': self.request.user.is_superuser,
            'limit': GachaPointGrant.DAILY_LIMIT_PER_STUDENT,
            'maxPerGrant': GachaPointGrant.MAX_PER_GRANT,
            # '__code__' is swapped for the chosen task's code in the browser.
            'taskUrl': reverse('organization_wheel_task', args=[org.id, org.slug, '__code__']),
            'grantUrl': reverse('organization_wheel_grant', args=[org.id, org.slug]),
            'i18n': self.get_js_strings(),
        }
        context['title'] = _('Roda de la pissarra de %s') % org.name
        context['wheel_config'] = json_script(config, 'wheel-config')
        return context

    @staticmethod
    def get_js_strings():
        return {
            'pickTask': _('Tria una tasca!'),
            'noStudents': _('Cap alumne!'),
            'loading': _('Carregant...'),
            'taskError': _("No s'han pogut carregar els problemes d'aquesta tasca."),
            'taskEmpty': _("Aquesta tasca no té cap problema que puguis veure."),
            'taskUnknown': _('No conec aquesta tasca. Tria-la de la llista!'),
            'needStudents': _('Marca almenys un alumne per poder girar la roda!'),
            'everyoneDone': _('Tothom ha sortit a la pissarra! Torna a marcar els alumnes per començar de nou.'),
            'taskLoaded': _('Problemes a la roda: {count}'),
            'spinLines': [
                _("Consultant l'oracle del Python... 🐍"),
                _('Barrejant els noms dins del barret... 🎩'),
                _('Que ningú es faci el mort! 💀'),
                _("Executant l'algorisme... (és O(n!)) 🏃"),
                _("Els astres s'estan alineant... ✨"),
                _('Compilant el destí... 0 errors, 1 víctima 😈'),
                _('Respireu fondo, que això va a ser un segfault! 💥'),
                _('Cercant algú que digui «jo no he estat»... 🕵️'),
            ],
            'winLines': [
                _('Surt a la pissarra amb dignitat (o sense). 🎤'),
                _('Els astres no s\'equivoquen mai. 🔮'),
                _("Ctrl+C no et salvarà d'aquesta. 😈"),
                _('Que sonin les trompetes! 🎺'),
                _("Aplaudiments, que se'ls mereix! 👏"),
                _('No hi ha cap bug, només funcionalitats sorpresa. 🐛'),
                _('Això no era un simulacre! 🚨'),
                _('Val a mirar el veí... però només una mica. 👀'),
            ],
            'solves': _('ha de resoldre'),
            'studentsOn': _('({n} a la roda)'),
            'rewardSkip': _('Ara no'),
            'rewardAsk': _('Vols premiar {student} amb GachaPoints?'),
            'rewardGiven': _('Avui li has donat {given} de {limit} GachaPoints.'),
            'rewardUnlimited': _('Sense límit diari (superadmin).'),
            'rewardNone': _('Avui ja no li pots donar més GachaPoints.'),
            'rewardDone': _('{n} GachaPoints per a {student}! 🎁'),
            'rewardGive': _('+{n}'),
            'rewardError': _('No s\'han pogut donar els GachaPoints.'),
            # nivells del slider «over-the-top», del 0 al 10 (el 10 és el superllegendari)
            'otNames': [_('Mode biblioteca 🤫'), _('Sobri'), _('Discret'), _('Festiu'), _('Animat'), _('Festa major'),
                        _('Exagerat'), _('Boig'), _('Caos'), _('Apocalipsi'), _('SUPERLLEGENDARI')],
            'otLegend': _('És una llegenda!'),
            # frases còmiques de l'epíleg de la tirada (nivells 6+): la roda s'arrossega, fa una falsa parada, té molla o rebobina
            'finaleCreep': [_('Va... va... una mica més... 😬'), _('Que no es pari just a la vora! 🫣')],
            'finaleFake': [_("Ja s'ha aturat?... NO! 😱"), _('Tothom es va relaxar massa aviat! 🤨')],
            'finaleWobble': [_('Boioioioing! 🪀'), _('Aquesta roda té massa molla! 🌀')],
            'finaleRewind': [_('Marxa enrere! ⏪'), _('Ui, que ens hem passat! ↩️')],
            'muted': _('Activar el so'),
            'unmuted': _('Silenciar'),
        }


class OrganizationWheelTask(View):
    """JSON: the problems of a task that the teacher can see, i.e. what goes on the problem wheel."""

    def get(self, request, *args, **kwargs):
        org = Organization.objects.filter(pk=kwargs['pk']).first()
        if org is None:
            return JsonResponse({'error': _('Could not find such organization.')}, status=404)
        if not can_use_organization_wheel(request.user, getattr(request, 'profile', None), org):
            return JsonResponse({'error': _('No tens permís per fer servir aquesta roda.')}, status=403)
        task = ProblemTask.objects.filter(name=kwargs['task']).first()
        if task is None:
            return JsonResponse({'error': _('Aquesta tasca no existeix.')}, status=404)
        problems = list(Problem.get_visible_problems(request.user).filter(tasks_of_problem=task)
                        .distinct().order_by('code').only('id', 'code', 'name'))
        names = dict(ProblemTranslation.objects.filter(problem__in=[problem.id for problem in problems],
                                                       language=request.LANGUAGE_CODE)
                     .values_list('problem_id', 'name'))
        return JsonResponse({'problems': [{
            'code': problem.code,
            'name': names.get(problem.id, problem.name),
            'url': problem.get_absolute_url(),
        } for problem in problems]})


class OrganizationWheelGrant(View):
    """JSON POST: the teacher hands `amount` GachaPoints to `student`, a member of this team.

    GachaPoints are given by SUBTRACTING from `Profile.gacha_points` (what the user has spent). A teacher can
    give at most GachaPointGrant.DAILY_LIMIT_PER_STUDENT points per student per day; superusers have no limit."""

    @staticmethod
    def fail(message, status, **extra):
        return JsonResponse(dict(extra, error=message), status=status)

    def post(self, request, *args, **kwargs):
        org = Organization.objects.filter(pk=kwargs['pk']).first()
        if org is None:
            return self.fail(_('Could not find such organization.'), 404)
        giver = getattr(request, 'profile', None)
        if not can_use_organization_wheel(request.user, giver, org):
            return self.fail(_('No tens permís per fer servir aquesta roda.'), 403)

        try:
            student_id = int(request.POST.get('student', ''))
            amount = int(request.POST.get('amount', ''))
        except ValueError:
            return self.fail(_('Alumne o quantitat no vàlids.'), 400)
        if not 1 <= amount <= GachaPointGrant.MAX_PER_GRANT:
            return self.fail(_('La quantitat ha de ser entre 1 i %d.') % GachaPointGrant.MAX_PER_GRANT, 400)
        if student_id == giver.id:
            return self.fail(_('No et pots donar GachaPoints a tu mateix.'), 400)
        if not org.members.filter(id=student_id).exists():
            return self.fail(_("Aquest alumne no és d'aquest equip."), 404)

        unlimited = request.user.is_superuser
        limit = GachaPointGrant.DAILY_LIMIT_PER_STUDENT
        with transaction.atomic():
            # Lock the student's row first, so two simultaneous requests for the same student can't both read
            # "3 given today" and slip past the daily limit: the second one waits here and then sees the first.
            student = Profile.objects.select_for_update().get(pk=student_id)
            given = GachaPointGrant.given_today(giver, [student.id]).get(student.id, 0)
            if not unlimited and given + amount > limit:
                left = max(0, limit - given)
                return self.fail(_("Avui ja has donat %(given)d GachaPoints a aquest alumne (el màxim són %(limit)d "
                                   "al dia): te'n queden %(left)d.") % {'given': given, 'limit': limit, 'left': left},
                                 409, given=given, left=left)
            GachaPointGrant.objects.create(giver=giver, receiver=student, organization=org, points=amount,
                                           day=Profile.madrid_today())
            # F(): subtract in the database, not from the value we read, so we never overwrite a concurrent change
            # (e.g. a daily bonus or a gacha roll finishing at the same moment).
            Profile.objects.filter(pk=student.pk).update(gacha_points=F('gacha_points') - amount)
        given += amount
        return JsonResponse({'ok': True, 'given': given, 'left': None if unlimited else max(0, limit - given)})
