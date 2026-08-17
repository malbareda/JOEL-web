import json
import os
import re

import yaml
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.translation import gettext as _

if os.altsep:
    def split_path_first(path, repath=re.compile('[%s]' % re.escape(os.sep + os.altsep))):
        return repath.split(path, 1)
else:
    def split_path_first(path):
        return path.split(os.sep, 1)


# Checkers that turn a problem into a "database problem" (categorization, separate ranking,
# multi-question submission form, schema explorer) -- currently SQL/SQLite and Mongo/mongomock.
DATABASE_CHECKERS = ('sql', 'mongo')


class ProblemDataStorage(FileSystemStorage):
    def __init__(self):
        super(ProblemDataStorage, self).__init__(settings.DMOJ_PROBLEM_DATA_ROOT)

    def url(self, name):
        path = split_path_first(name)
        if len(path) != 2:
            raise ValueError('This file is not accessible via a URL.')
        return reverse('problem_data_file', args=path)

    def _save(self, name, content):
        if self.exists(name):
            self.delete(name)
        return super(ProblemDataStorage, self)._save(name, content)

    def get_available_name(self, name, max_length=None):
        return name

    def rename(self, old, new):
        return os.rename(self.path(old), self.path(new))


# Friendly name/description shown in the "choose an example database" dropdown, keyed by filename
# (without the .db extension). A .db file present in settings.DMOJ_SQL_SAMPLE_DATABASES_ROOT but
# missing from this dict still shows up (using its filename as the label), it just won't have a
# nice description -- so dropping in a new file there works immediately, this dict just improves it.
SQL_SAMPLE_DATABASE_INFO = {
    'northwind': (_('Northwind'), _('Base de dades clàssica de vendes: clients, comandes, productes, proveïdors...')),
    'miniwind': (_('Miniwind'), _('Versió reduïda de Northwind: clients, empleats, comandes, factures...')),
    'chinook': (_('Chinook'), _('Botiga de música digital: artistes, àlbums, cançons, clients, factures...')),
    'traders': (_('Traders'), _('Joc de comerç espacial: naus, planetes, mercaders, viatges...')),
    'knights': (_('Knights & Dragons'), _('Cavallers i dracs (en català), pensada per a exercicis senzills.')),
    'hotel': (_('Hotel'), _('Sistema de reserves d\'un hotel: clients, habitacions, reserves, temporades...')),
    'lastnames': (_('Cognoms de Catalunya'), _('Freqüència de cognoms a Catalunya (dades obertes de l\'Idescat).')),
    'employees': (_('Employees'), _('Una sola taula d\'empleats, pensada per a exercicis molt bàsics.')),
    'groupbytest': (_('GroupByTest'), _('Tres variants d\'una taula d\'empleats, pensada per practicar GROUP BY.')),
}


def get_sql_sample_databases():
    """Returns [(key, label, description), ...] for every .db file found in
    settings.DMOJ_SQL_SAMPLE_DATABASES_ROOT, sorted by label."""
    root = settings.DMOJ_SQL_SAMPLE_DATABASES_ROOT
    try:
        filenames = [f for f in os.listdir(root) if f.endswith('.db')]
    except OSError:
        return []
    results = []
    for filename in filenames:
        key = filename[:-len('.db')]
        label, description = SQL_SAMPLE_DATABASE_INFO.get(key, (key, ''))
        results.append((key, label, description))
    results.sort(key=lambda item: item[1])
    return results


def get_sql_sample_database_path(key):
    """Returns the absolute path to a sample database given its key, or None if it doesn't exist
    (e.g. an invalid/tampered key) -- always validated against the real directory listing, never
    trusts the key to already be a safe path component."""
    for existing_key, _label, _description in get_sql_sample_databases():
        if existing_key == key:
            return os.path.join(settings.DMOJ_SQL_SAMPLE_DATABASES_ROOT, key + '.db')
    return None


