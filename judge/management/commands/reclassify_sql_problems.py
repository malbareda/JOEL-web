import re

from django.core.management.base import BaseCommand
from django.db import transaction

from judge.models import Problem, ProblemType

# Problem types replaced by the finer-grained "SQL - ..." ones below.
OLD_TYPES = ('bdselects', 'bdinsertupdate')

# Position inside each of the 9 batches in problem_batches/sql/ (sql<db>NN): the batches were written with the
# same difficulty curve, so the topic of problem NN is the same in every database except for the exceptions below
# (which were read off the actual reference queries, e.g. the small single-table databases have no JOINs to practise).
DEFAULT_BY_POSITION = {
    1: 'sqlselbasic', 2: 'sqlselbasic', 3: 'sqlselbasic',
    4: 'sqlaggbasic',
    5: 'sqlagggroup', 6: 'sqlagggroup',
    7: 'sqljoinbasic', 8: 'sqljoincomplex', 9: 'sqljoincomplex',
    10: 'sqlmixed',
}
OVERRIDES = {
    ('employees', 7): 'sqlsubq', ('employees', 9): 'sqlselbasic',
    ('lastnames', 7): 'sqlsubq', ('lastnames', 9): 'sqlselbasic',
    ('groupbytest', 7): 'sqlmixed', ('groupbytest', 8): 'sqljoinbasic', ('groupbytest', 9): 'sqlsubq',
    ('knights', 9): 'sqlselbasic',
    ('miniwind', 9): 'sqlsubq',
}
BATCH_RE = re.compile(r'^sql(chinook|employees|groupbytest|hotel|knights|lastnames|miniwind|northwind|traders)(\d\d)$')

# Hand-made problems that predate the batches.
HAND_MADE = {
    'provasql': 'sqlselbasic', 'provasql2': 'sqlselbasic', 'sqlselects': 'sqlselbasic',
    'sqljoins': 'sqljoinbasic', 'sqlagregacions': 'sqlagggroup', 'sqldificil': 'sqlmixed',
    'sqlinsertchinook': 'sqlinsert', 'sqlinsertemployees': 'sqlinsert', 'sqlinsertknights': 'sqlinsert',
    'sqlupdategroupby': 'sqlupdate', 'sqlupdatehotel': 'sqlupdate', 'sqlupdatetraders': 'sqlupdate',
}


def new_type_for(code):
    if code in HAND_MADE:
        return HAND_MADE[code]
    match = BATCH_RE.match(code)
    if match:
        db, position = match.group(1), int(match.group(2))
        return OVERRIDES.get((db, position)) or DEFAULT_BY_POSITION[position]
    return None


class Command(BaseCommand):
    help = ('Replace the old "BD - Selects" / "BD - Inserts i Updates" problem types by the finer "SQL - ..." '
            'ones. Problems of other types (Mongo, programming...) are not touched. Problems created by '
            'create_db_problems already come with their own type and are left alone.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='print the plan and change nothing')
        parser.add_argument('--delete-old-types', action='store_true',
                            help='afterwards delete the old types if no problem uses them any more')

    def handle(self, *args, **options):
        new_types = {t.name: t for t in ProblemType.objects.filter(name__startswith='sql')}
        plan = []
        unmapped = []
        for problem in Problem.objects.filter(types__name__in=OLD_TYPES).distinct().order_by('code'):
            target = new_type_for(problem.code)
            if target is None:
                unmapped.append(problem.code)
            elif target not in new_types:
                raise SystemExit('type "%s" does not exist; create it first' % target)
            else:
                plan.append((problem, target))
        counts = {}
        for _problem, target in plan:
            counts[target] = counts.get(target, 0) + 1
        for name, n in sorted(counts.items()):
            self.stdout.write('%4d  %s (%s)' % (n, new_types[name].full_name, name))
        if unmapped:
            self.stderr.write('NOT CLASSIFIED (left with their old type): %s' % ', '.join(unmapped))
        if options['dry_run']:
            self.stdout.write('dry run: %d problems would change, nothing changed' % len(plan))
            return
        with transaction.atomic():
            for problem, target in plan:
                keep = [t for t in problem.types.all() if t.name not in OLD_TYPES]
                problem.types.set(keep + [new_types[target]])
        self.stdout.write('%d problems reclassified' % len(plan))
        if options['delete_old_types']:
            for name in OLD_TYPES:
                old = ProblemType.objects.filter(name=name).first()
                if old is None:
                    continue
                remaining = old.problem_set.count()
                if remaining:
                    self.stderr.write('not deleting "%s": %d problems still use it' % (name, remaining))
                else:
                    old.delete()
                    self.stdout.write('deleted empty type "%s"' % name)
