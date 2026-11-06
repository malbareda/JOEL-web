"""Web-side access to the PostgreSQL server that grades the Postgres-only problems ("postgres" checker).

The judge's checker (dmoj/checkers/postgres.py) grades the submissions; this module lists the databases a problem
can use, shows a database's schema, and validates a reference with that same checker code.

Roles (credentials in /home/ubuntu/.secrets): joel_pg_read (SELECT only) and joel_pg_run (writes and routines,
always rolled back). Listing the databases uses the instance's administrator: the OS user that runs the site,
over the local socket (peer authentication), and only to read pg_database.
"""
import re
import subprocess

import psycopg2
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from judge.utils.judge_checkers import load_judge_checker

READ_CONFIG = getattr(settings, 'JOEL_PG_READ_CNF', '/home/ubuntu/.secrets/joel_pg_read.conf')
SOCKET_DIR = getattr(settings, 'JOEL_PG_SOCKET_DIR', '/var/run/postgresql')
DUMP_TIMEOUT = getattr(settings, 'JOEL_DUMP_TIMEOUT', 60)
_DATABASE_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,63}$')
# pg_dump 17 starts with this setting, which servers before PostgreSQL 17 reject.
_TRANSACTION_TIMEOUT_RE = re.compile(br'^SET transaction_timeout = 0;\n', re.MULTILINE)

POSTGRES_DATABASE_INFO = {
    'chinook': (_('Chinook (PostgreSQL)'), _('Botiga de música digital: artistes, àlbums, pistes, clients, '
                                             'factures...')),
    'northwind': (_('Northwind (PostgreSQL)'), _('Vendes: clients, comandes, productes, proveïdors, empleats...')),
    'pagila': (_('Pagila (PostgreSQL)'), _('Videoclub (la sakila de PostgreSQL), amb funcions, triggers, vistes i '
                                           'taules particionades.')),
}


class GraderUnavailable(Exception):
    pass


class DumpError(Exception):
    pass


def _config(path):
    values = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    return values


def connect(database):
    try:
        return psycopg2.connect(dbname=database, connect_timeout=5, application_name='joel-site', **_config(READ_CONFIG))
    except psycopg2.Error as e:
        raise GraderUnavailable(str(e))


def get_postgres_databases():
    """[(name, label, description), ...] for every database the read-only grading role may connect to, sorted by
    label, or [] if the server can't be reached."""
    try:
        conn = psycopg2.connect(dbname='postgres', host=SOCKET_DIR, connect_timeout=5)
    except psycopg2.Error:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres' "
                           "AND has_database_privilege('joel_pg_read', datname, 'CONNECT') ORDER BY datname")
            names = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
    results = []
    for name in names:
        label, description = POSTGRES_DATABASE_INFO.get(name, (name, ''))
        results.append((name, str(label), str(description)))
    results.sort(key=lambda item: item[1].lower())
    return results


def is_postgres_database(name):
    return any(existing == name for existing, _label, _description in get_postgres_databases())


def dump_database(database):
    """Returns a `pg_dump` of `database` as bytes, for students to load into an empty database of their own. Runs as
    the instance's administrator (peer authentication over the socket): the read-only grading role can't read the
    sequences, so it can't dump. The rows go as INSERTs, not as COPY ... FROM stdin (a psql command that graphical
    clients such as DBeaver can't run in a script), and the PostgreSQL 17-only setting on its first lines is left out.
    Raises DumpError if the dump can't be made."""
    if not _DATABASE_NAME_RE.match(database):
        raise DumpError('invalid database name: %r' % database)
    command = ['pg_dump', '--host=%s' % SOCKET_DIR, '--no-owner', '--no-privileges', '--rows-per-insert=100',
               '--dbname=%s' % database]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=DUMP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DumpError(str(e))
    if result.returncode:
        raise DumpError(result.stderr.decode('utf-8', 'replace').strip())
    return _TRANSACTION_TIMEOUT_RE.sub(b'', result.stdout)


