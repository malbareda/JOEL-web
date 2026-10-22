import importlib.util
import io
import json
import os
import shutil
import sqlite3
import sys
import types
from zipfile import ZipFile

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from judge.models import Language, Problem, ProblemData, ProblemGroup, ProblemTestCase, ProblemType, Profile
from judge.models.problem_data import problem_data_storage
from judge.utils import mysql_grader
from judge.utils.problem_data import MYSQL_WRITE_STATEMENTS, ProblemDataCompiler, get_sql_sample_database_path, \
    get_sql_sample_databases, sql_statement_keyword


def _load_judge_sql_checker():
    """Loads the judge engine's SQL checker by file path: this repo has its own `dmoj` package (the site
    settings) that shadows the engine's, so a normal import can't reach `dmoj.checkers`. Reusing the real
    helpers means a reference query accepted here is also accepted when graded."""
    candidates = [os.path.join(d, 'dmoj', 'checkers', 'sql.py') for d in sys.path if d]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if path is None:
        raise ImportError('Could not find the judge engine\'s dmoj/checkers/sql.py in sys.path')
    spec = importlib.util.spec_from_file_location('judge_engine_sql_checker', path)
    module = importlib.util.module_from_spec(spec)
    # The checker also imports engine modules (dmoj.judgeenv, dmoj.result) that are shadowed the same way. It
    # only uses them inside check(), which we never call, so stub them just while the file is loaded.
    stubs = {'dmoj.judgeenv': types.SimpleNamespace(get_problem_root=None),
             'dmoj.result': types.SimpleNamespace(CheckerResult=None)}
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in saved.items():
            if old is None:
                del sys.modules[name]
            else:
                sys.modules[name] = old
    return module


_sql_checker = _load_judge_sql_checker()
_execute_sql = _sql_checker._execute_sql
_execute_write = _sql_checker._execute_write
_security_check = _sql_checker._security_check
_make_temp_copy = _sql_checker._make_temp_copy
_dump_all_tables = _sql_checker._dump_all_tables
_detect_statement_type = _sql_checker._detect_statement_type

MAX_REFERENCE_ROWS = 20000
AUTHORS = ('edgar', 'marc')


class BatchError(Exception):
    pass