# Same idea as SQL_SAMPLE_DATABASE_INFO above, but for Mongo checker problems (.json files in
# settings.DMOJ_MONGO_SAMPLE_DATABASES_ROOT).
MONGO_SAMPLE_DATABASE_INFO = {
    'employees': (_('Employees'), _('Una sola col·lecció d\'empleats, pensada per a exercicis molt bàsics.')),
    'blog': (_('Blog'), _('Un blog amb comentaris niats dins de cada article, per practicar consultes de documents.')),
    'students': (_('Students'), _('Notes d\'alumnes per assignatura, pensada per a consultes find() bàsiques.')),
    'library': (_('Library'), _('Una biblioteca de llibres en català, pensada per a exercicis d\'insertOne/insertMany.')),
    'inventory': (_('Inventory'), _('Estoc d\'una botiga d\'informàtica, pensada per a exercicis d\'updateOne/updateMany.')),
    'orders': (_('Orders'), _('Comandes d\'una botiga, pensada per practicar el framework d\'agregació (agrupar i sumar per client).')),
}


def get_mongo_sample_databases():
    """Returns [(key, label, description), ...] for every .json file found in
    settings.DMOJ_MONGO_SAMPLE_DATABASES_ROOT, sorted by label."""
    root = settings.DMOJ_MONGO_SAMPLE_DATABASES_ROOT
    try:
        filenames = [f for f in os.listdir(root) if f.endswith('.json')]
    except OSError:
        return []
    results = []
    for filename in filenames:
        key = filename[:-len('.json')]
        label, description = MONGO_SAMPLE_DATABASE_INFO.get(key, (key, ''))
        results.append((key, label, description))
    results.sort(key=lambda item: item[1])
    return results


def get_mongo_sample_database_path(key):
    """Returns the absolute path to a sample Mongo database given its key, or None if it doesn't
    exist (e.g. an invalid/tampered key) -- always validated against the real directory listing,
    never trusts the key to already be a safe path component."""
    for existing_key, _label, _description in get_mongo_sample_databases():
        if existing_key == key:
            return os.path.join(settings.DMOJ_MONGO_SAMPLE_DATABASES_ROOT, key + '.json')
    return None


class ProblemDataError(Exception):
    def __init__(self, message):
        super(ProblemDataError, self).__init__(message)
        self.message = message


