"""Web-side access to the MariaDB instance that grades "mysql" checker problems.

The judge's checkers (dmoj/checkers/mysql.py for SELECT, mysqlwrite.py for INSERT/UPDATE/DELETE) run the
student's and the reference statements there; this module lets the site list the databases it can grade on,
show a database's schema, validate a reference statement, and load SQL dumps.

Databases on the grading server:
- catalog databases (hotel, Chinook...), loaded by an administrator with `manage.py load_grader_db`;
- `p_<problem code>`, a teacher's own dump for one problem, loaded when the problem data is saved;
- `w_<name>`, a writable copy of each of those, where write questions run inside a transaction that is
  always rolled back. Write questions never touch the databases SELECT questions read.

Users: `joel_grader` (SELECT on catalog and p_* databases), `joel_writer` (SELECT/INSERT/UPDATE/DELETE on
w_* databases only), `joel_loader` (creates and drops p_*/w_* databases, and the throwaway users that load
them), and the instance's administrator (the `ubuntu` OS user over the socket), only for catalog databases.
"""
import re
import secrets

import pymysql
from django.conf import settings
from pymysql.constants import CLIENT

from django.utils.translation import gettext_lazy as _

from judge.utils.problem_data import SQL_SAMPLE_DATABASE_INFO

# [client] option files with each user's credentials and socket.
CLIENT_CONFIG = getattr(settings, 'JOEL_MYSQL_CNF', '/home/ubuntu/.secrets/joel_grader.cnf')
WRITER_CONFIG = getattr(settings, 'JOEL_MYSQL_WRITER_CNF', '/home/ubuntu/.secrets/joel_writer.cnf')
LOADER_CONFIG = getattr(settings, 'JOEL_MYSQL_LOADER_CNF', '/home/ubuntu/.secrets/joel_loader.cnf')
ADMIN_SOCKET = getattr(settings, 'JOEL_MYSQL_SOCKET', '/home/ubuntu/mariadb-grader/run/mysqld.sock')
ADMIN_USER = getattr(settings, 'JOEL_MYSQL_ADMIN_USER', 'ubuntu')

# Teachers' dumps are loaded while the problem data form is being saved, so they must fit in the request.
MAX_DUMP_BYTES = getattr(settings, 'JOEL_MYSQL_MAX_DUMP_BYTES', 10 * 1024 * 1024)

_SYSTEM_DATABASES = ('information_schema', 'mysql', 'performance_schema', 'sys')

# Labels of catalog databases that have no SQLite counterpart (or a different name), by lowercased name.
MYSQL_DATABASE_INFO = {
    'company': (_('Employees'), _('Una sola taula d\'empleats, pensada per a exercicis molt bàsics.')),
    'knightsdb': (_('Knights & Dragons'), _('Cavallers i dracs (en català), pensada per a exercicis senzills.')),
    'miniwind_classic': (_('Miniwind clàssica'), _('Versió petita a l\'estil Northwind: categories, clients, '
                                                   'productes i comandes.')),
    'sakila': (_('Sakila'), _('Videoclub (BD d\'exemple oficial de MySQL): pel·lícules, actors, clients, lloguers, '
                              'pagaments...')),
    'valorantpromatches': (_('Valorant Pro Matches'), _('Partides professionals de Valorant: equips, jugadors, '
                                                        'mapes, agents, estadístiques...')),
    'futbol24': (_('Futbol24'), _('Partits internacionals de futbol, golejadors i tandes de penals.')),
    'ies23g': (_('IES 2023'), _('Institut: usuaris, grups, cicles, mòduls, unitats formatives, qualificacions, '
                                'tasques...')),
}
_DATABASE_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,60}$')


class GraderUnavailable(Exception):
    pass


class DumpError(Exception):
    pass


def problem_database(code):
    """The database a problem's own dump is loaded into."""
    return 'p_%s' % code


def writable_database(database):
    """The writable copy of a database, where write questions are graded."""
    return 'w_%s' % database


def connect(database=None):
    try:
        return pymysql.connect(read_default_file=CLIENT_CONFIG, database=database, charset='utf8mb4',
                               autocommit=True, connect_timeout=5, read_timeout=15)
    except pymysql.MySQLError as e:
        raise GraderUnavailable(str(e))