def _list_tables(db_path):
    conn = sqlite3.connect('file:%s?mode=ro' % db_path, uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    finally:
        conn.close()


def validate_write_question(db_path, sql, kind):
    """Same as validate_question for an INSERT/UPDATE reference statement. The checker grades these by running the
    student's statement and the reference one on separate copies of the database and comparing the final content of
    every table, so a reference that changes nothing would accept any statement that also changes nothing."""
    msg = _security_check(sql, kind)
    if msg:
        return [msg]
    try:
        with _make_temp_copy(db_path) as copy:
            before = _dump_all_tables(copy)
            _execute_write(copy, sql)
            after = _dump_all_tables(copy)
    except Exception as e:
        return ['statement fails: %s' % e]
    if before == after:
        return ['statement does not change the database']
    return []


def validate_mysql_write_question(database, sql, kind):
    """validate_write_question for the mysql engine: the statement runs on the writable copy w_<database> inside a
    transaction that is rolled back (the same way the judge's mysqlwrite checker grades it)."""
    if ';' in sql.strip().rstrip(';'):
        return ['only a single statement is allowed']
    try:
        before, after = mysql_grader.run_write(database, sql)
    except Exception as e:
        return ['statement fails: %s' % e]
    if before == after:
        return ['statement does not change the database']
    return []


def statement_kind(info, sql):
    """SELECT/INSERT/UPDATE (and DELETE with the mysql engine), or None for anything else."""
    if info['engine'] == 'mysql':
        keyword = sql_statement_keyword(sql)
        if keyword in MYSQL_WRITE_STATEMENTS:
            return keyword
    return _detect_statement_type(sql)


def validate_question(info, sql):
    """Returns a list of problems with this reference query (empty if it is fine)."""
    kind = statement_kind(info, sql)
    if info['engine'] == 'mysql' and kind in MYSQL_WRITE_STATEMENTS:
        return validate_mysql_write_question(info['database'], sql, kind)
    if kind in ('INSERT', 'UPDATE'):
        return validate_write_question(info['db_path'], sql, kind)
    errors = []
    msg = _security_check(sql, 'SELECT')
    if msg:
        return [msg]
    upper = ' '.join(sql.upper().split())
    if ' LIMIT ' in upper and ' ORDER BY ' not in upper:
        errors.append('LIMIT without ORDER BY: result is not deterministic')
    try:
        if info['engine'] == 'mysql':
            columns, rows = mysql_grader.run_query(info['database'], sql, MAX_REFERENCE_ROWS)
        else:
            columns, rows = _execute_sql(info['db_path'], sql)
    except Exception as e:
        return errors + ['query fails: %s' % e]
    if not columns:
        errors.append('query returns no columns')
    if not rows:
        errors.append('query returns no rows')
    if len(rows) > MAX_REFERENCE_ROWS:
        errors.append('query returns %d rows (max %d)' % (len(rows), MAX_REFERENCE_ROWS))
    return errors


def load_batch(path):
    with open(path, encoding='utf-8') as f:
        batch = json.load(f)
    if 'problems' not in batch:
        raise BatchError('%s: missing "problems"' % path)
    return batch


def resolve(batch, n, prob):
    """Everything about problem number `n` of a batch that may be set per problem or once for the whole batch:
    its code, engine ("mysql", the only one accepted now), database (and a human label for it) and problem type
    name. "database" is a database on the MariaDB grading server. The SQLite engine is no longer used for new
    problems: SQL problems are graded on MySQL, and its code paths below only remain for reference."""
    database = prob.get('database') or batch.get('database')
    if not database:
        raise BatchError('problem #%d: no "database" (neither in the problem nor in the batch)' % n)
    engine = prob.get('engine') or batch.get('engine') or 'mysql'
    if engine == 'mysql':
        db_path = None
        if not mysql_grader.is_mysql_database(database):
            raise BatchError('problem #%d: database "%s" is not on the MySQL grading server' % (n, database))
    elif engine == 'sqlite':
        raise BatchError('problem #%d: the SQLite engine is no longer used; use "engine": "mysql" and a database '
                         'of the MySQL grading server' % n)
    else:
        raise BatchError('problem #%d: unknown engine "%s" (use "mysql")' % (n, engine))
    code = prob.get('code') or ('%s%02d' % (batch['code_prefix'], n) if batch.get('code_prefix') else None)
    if not code:
        raise BatchError('problem #%d: no "code" (and the batch has no "code_prefix")' % n)
    label = prob.get('label') or batch.get('label') or next(
        (lbl for key, lbl, _desc in get_sql_sample_databases() if key.lower() == database.lower()), database)
    return {'code': code, 'database': database, 'engine': engine, 'db_path': db_path, 'label': label,
            'type': prob.get('type') or batch.get('type')}


def check_batch(batch):
    """Validates every question of a batch. Returns a list of error strings."""
    errors = []
    seen = set()
    codes = set()
    for n, prob in enumerate(batch['problems'], 1):
        try:
            info = resolve(batch, n, prob)
        except BatchError as e:
            errors.append(str(e))
            continue
        code = info['code']
        if code in codes:
            errors.append('%s: duplicated problem code' % code)
        codes.add(code)
        if len(code) > 20:
            errors.append('%s: code longer than 20 characters' % code)
        if info['type']:
            if not ProblemType.objects.filter(name=info['type']).exists():
                errors.append('%s: unknown problem type "%s"' % (code, info['type']))
        elif not Problem.objects.filter(code=code).exists():
            errors.append('%s: no "type" for a new problem' % code)
        if not prob.get('questions'):
            errors.append('%s: no questions' % code)
        for q, question in enumerate(prob.get('questions', []), 1):
            where = '%s q%d' % (code, q)
            if not question.get('text', '').strip():
                errors.append('%s: empty question text' % where)
            if question.get('text') in seen:
                errors.append('%s: duplicated question text' % where)
            seen.add(question.get('text'))
            for err in validate_question(info, question.get('sql', '')):
                errors.append('%s: %s' % (where, err))
    return errors


def make_description(info, prob):
    if info['engine'] == 'mysql':
        table_names = [table['name'] for table in mysql_grader.get_schema(info['database'])[0]]
    else:
        table_names = _list_tables(info['db_path'])
    tables = ', '.join('`%s`' % t for t in table_names)
    parts = []
    if prob.get('intro'):
        parts.append(prob['intro'].strip())
    parts.append('Aquest problema fa servir la base de dades **%s**, amb les taules següents: %s. '
                 'Pots consultar l\'esquema complet amb el botó **"View the database schema"** '
                 'd\'aquesta mateixa pàgina.' % (info['label'], tables))
    if info['engine'] == 'mysql':
        parts.append('Les consultes s\'executen sobre **MySQL** (MariaDB), així que pots fer servir la sintaxi i les '
                     'funcions de MySQL que fas servir a classe.')
    kinds = {statement_kind(info, q['sql']) for q in prob['questions']}
    if kinds == {'SELECT'}:
        parts.append('Cada pregunta es contesta amb una consulta `SELECT` independent, en el seu propi quadre de '
                     'text. Es comparen el nombre de columnes i les files del resultat; els noms de les columnes i '
                     'l\'ordre de les files no es tenen en compte.')
    else:
        word = ' o '.join('`%s`' % k for k in sorted(k for k in kinds if k))
        parts.append('Cada pregunta es contesta amb **una sola sentència** %s, en el seu propi quadre de text. '
                     'Cada pregunta s\'executa per separat sobre una còpia de la base de dades original: els canvis '
                     'd\'una pregunta no afecten les altres. Per donar-la per bona es compara el contingut final de '
                     'totes les taules amb el que deixaria la solució del professor, així que cal escriure '
                     'exactament els valors demanats (els números sense cometes i els textos entre cometes '
                     'simples).%s' % (word, '' if info['engine'] == 'mysql' else ' No es permet `DELETE`.'))
    return '\n\n'.join(parts)


def build_zip(questions):
    buf = io.BytesIO()
    with ZipFile(buf, 'w') as z:
        for n, question in enumerate(questions, 1):
            z.writestr('q%d.sql' % n, question['sql'].strip() + '\n')
    return buf.getvalue()


def create_problem(batch, n, prob, author, group, language, replace):
    info = resolve(batch, n, prob)
    code = info['code']
    questions = prob['questions']
    existing = Problem.objects.filter(code=code).first()
    if existing and not replace:
        return code, 'skipped (already exists)'

    with transaction.atomic():
        if existing:
            problem = existing
            problem.cases.all().delete()
        else:
            problem = Problem(code=code)
        problem.name = prob['name']
        problem.description = make_description(info, prob)
        problem.group = group
        problem.time_limit = 2.0
        problem.memory_limit = 64000
        problem.points = float(sum(q.get('points', 1) for q in questions))
        problem.partial = True
        if not existing:  # --replace keeps a problem that was already published public
            problem.is_public = False
        problem.save()
        if info['type']:
            problem.types.set([ProblemType.objects.get(name=info['type'])])
        problem.allowed_languages.set([language])
        if not existing:  # --replace keeps whoever the problem's authors are now
            problem.authors.set([author])

        checker = 'mysql' if info['engine'] == 'mysql' else 'sql'
        data, _created = ProblemData.objects.get_or_create(problem=problem)
        data.checker = checker
        # The mysql checker finds its database in the problem's checker_args; the SQLite one uses the .db file.
        data.checker_args = json.dumps({'database': info['database']}) if checker == 'mysql' else ''
        data.save()
        if data.zipfile:
            data.zipfile.delete(save=False)
        if data.sql_db:
            data.sql_db.delete(save=False)
        data.zipfile.save('data.zip', ContentFile(build_zip(questions)), save=False)
        if checker == 'sql':
            with open(info['db_path'], 'rb') as f:
                data.sql_db.save('%s.db' % info['database'], ContentFile(f.read()), save=False)
        data.save()

        for order, question in enumerate(questions, 1):
            ProblemTestCase.objects.create(
                dataset=problem, order=order, type='C', input_file='', output_file='q%d.sql' % order,
                points=question.get('points', 1), is_pretest=False, checker=checker,
                checker_args=json.dumps({'question': question['text'].strip()}))

        with ZipFile(data.zipfile.path) as z:
            valid_files = z.namelist()
        ProblemDataCompiler.generate(problem, data, problem.cases.order_by('order'), valid_files)
        data.refresh_from_db()
        if data.feedback:
            raise BatchError('%s: compiler error: %s' % (code, data.feedback))
    return code, 'created' if not existing else 'replaced'


class Command(BaseCommand):
    help = ('Create (private) SQL SELECT problems in bulk from JSON batch files. '
            'Every reference query is validated against the real database first.')

    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', help='batch JSON file(s)')
        parser.add_argument('--dry-run', action='store_true', help='only validate, create nothing')
        parser.add_argument('--replace', action='store_true',
                            help='overwrite problems whose code already exists (default: skip them)')
        parser.add_argument('--limit', type=int, default=None, help='only create the first N problems of each file')
        parser.add_argument('--only', nargs='+', metavar='CODE', help='only these problem codes')

    def handle(self, *args, **options):
        batches = []
        failed = False
        for path in options['files']:
            try:
                batch = load_batch(path)
            except (BatchError, ValueError, IOError) as e:
                raise CommandError(str(e))
            if options['limit']:
                batch['problems'] = batch['problems'][:options['limit']]
            if options['only']:
                batch['problems'] = [p for n, p in enumerate(batch['problems'], 1)
                                     if resolve(batch, n, p)['code'] in options['only']]
            errors = check_batch(batch)
            nq = sum(len(p['questions']) for p in batch['problems'])
            self.stdout.write('%s: %d problems, %d questions, %d errors' %
                              (os.path.basename(path), len(batch['problems']), nq, len(errors)))
            for err in errors:
                self.stderr.write('  ERROR %s' % err)
            failed = failed or bool(errors)
            batches.append(batch)
        if failed:
            raise CommandError('validation failed, nothing was created')
        if options['dry_run']:
            self.stdout.write('dry run OK, nothing created')
            return

        # A batch may name its own author(s) with "author" (one username) or "authors" (a list); otherwise the
        # problems alternate over the default AUTHORS. Resolve every batch's authors up front so a bad username
        # fails before any problem is created.
        def resolve_authors(batch):
            names = batch.get('authors') or ([batch['author']] if batch.get('author') else None) or AUTHORS
            try:
                return [Profile.objects.get(user__username=u) for u in names]
            except Profile.DoesNotExist:
                raise CommandError('unknown author username in %r' % (list(names),))
        batch_authors_list = [resolve_authors(batch) for batch in batches]
        group = ProblemGroup.objects.get(name='sql')
        language = Language.objects.get(key='TEXT')
        position = 0  # authors alternate over the whole run, not per file, so odd-sized files stay balanced
        for batch, batch_authors in zip(batches, batch_authors_list):
            for n, prob in enumerate(batch['problems'], 1):
                position += 1
                try:
                    code, status = create_problem(batch, n, prob, batch_authors[(position - 1) % len(batch_authors)],
                                                  group, language,
                                                  options['replace'])
                except Exception:
                    # Don't leave a half-written data directory behind for a problem that rolled back.
                    code = resolve(batch, n, prob)['code']
                    if not Problem.objects.filter(code=code).exists():
                        shutil.rmtree(problem_data_storage.path(code), ignore_errors=True)
                    raise
                self.stdout.write('  %s: %s' % (code, status))