class ProblemDataCompiler(object):
    def __init__(self, problem, data, cases, files):
        self.problem = problem
        self.data = data
        self.cases = cases
        self.files = files

        self.generator = data.generator

    def _get_sql_db_filename(self):
        """
        Returns the filename of the SQL database file,
        or raises ProblemDataError if not configured.
        """
        if not self.data.sql_db:
            raise ProblemDataError(_('SQL checker requires a database file. '
                                     'Please upload one in the "SQL database file" field.'))
        db_path = split_path_first(self.data.sql_db.name)
        if len(db_path) != 2:
            raise ProblemDataError(_('How did you corrupt the SQL database path?'))
        return db_path[1]

    def _get_mongo_db_filename(self):
        """
        Returns the filename of the Mongo database file,
        or raises ProblemDataError if not configured.
        """
        if not self.data.mongo_db:
            raise ProblemDataError(_('Mongo checker requires a database file. '
                                     'Please upload one in the "Mongo database file" field.'))
        db_path = split_path_first(self.data.mongo_db.name)
        if len(db_path) != 2:
            raise ProblemDataError(_('How did you corrupt the Mongo database path?'))
        return db_path[1]

    def make_init(self):
        cases = []
        batch = None

        def end_batch():
            if not batch['batched']:
                raise ProblemDataError(_('Empty batches not allowed.'))
            cases.append(batch)

        def make_checker(case, question_index=None, effective_checker=None):
            checker_name = effective_checker or case.checker
            if checker_name == 'sql':
                db_filename = self._get_sql_db_filename()
                args = {'db_file': db_filename}
                if case.checker_args:
                    try:
                        args.update(json.loads(case.checker_args))
                    except ValueError:
                        pass
                if question_index is not None:
                    args['question_index'] = question_index
                return {
                    'name': 'sql',
                    'args': args,
                }
            if checker_name == 'mongo':
                db_filename = self._get_mongo_db_filename()
                args = {'db_file': db_filename}
                if case.checker_args:
                    try:
                        args.update(json.loads(case.checker_args))
                    except ValueError:
                        pass
                if question_index is not None:
                    args['question_index'] = question_index
                return {
                    'name': 'mongo',
                    'args': args,
                }
            if case.checker_args:
                return {
                    'name': checker_name,
                    'args': json.loads(case.checker_args),
                }
            return checker_name

        sql_question_counter = [0]

        for i, case in enumerate(self.cases, 1):
            if case.type == 'C':
                data = {}
                is_sql = (case.checker in DATABASE_CHECKERS) or (self.data.checker in DATABASE_CHECKERS)

                if batch:
                    case.points = None
                    case.is_pretest = batch['is_pretest']
                else:
                    if case.points is None:
                        raise ProblemDataError(_('Points must be defined for non-batch case #%d.') % i)
                    data['is_pretest'] = case.is_pretest

                if not self.generator:
                    # For SQL problems, input_file is optional
                    if not is_sql:
                        if case.input_file not in self.files:
                            raise ProblemDataError(_('Input file for case %d does not exist: %s') %
                                                   (i, case.input_file))
                    if case.output_file not in self.files:
                        raise ProblemDataError(_('Output file for case %d does not exist: %s') %
                                               (i, case.output_file))

                if case.input_file:
                    data['in'] = case.input_file
                if case.output_file:
                    data['out'] = case.output_file
                if case.points is not None:
                    data['points'] = case.points
                if case.generator_args:
                    data['generator_args'] = case.generator_args.splitlines()
                if case.output_limit is not None:
                    data['output_limit_length'] = case.output_limit
                if case.output_prefix is not None:
                    data['output_prefix_length'] = case.output_prefix
                if case.checker or (is_sql and not batch):
                    question_index = None
                    if not batch and is_sql:
                        sql_question_counter[0] += 1
                        question_index = sql_question_counter[0]
                    effective_checker = case.checker or (self.data.checker if is_sql else '')
                    data['checker'] = make_checker(case, question_index, effective_checker)
                else:
                    case.checker_args = ''
                case.save(update_fields=('checker_args', 'is_pretest'))
                (batch['batched'] if batch else cases).append(data)
            elif case.type == 'S':
                if batch:
                    end_batch()
                if case.points is None:
                    raise ProblemDataError(_('Batch start case #%d requires points.') % i)
                batch = {
                    'points': case.points,
                    'batched': [],
                    'is_pretest': case.is_pretest,
                }
                if case.generator_args:
                    batch['generator_args'] = case.generator_args.splitlines()
                if case.output_limit is not None:
                    batch['output_limit_length'] = case.output_limit
                if case.output_prefix is not None:
                    batch['output_prefix_length'] = case.output_prefix
                if case.checker:
                    batch['checker'] = make_checker(case)
                else:
                    case.checker_args = ''
                case.input_file = ''
                case.output_file = ''
                case.save(update_fields=('checker_args', 'input_file', 'output_file'))
            elif case.type == 'E':
                if not batch:
                    raise ProblemDataError(_('Attempt to end batch outside of one in case #%d') % i)
                case.is_pretest = batch['is_pretest']
                case.input_file = ''
                case.output_file = ''
                case.generator_args = ''
                case.checker = ''
                case.checker_args = ''
                case.save()
                end_batch()
                batch = None
        if batch:
            end_batch()

        init = {}

        if self.data.zipfile:
            zippath = split_path_first(self.data.zipfile.name)
            if len(zippath) != 2:
                raise ProblemDataError(_('How did you corrupt the zip path?'))
            init['archive'] = zippath[1]

        if self.generator:
            generator_path = split_path_first(self.generator.name)
            if len(generator_path) != 2:
                raise ProblemDataError(_('How did you corrupt the generator path?'))
            init['generator'] = generator_path[1]

        pretests = [case for case in cases if case['is_pretest']]
        for case in cases:
            del case['is_pretest']
        if pretests:
            init['pretest_test_cases'] = pretests
        if cases:
            init['test_cases'] = cases
        if self.data.output_limit is not None:
            init['output_limit_length'] = self.data.output_limit
        if self.data.output_prefix is not None:
            init['output_prefix_length'] = self.data.output_prefix
        if self.data.checker:
            init['checker'] = make_checker(self.data)
        else:
            self.data.checker_args = ''
        return init

    def compile(self):
        from judge.models import problem_data_storage

        yml_file = '%s/init.yml' % self.problem.code
        try:
            init = yaml.safe_dump(self.make_init())
        except ProblemDataError as e:
            self.data.feedback = e.message
            self.data.save()
            problem_data_storage.delete(yml_file)
        else:
            self.data.feedback = ''
            self.data.save()
            if init:
                problem_data_storage.save(yml_file, ContentFile(init))
            else:
                problem_data_storage.delete(yml_file)

    @classmethod
    def generate(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        self.compile()