def get_mysql_databases():
    """Returns [(name, label, description), ...] for every catalog database (not a problem's own p_* one)
    the grading user can read, sorted by label, or [] if the grading server can't be reached. Labels reuse
    the SQLite sample databases' ones when the name matches (ignoring case)."""
    try:
        conn = connect()
    except GraderUnavailable:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute('SHOW DATABASES')
            names = [row[0] for row in cursor.fetchall()
                     if row[0] not in _SYSTEM_DATABASES and not row[0].startswith(('p_', 'w_'))]
    finally:
        conn.close()
    info = {key.lower(): value for key, value in SQL_SAMPLE_DATABASE_INFO.items()}
    info.update(MYSQL_DATABASE_INFO)
    results = []
    for name in names:
        label, description = info.get(name.lower(), (name, ''))
        results.append((name, str(label), str(description)))
    results.sort(key=lambda item: item[1].lower())
    return results


def is_mysql_database(name):
    return any(existing == name for existing, _label, _description in get_mysql_databases())


def get_schema(database):
    """Returns (tables, relationships) in the same shape the SQLite schema view builds:
    tables = [{'name', 'create_sql', 'columns': [{'name', 'type', 'pk'}]}],
    relationships = [{'from_table', 'from_column', 'to_table'}]."""
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables "
                           "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name", [database])
            names = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT table_name, column_name, column_type, column_key FROM information_schema.columns "
                           "WHERE table_schema = %s ORDER BY table_name, ordinal_position", [database])
            columns = {}
            for table, column, column_type, key in cursor.fetchall():
                columns.setdefault(table, []).append({'name': column, 'type': column_type, 'pk': key == 'PRI'})
            cursor.execute("SELECT table_name, column_name, referenced_table_name "
                           "FROM information_schema.key_column_usage "
                           "WHERE table_schema = %s AND referenced_table_name IS NOT NULL "
                           "ORDER BY table_name, ordinal_position", [database])
            relationships = [{'from_table': table, 'from_column': column, 'to_table': referenced}
                             for table, column, referenced in cursor.fetchall()]
            tables = []
            for name in names:
                cursor.execute('SHOW CREATE TABLE `%s`' % name.replace('`', '``'))
                tables.append({'name': name, 'create_sql': cursor.fetchone()[1], 'columns': columns.get(name, [])})
    finally:
        conn.close()
    return tables, relationships


def run_query(database, sql, max_rows=None):
    """Runs a query as the grading user and returns (columns, rows), reading at most max_rows + 1 rows
    when max_rows is given (so callers can tell "more than max_rows" apart)."""
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if max_rows is None else cursor.fetchmany(max_rows + 1)
    finally:
        conn.close()
    return columns, list(rows)


# --- Loading dumps -------------------------------------------------------------------------------------------------

# Statements that would pick, create or drop a database by name. A dump is always loaded into the database chosen
# by the caller, so these lines are dropped (the throwaway user that runs the dump couldn't run them anyway).
_DATABASE_LINE_RE = re.compile(r'^\s*(?:/\*!\d+\s*)?(?:(?:CREATE|DROP)\s+(?:DATABASE|SCHEMA)\b|USE\s)[^\n]*$',
                               re.IGNORECASE | re.MULTILINE)
# DEFINER=`user`@`host` clauses need SUPER to load as another user; without one the object is owned by the loader.
_DEFINER_RE = re.compile(r"DEFINER\s*=\s*(?:`[^`]*`|'[^']*'|[\w.$-]+)\s*@\s*(?:`[^`]*`|'[^']*'|[\w.%-]+)",
                         re.IGNORECASE)
# The first line newer mariadb-dump versions write (10.11.8+): a client-side command that older clients reject.
_SANDBOX_LINE_RE = re.compile(r'^/\*M!999999\\- enable the sandbox mode \*/[^\n]*\n?')
_DELIMITER_RE = re.compile(r'^\s*DELIMITER\s+(\S+)\s*$', re.IGNORECASE)
# The database a dump was exported from, as named by its CREATE DATABASE / USE lines.
_DUMP_DATABASE_NAME_RE = re.compile(r'(?:(?:CREATE|DROP)\s+(?:DATABASE|SCHEMA)\s+(?:/\*.*?\*/\s*)?(?:IF\s+(?:NOT\s+)?EXISTS\s+)?'
                                    r'(?:/\*.*?\*/\s*)?|USE\s+)`?(\w+)`?', re.IGNORECASE)
