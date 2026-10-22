import time

from django.core.management.base import BaseCommand, CommandError

from judge.utils import mysql_grader


class Command(BaseCommand):
    help = ('Load a catalog database on the MariaDB grading server (the "mysql" checker) from one or more SQL dumps, '
            'replacing it if it already exists, together with its writable copy w_<name> for write questions. '
            'Any CREATE DATABASE / USE line in the dumps is ignored: everything goes into <name>.')

    def add_arguments(self, parser):
        parser.add_argument('name', help='database name on the grading server (e.g. hotel)')
        parser.add_argument('files', nargs='+', help='SQL dump file(s), loaded in this order as a single script')
        parser.add_argument('--copy-only', action='store_true',
                            help='only (re)load the writable copy w_<name>, leaving <name> as it is')

    def handle(self, *args, **options):
        name = options['name']
        if name.startswith(('p_', 'w_')):
            raise CommandError('p_* and w_* names are reserved for problems\' own databases and writable copies')
        text = '\n'.join(open(path, encoding='utf-8', errors='replace').read() for path in options['files'])
        targets = [mysql_grader.writable_database(name)] if options['copy_only'] else \
            [name, mysql_grader.writable_database(name)]
        for database in targets:
            start = time.time()
            try:
                mysql_grader.load_dump(text, database, admin=True)
            except mysql_grader.DumpError as e:
                raise CommandError('%s: %s' % (database, e))
            self.stdout.write('%s: loaded in %.1f s' % (database, time.time() - start))
        if not options['copy_only']:
            conn = mysql_grader._admin_connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("GRANT SELECT ON `%s`.* TO 'joel_grader'@'localhost'" % name)
            finally:
                conn.close()
            self.stdout.write('%s: SELECT granted to joel_grader' % name)
