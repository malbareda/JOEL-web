import json
import mimetypes
import os
from itertools import chain
from zipfile import BadZipfile, ZipFile

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.forms import BaseModelFormSet, ChoiceField, HiddenInput, ModelForm, NumberInput, Select, \
    formset_factory
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from judge.highlight_code import highlight_code
from judge.models import Problem, ProblemData, ProblemTestCase, Submission, problem_data_storage
from judge.models.problem_data import CHECKERS
from judge.utils import mysql_grader
from judge.utils.mysql_grader import get_mysql_databases
from judge.utils.pg_grader import get_postgres_databases
from judge.utils.problem_data import ProblemDataCompiler, get_mongo_sample_database_path, \
    get_mongo_sample_databases
from judge.utils.unicode import utf8text
from judge.utils.views import TitleMixin, add_file_response
from judge.views.problem import ProblemMixin

mimetypes.init()
mimetypes.add_type('application/x-yaml', '.yml')


def checker_args_cleaner(self):
    data = self.cleaned_data['checker_args']
    if not data or data.isspace():
        return ''
    try:
        if not isinstance(json.loads(data), dict):
            raise ValidationError(_('Checker arguments must be a JSON object'))
    except ValueError:
        raise ValidationError(_('Checker arguments is invalid JSON'))
    return data


class ProblemDataForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SQL problems are graded on MySQL (MariaDB) now: the SQLite checker, its .db upload and its example
        # databases are no longer offered for new problems.
        self.fields['mongo_template'] = ChoiceField(
            required=False, label=_('Or choose an example database'),
            choices=[('', _('(cap seleccionada -- puja el teu propi fitxer .json)'))] + [
                (key, '%s -- %s' % (label, description) if description else label)
                for key, label, description in get_mongo_sample_databases()
            ],
        )
        try:
            current_database = json.loads(self.instance.checker_args or '{}').get('database', '')
        except (ValueError, AttributeError):
            current_database = ''
        mysql_choices = [(name, '%s -- %s' % (label, description) if description else label)
                         for name, label, description in get_mysql_databases()]
        if current_database and current_database not in dict(mysql_choices):
            mysql_choices.append((current_database, _('%s (not available on the grading server)') % current_database))
        self.fields['mysql_database'] = ChoiceField(
            required=False, label=_('MySQL database'), initial=current_database,
            choices=[('', _('(cap seleccionada)'))] + mysql_choices,
        )
        postgres_choices = [(name, '%s -- %s' % (label, description) if description else label)
                            for name, label, description in get_postgres_databases()]
        if (self.instance.checker == 'postgres' and current_database and
                current_database not in dict(postgres_choices)):
            postgres_choices.append((current_database,
                                     _('%s (not available on the grading server)') % current_database))
        self.fields['postgres_database'] = ChoiceField(
            required=False, label=_('PostgreSQL database'),
            initial=current_database if self.instance.checker == 'postgres' else '',
            choices=[('', _('(cap seleccionada)'))] + postgres_choices,
        )

    def clean_zipfile(self):
        if hasattr(self, 'zip_valid') and not self.zip_valid:
            raise ValidationError(_('Your zip file is invalid!'))
        return self.cleaned_data['zipfile']

    def clean_mysql_dump(self):
        mysql_dump = self.cleaned_data.get('mysql_dump')
        if mysql_dump:
            if not mysql_dump.name.lower().endswith('.sql'):
                raise ValidationError(_('The MySQL dump must be a .sql file.'))
            if mysql_dump.size > mysql_grader.MAX_DUMP_BYTES:
                raise ValidationError(_('The MySQL dump can be at most %d MB.') %
                                      (mysql_grader.MAX_DUMP_BYTES // (1024 * 1024)))
        return mysql_dump

    def clean_mongo_db(self):
        mongo_db = self.cleaned_data.get('mongo_db')
        if mongo_db and not mongo_db.name.endswith('.json'):
            raise ValidationError(_('Mongo database file must be a .json file.'))
        return mongo_db

    def clean(self):
        cleaned_data = super().clean()
        checker = cleaned_data.get('checker')
        mongo_db = cleaned_data.get('mongo_db')
        mongo_template = cleaned_data.get('mongo_template')
        if checker == 'mongo' and not mongo_db and not mongo_template and not self.instance.mongo_db:
            raise ValidationError(_('Mongo checker requires a database file. Please upload a .json '
                                    'file or choose an example database.'))
        # MySQL and PostgreSQL problems are separate blocks: their references are written for one dialect, so an
        # existing problem can't be switched from one engine to the other.
        if self.instance.pk and {self.instance.checker, checker} == {'mysql', 'postgres'}:
            raise ValidationError(_('This problem is graded with %(old)s and cannot be switched to %(new)s: '
                                    'its solutions are written for that dialect. Create a new problem instead.') %
                                  {'old': dict(CHECKERS)[self.instance.checker], 'new': dict(CHECKERS)[checker]})
        if checker == 'postgres' and not cleaned_data.get('postgres_database'):
            raise ValidationError(_('PostgreSQL checker requires a database. Please choose one.'))
        if checker == 'mysql':
            mysql_dump = cleaned_data.get('mysql_dump')
            new_dump = isinstance(mysql_dump, UploadedFile)
            keeps_dump = bool(self.instance.mysql_dump) and mysql_dump is not False
            if not new_dump and not keeps_dump and not cleaned_data.get('mysql_database'):
                raise ValidationError(_('MySQL checker requires a database. Please choose one or upload a dump.'))
            if new_dump:
                # Load it now, so a dump that MariaDB rejects is reported here and nothing is saved.
                mysql_dump.seek(0)
                text = mysql_dump.read().decode('utf-8', errors='replace')
                mysql_dump.seek(0)
                try:
                    mysql_grader.load_problem_dump(self.instance.problem.code, text)
                except mysql_grader.DumpError as e:
                    self.add_error('mysql_dump', _('MariaDB could not load this dump: %s') % e)
                except mysql_grader.GraderUnavailable:
                    self.add_error('mysql_dump', _('The MySQL grading server is not available right now.'))
        return cleaned_data

    clean_checker_args = checker_args_cleaner

    class Meta:
        model = ProblemData
        fields = ['zipfile', 'generator', 'output_limit', 'output_prefix', 'checker', 'caseformat',
                  'allowed_tips', 'allowed_superhints', 'help_chat', 'checker_args', 'mongo_db', 'mysql_dump']
        widgets = {
            'checker_args': HiddenInput,
        }


class ProblemCaseForm(ModelForm):
    clean_checker_args = checker_args_cleaner

    class Meta:
        model = ProblemTestCase
        fields = ('order', 'type', 'input_file', 'output_file', 'points',
                  'is_pretest', 'output_limit', 'output_prefix', 'checker', 'checker_args', 'generator_args')
        widgets = {
            'generator_args': HiddenInput,
            'type': Select(attrs={'style': 'width: 100%'}),
            'points': NumberInput(attrs={'style': 'width: 4em'}),
            'output_prefix': NumberInput(attrs={'style': 'width: 4.5em'}),
            'output_limit': NumberInput(attrs={'style': 'width: 6em'}),
            'checker_args': HiddenInput,
        }


class ProblemCaseFormSet(formset_factory(ProblemCaseForm, formset=BaseModelFormSet, extra=1, max_num=1,
                                         can_delete=True)):
    model = ProblemTestCase

    def __init__(self, *args, **kwargs):
        self.valid_files = kwargs.pop('valid_files', None)
        super(ProblemCaseFormSet, self).__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        form = super(ProblemCaseFormSet, self)._construct_form(i, **kwargs)
        form.valid_files = self.valid_files
        return form


class ProblemManagerMixin(LoginRequiredMixin, ProblemMixin, DetailView):
    def get_object(self, queryset=None):
        problem = super(ProblemManagerMixin, self).get_object(queryset)
        if problem.is_manually_managed:
            raise Http404()
        if self.request.user.is_superuser or problem.is_editable_by(self.request.user):
            return problem
        raise Http404()


class ProblemSubmissionDiff(TitleMixin, ProblemMixin, DetailView):
    template_name = 'problem/submission-diff.html'

    def get_title(self):
        return _('Comparing submissions for {0}').format(self.object.name)

    def get_content_title(self):
        return format_html(_('Comparing submissions for <a href="{1}">{0}</a>'), self.object.name,
                           reverse('problem_detail', args=[self.object.code]))

    def get_object(self, queryset=None):
        problem = super(ProblemSubmissionDiff, self).get_object(queryset)
        if self.request.user.is_superuser or problem.is_editable_by(self.request.user):
            return problem
        raise Http404()

    def get_context_data(self, **kwargs):
        context = super(ProblemSubmissionDiff, self).get_context_data(**kwargs)
        try:
            ids = self.request.GET.getlist('id')
            subs = Submission.objects.filter(id__in=ids)
        except ValueError:
            raise Http404
        if not subs:
            raise Http404

        context['submissions'] = subs

        # If we have associated data we can do better than just guess
        data = ProblemTestCase.objects.filter(dataset=self.object, type='C')
        if data:
            num_cases = data.count()
        else:
            num_cases = subs.first().test_cases.count()
        context['num_cases'] = num_cases
        return context


class ProblemDataView(TitleMixin, ProblemManagerMixin):
    template_name = 'problem/data.html'

    def get_title(self):
        return _('Editing data for {0}').format(self.object.name)

    def get_content_title(self):
        return mark_safe(escape(_('Editing data for %s')) % (
            format_html('<a href="{1}">{0}</a>', self.object.name,
                        reverse('problem_detail', args=[self.object.code]))))

    def get_data_form(self, post=False):
        return ProblemDataForm(data=self.request.POST if post else None, prefix='problem-data',
                               files=self.request.FILES if post else None,
                               instance=ProblemData.objects.get_or_create(problem=self.object)[0])

    def get_case_formset(self, files, post=False):
        return ProblemCaseFormSet(data=self.request.POST if post else None, prefix='cases', valid_files=files,
                                  queryset=ProblemTestCase.objects.filter(dataset_id=self.object.pk).order_by('order'))

    def get_valid_files(self, data, post=False):
        try:
            if post and 'problem-data-zipfile-clear' in self.request.POST:
                return []
            elif post and 'problem-data-zipfile' in self.request.FILES:
                return ZipFile(self.request.FILES['problem-data-zipfile']).namelist()
            elif data.zipfile:
                return ZipFile(data.zipfile.path).namelist()
        except BadZipfile:
            return []
        return []

    def get_context_data(self, **kwargs):
        context = super(ProblemDataView, self).get_context_data(**kwargs)
        if 'data_form' not in context:
            context['data_form'] = self.get_data_form()
            valid_files = context['valid_files'] = self.get_valid_files(context['data_form'].instance)
            context['data_form'].zip_valid = valid_files is not False
            context['cases_formset'] = self.get_case_formset(valid_files)
        context['valid_files_json'] = mark_safe(json.dumps(context['valid_files']))
        context['valid_files'] = set(context['valid_files'])
        context['all_case_forms'] = chain(context['cases_formset'], [context['cases_formset'].empty_form])
        return context

    def post(self, request, *args, **kwargs):
        self.object = problem = self.get_object()
        data_form = self.get_data_form(post=True)
        valid_files = self.get_valid_files(data_form.instance, post=True)
        data_form.zip_valid = valid_files is not False
        cases_formset = self.get_case_formset(valid_files, post=True)
        if data_form.is_valid() and cases_formset.is_valid():
            data = data_form.save()
            if data.checker == 'mysql':
                # A problem's own dump wins over the catalog database; clearing the dump drops its database.
                if data.mysql_dump:
                    database = mysql_grader.problem_database(problem.code)
                else:
                    database = data_form.cleaned_data['mysql_database']
                    if data_form.cleaned_data.get('mysql_dump') is False:
                        try:
                            mysql_grader.drop_problem_databases(problem.code)
                        except mysql_grader.GraderUnavailable:
                            pass
                data.checker_args = json.dumps({'database': database})
                data.save(update_fields=['checker_args'])
            if data.checker == 'postgres':
                data.checker_args = json.dumps({'database': data_form.cleaned_data['postgres_database']})
                data.save(update_fields=['checker_args'])
            mongo_template = data_form.cleaned_data.get('mongo_template')
            if mongo_template and not self.request.FILES.get('problem-data-mongo_db'):
                template_path = get_mongo_sample_database_path(mongo_template)
                if template_path:
                    with open(template_path, 'rb') as f:
                        data.mongo_db.save('%s.json' % mongo_template, ContentFile(f.read()), save=True)
            for case in cases_formset.save(commit=False):
                case.dataset_id = problem.id
                case.save()
            for case in cases_formset.deleted_objects:
                case.delete()
            ProblemDataCompiler.generate(problem, data, problem.cases.order_by('order'), valid_files)
            return HttpResponseRedirect(request.get_full_path())
        return self.render_to_response(self.get_context_data(data_form=data_form, cases_formset=cases_formset,
                                                             valid_files=valid_files))

    put = post


@login_required
def problem_data_file(request, problem, path):
    object = get_object_or_404(Problem, code=problem)
    if not object.is_editable_by(request.user):
        raise Http404()

    problem_dir = problem_data_storage.path(problem)
    if os.path.commonpath((problem_data_storage.path(os.path.join(problem, path)), problem_dir)) != problem_dir:
        raise Http404()

    response = HttpResponse()

    if hasattr(settings, 'DMOJ_PROBLEM_DATA_INTERNAL'):
        url_path = '%s/%s/%s' % (settings.DMOJ_PROBLEM_DATA_INTERNAL, problem, path)
    else:
        url_path = None

    try:
        add_file_response(request, response, url_path, os.path.join(problem, path), problem_data_storage)
    except IOError:
        raise Http404()

    response['Content-Type'] = 'application/octet-stream'
    return response


@login_required
def problem_init_view(request, problem):
    problem = get_object_or_404(Problem, code=problem)
    if not problem.is_editable_by(request.user):
        raise Http404()

    try:
        with problem_data_storage.open(os.path.join(problem.code, 'init.yml'), 'rb') as f:
            data = utf8text(f.read()).rstrip('\n')
    except IOError:
        raise Http404()

    return render(request, 'problem/yaml.html', {
        'raw_source': data, 'highlighted_source': highlight_code(data, 'yaml'),
        'title': _('Generated init.yml for %s') % problem.name,
        'content_title': mark_safe(escape(_('Generated init.yml for %s')) % (
            format_html('<a href="{1}">{0}</a>', problem.name,
                        reverse('problem_detail', args=[problem.code])))),
    })