# A whole line that is only a version-conditional statement: /*!50503 SET NAMES utf8mb4 */; or /*M!100616 ... */;
_CONDITIONAL_LINE_RE = re.compile(r'^\s*/\*(M?)!(\d+)\s.*\*/\s*;\s*$', re.MULTILINE)


def prepare_dump(text, server_version=100505):
    """Turns a mysqldump/phpMyAdmin/Workbench export into statements that can be sent to the server as they are,
    in one multi-statement request, and loaded into whichever database the connection uses. The text never goes
    through the `mariadb` command-line client, whose own commands (`\\! shell command`, `source file`...) would
    run on this server."""
    text = text.lstrip('﻿').replace('\r\n', '\n')
    text = _SANDBOX_LINE_RE.sub('', text)
    original_names = {match.group(1) for line in _DATABASE_LINE_RE.findall(text)
                      for match in [_DUMP_DATABASE_NAME_RE.search(line)] if match}
    text = _DATABASE_LINE_RE.sub('', text)
    # Tables named with the original database (`hotel`.`Rooms`) go into the target database instead.
    for name in original_names:
        text = re.sub(r'`%s`\.(?=[`\w])|\b%s\.(?=[`A-Za-z_])' % (re.escape(name), re.escape(name)), '', text)
    # A conditional statement for a newer server than this one is just a comment here, which would leave an empty
    # statement (";") that the server rejects in a multi-statement request. The command-line client skips those.
    text = _CONDITIONAL_LINE_RE.sub(
        lambda m: '' if m.group(1) == 'M' and int(m.group(2)) > server_version else m.group(0), text)
    text = _DEFINER_RE.sub('', text)
    if re.search(r'^\s*DELIMITER\s', text, re.IGNORECASE | re.MULTILINE):
        # DELIMITER is a client command (used around triggers and routines). The server's own multi-statement
        # parser already understands BEGIN ... END bodies, so each custom delimiter just becomes ';'.
        lines, delimiter = [], ';'
        for line in text.split('\n'):
            match = _DELIMITER_RE.match(line)
            if match:
                delimiter = match.group(1)
                continue
            if delimiter != ';' and line.rstrip().endswith(delimiter):
                line = line.rstrip()[:-len(delimiter)] + ';'
            lines.append(line)
        text = '\n'.join(lines)
    return text


def _admin_connect(**kwargs):
    return pymysql.connect(unix_socket=ADMIN_SOCKET, user=ADMIN_USER, charset='utf8mb4', autocommit=True, **kwargs)


def _loader_connect(**kwargs):
    try:
        return pymysql.connect(read_default_file=LOADER_CONFIG, charset='utf8mb4', autocommit=True,
                               connect_timeout=5, **kwargs)
    except pymysql.MySQLError as e:
        raise GraderUnavailable(str(e))


def _check_name(database):
    if not _DATABASE_NAME_RE.match(database):
        raise DumpError('invalid database name: %r' % database)