def get_schema(database):
    """(tables, relationships) in the shape the schema view expects (see mysql_grader.get_schema)."""
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                           "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relispartition "
                           "ORDER BY c.relname")
            names = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT c.table_name, c.column_name, "
                           "CASE WHEN c.data_type = 'USER-DEFINED' THEN c.udt_name ELSE c.data_type END, "
                           "EXISTS (SELECT 1 FROM information_schema.table_constraints tc "
                           "JOIN information_schema.key_column_usage k ON k.constraint_name = tc.constraint_name "
                           "AND k.table_schema = tc.table_schema AND k.table_name = tc.table_name "
                           "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public' "
                           "AND tc.table_name = c.table_name AND k.column_name = c.column_name) "
                           "FROM information_schema.columns c WHERE c.table_schema = 'public' "
                           "ORDER BY c.table_name, c.ordinal_position")
            columns = {}
            for table, column, column_type, pk in cursor.fetchall():
                columns.setdefault(table, []).append({'name': column, 'type': column_type, 'pk': pk})
            cursor.execute("SELECT cl.relname, a.attname, ref.relname FROM pg_constraint con "
                           "JOIN pg_class cl ON cl.oid = con.conrelid JOIN pg_class ref ON ref.oid = con.confrelid "
                           "JOIN pg_namespace n ON n.oid = cl.relnamespace "
                           "JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1] "
                           "WHERE con.contype = 'f' AND n.nspname = 'public' AND NOT cl.relispartition "
                           "ORDER BY cl.relname")
            relationships = [{'from_table': table, 'from_column': column, 'to_table': referenced}
                             for table, column, referenced in cursor.fetchall()]
            tables = []
            for name in names:
                definition = ',\n'.join('  %s %s%s' % (col['name'], col['type'], ' PRIMARY KEY' if col['pk'] else '')
                                        for col in columns.get(name, []))
                tables.append({'name': name, 'create_sql': 'CREATE TABLE %s (\n%s\n);' % (name, definition),
                               'columns': columns.get(name, [])})
    finally:
        conn.rollback()
        conn.close()
    return tables, relationships


def validate_reference(database, reference, max_rows=None):
    """Grades the reference against itself with the judge's checker: returns a list of problems (empty if fine)
    and the mode ('query', 'write' or 'routine')."""
    checker = load_judge_checker('postgres')
    tests = checker._TEST_MARKER_RE.findall(reference)
    code = checker._TEST_MARKER_RE.sub('', reference).strip()
    try:
        statements = checker.split_statements(code)
    except ValueError as e:
        return ['reference does not parse: %s' % e], None
    if not statements:
        return ['empty reference'], None
    first = checker._keyword(statements[0])
    if first in checker._QUERY_KEYWORDS and len(statements) == 1 and not tests:
        mode = 'query'
    elif first in checker._WRITE_KEYWORDS and len(statements) == 1 and not tests:
        mode = 'write'
    else:
        mode = 'routine'
    errors = []
    try:
        if mode == 'query':
            columns, rows = checker._run_query(database, statements[0])
            if not columns:
                errors.append('query returns no columns')
            if not rows:
                errors.append('query returns no rows')
            if max_rows is not None and len(rows) > max_rows:
                errors.append('query returns %d rows (max %d)' % (len(rows), max_rows))
        else:
            outcomes, state = checker._run_transaction(database, statements, tests)
            if mode == 'write' and not state:
                errors.append('statement does not change the database')
            if mode == 'routine':
                if not tests:
                    errors.append('a routine question needs tests (--@@TEST@@ lines)')
                elif all(outcome[0] == 'error' for outcome in outcomes):
                    errors.append('every test gives an error with the reference')
    except psycopg2.Error as e:
        errors.append('reference fails: %s' % checker._error_text(e))
    result = checker.check(reference, reference, database=database)
    if errors == [] and not result.passed:
        errors.append('the reference does not pass against itself: %s' % result.feedback)
    return errors, mode
