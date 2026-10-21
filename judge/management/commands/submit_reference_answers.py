import time
from zipfile import ZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from judge.models import Language, Problem, Profile, Submission, SubmissionSource

AUTHOR = 'edgar'
FINAL_STATUSES = ('D', 'IE', 'CE', 'AB')


def reference_source(problem):
    """The submission text answering every question with the reference query stored in the problem's data zip,
    in the same `-- @@Q<n>@@` format the web submission form produces."""
    data = problem.data_files
    if not data.zipfile:
        raise CommandError('%s: has no data zip' % problem.code)
    parts = []
    with ZipFile(data.zipfile.path) as z:
        for n, case in enumerate(problem.cases.filter(type='C').order_by('order'), 1):
            parts.append('-- @@Q%d@@\n%s\n' % (n, z.read(case.output_file).decode('utf-8').strip()))
    return ''.join(parts)


class Command(BaseCommand):
    help = ('Submit the correct answer of each SQL problem as %s, judged by the real judge, so teachers can see '
            'the reference solution as an AC submission. Problems where %s already has a full-score AC are '
            'skipped.' % (AUTHOR, AUTHOR))

    def add_arguments(self, parser):
        parser.add_argument('codes', nargs='*', help='problem codes (default: every problem of a "SQL - ..." type)')
        parser.add_argument('--chunk', type=int, default=20, help='submissions sent to the judges at a time')
        parser.add_argument('--timeout', type=int, default=300, help='seconds to wait for each chunk')
        parser.add_argument('--dry-run', action='store_true', help='only list what would be submitted')

    def handle(self, *args, **options):
        if options['codes']:
            problems = list(Problem.objects.filter(code__in=options['codes']).order_by('code'))
            missing = set(options['codes']) - {p.code for p in problems}
            if missing:
                raise CommandError('unknown problem(s): %s' % ', '.join(sorted(missing)))
        else:
            problems = list(Problem.objects.filter(types__full_name__startswith='SQL - ').distinct().order_by('code'))
        author = Profile.objects.get(user__username=AUTHOR)
        language = Language.objects.get(key='TEXT')

        todo = []
        for problem in problems:
            # Same condition Submission.can_see_detail uses to say "solved": AC with the problem's full points.
            if Submission.objects.filter(user=author, problem=problem, result='AC',
                                         points=problem.points).exists():
                continue
            todo.append(problem)
        self.stdout.write('%d problems, %d already have an AC by %s, %d to submit' %
                          (len(problems), len(problems) - len(todo), AUTHOR, len(todo)))
        if options['dry_run']:
            return

        failed = []
        for start in range(0, len(todo), options['chunk']):
            subs = []
            for problem in todo[start:start + options['chunk']]:
                sub = Submission.objects.create(user=author, problem=problem, language=language)
                SubmissionSource.objects.create(submission=sub, source=reference_source(problem))
                sub.judge()
                subs.append(sub)
            deadline = time.time() + options['timeout']
            while time.time() < deadline:
                time.sleep(3)
                for sub in subs:
                    sub.refresh_from_db()
                if all(sub.status in FINAL_STATUSES for sub in subs):
                    break
            for sub in subs:
                ok = sub.status == 'D' and sub.result == 'AC' and sub.points == sub.problem.points
                if not ok:
                    failed.append(sub)
                    self.stderr.write('  NOT AC: %s (#%d) status=%s result=%s points=%s/%s' %
                                      (sub.problem.code, sub.id, sub.status, sub.result, sub.points,
                                       sub.problem.points))
            self.stdout.write('  %d/%d submitted, %d not AC so far' %
                              (min(start + options['chunk'], len(todo)), len(todo), len(failed)))
        if failed:
            raise CommandError('%d submissions did not get a full AC (they were kept for inspection)' % len(failed))
        self.stdout.write('all %d reference submissions are AC' % len(todo))