def load_dump(text, database, admin=False):
    """(Re)creates `database` on the grading server from a dump, replacing whatever it held. Every table is made
    InnoDB, since write questions rely on rolling back. With admin=False (teachers' uploads) only p_* and w_*
    databases can be touched. Raises DumpError with MariaDB's message if the dump doesn't load; the database is
    then dropped, so a failed load never leaves a half-loaded one behind."""
    _check_name(database)
    if not admin and not database.startswith(('p_', 'w_')):
        raise DumpError('only p_* and w_* databases can be loaded from the web')
    conn = _admin_connect() if admin else _loader_connect()
    with conn.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        major, minor, patch = (re.match(r'(\d+)\.(\d+)\.(\d+)', cursor.fetchone()[0]).groups())
    text = prepare_dump(text, int(major) * 10000 + int(minor) * 100 + int(patch))
    user = owner_user(database)
    password = secrets.token_urlsafe(24)
    loaded = False
    try:
        with conn.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS `%s`' % database)
            cursor.execute('CREATE DATABASE `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci' % database)
            # The dump runs as the database's own user, which can only touch this one database. It stays (locked, so
            # nobody can log in as it) as the definer of the dump's views, triggers and routines, which run with its
            # privileges: without it they would refer to a user that no longer exists and fail.
            cursor.execute("DROP USER IF EXISTS %s@'localhost'", [user])
            cursor.execute("CREATE USER %s@'localhost' IDENTIFIED BY %s", [user, password])
            # In GRANT the database name is a pattern ('_' = any character): escape it, both to grant exactly this
            # database and because the loader may only grant on names it holds (p\_%, w\_%), not on patterns.
            escaped = database.replace('\\', '\\\\').replace('_', '\\_').replace('%', '\\%')
            cursor.execute("GRANT ALL PRIVILEGES ON `%s`.* TO %%s@'localhost'" % escaped, [user])
        try:
            loader = pymysql.connect(unix_socket=ADMIN_SOCKET, user=user, password=password, database=database,
                                     charset='utf8mb4', autocommit=True, client_flag=CLIENT.MULTI_STATEMENTS)
            try:
                with loader.cursor() as cursor:
                    cursor.execute(text)
                    while cursor.nextset():
                        pass
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s "
                                   "AND table_type = 'BASE TABLE' AND engine <> 'InnoDB'", [database])
                    for (table,) in cursor.fetchall():
                        cursor.execute('ALTER TABLE `%s` ENGINE=InnoDB' % table.replace('`', '``'))
            finally:
                loader.close()
            loaded = True
        except pymysql.MySQLError as e:
            with conn.cursor() as cursor:
                cursor.execute('DROP DATABASE IF EXISTS `%s`' % database)
            raise DumpError(e.args[1] if len(e.args) > 1 else str(e))
    finally:
        try:
            with conn.cursor() as cursor:
                if loaded:
                    cursor.execute("ALTER USER %s@'localhost' ACCOUNT LOCK", [user])
                else:
                    cursor.execute("DROP USER IF EXISTS %s@'localhost'", [user])
        finally:
            conn.close()


def owner_user(database):
    """The locked user that owns a loaded database's views, triggers and routines (MariaDB allows 80 characters)."""
    return 'own_%s' % database


def load_problem_dump(code, text):
    """Loads a teacher's dump as problem `code`'s database (and its writable copy). Returns the database name."""
    if len(text.encode('utf-8')) > MAX_DUMP_BYTES:
        raise DumpError('the dump is larger than %d MB' % (MAX_DUMP_BYTES // (1024 * 1024)))
    database = problem_database(code)
    load_dump(text, database)
    load_dump(text, writable_database(database))
    return database


def drop_problem_databases(code):
    database = problem_database(code)
    conn = _loader_connect()
    try:
        with conn.cursor() as cursor:
            for name in (database, writable_database(database)):
                cursor.execute('DROP DATABASE IF EXISTS `%s`' % name)
                cursor.execute("DROP USER IF EXISTS %s@'localhost'", [owner_user(name)])
    finally:
        conn.close()


# --- Write statements ----------------------------------------------------------------------------------------------

def _writer_connect(database):
    try:
        return pymysql.connect(read_default_file=WRITER_CONFIG, database=database, charset='utf8mb4',
                               autocommit=False, connect_timeout=5, read_timeout=30)
    except pymysql.MySQLError as e:
        raise GraderUnavailable(str(e))


def _dump_tables(cursor, database):
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s "
                   "AND table_type = 'BASE TABLE' ORDER BY table_name", [database])
    state = {}
    for (table,) in cursor.fetchall():
        cursor.execute('SELECT * FROM `%s`' % table.replace('`', '``'))
        state[table] = sorted(cursor.fetchall(), key=lambda row: tuple((v is not None, str(v)) for v in row))
    return state


def run_write(database, sql):
    """Runs a write statement on `database`'s writable copy inside a transaction that is always rolled back, and
    returns (before, after): every table's rows before and after it. Raises pymysql errors as they come."""
    conn = _writer_connect(writable_database(database))
    try:
        with conn.cursor() as cursor:
            before = _dump_tables(cursor, writable_database(database))
            cursor.execute(sql)
            after = _dump_tables(cursor, writable_database(database))
        return before, after
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
