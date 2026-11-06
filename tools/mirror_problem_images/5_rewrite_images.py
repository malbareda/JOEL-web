"""Point problem statements at the self-hosted copies of their images.

usage: rewrite_images.py <manifest.json> [--apply]
Without --apply: dry run (prints what would change, writes nothing).
With --apply:   1) writes a JSON backup of every text it will change (outside /tmp),
                2) updates Problem.description and ProblemTranslation.description (only the image URL
                   inside <img src="..."> or ![](...) changes),
                3) calls judge.signals.problem_update for each touched problem (fragment cache + PDFs).
Per-problem overrides use manifest keys "override:<problem code>:<original url>".
"""
import collections, datetime, json, os, re, sys
sys.path.insert(0, '/home/ubuntu/educational-online-judge')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')
import django
django.setup()
from django.db import transaction
from judge.models import Problem, ProblemTranslation
from judge.signals import problem_update

manifest = json.load(open(sys.argv[1]))
APPLY = '--apply' in sys.argv
BASE = 'https://jo-el.es/media/problem-images/'
HTML = re.compile(r'''(<img\b[^>]*?\bsrc\s*=\s*)(["'])(.*?)\2''', re.I | re.S)
MD = re.compile(r'(!\[[^\]]*\]\(\s*)([^)\s]+)')


def rewrite(code, text):
    """returns (new_text, replaced, unresolved_urls)"""
    replaced, unresolved = 0, []

    def pick(url):
        u = url.strip()
        m = manifest.get('override:%s:%s' % (code, u)) or manifest.get(u)
        return BASE + m['file'] if m else None

    def h(m):
        nonlocal replaced
        new = pick(m.group(3))
        if new is None:
            if m.group(3).strip() and not m.group(3).strip().startswith(('data:', BASE)):
                unresolved.append(m.group(3).strip())
            return m.group(0)
        replaced += 1
        return m.group(1) + m.group(2) + new + m.group(2)

    def md(m):
        nonlocal replaced
        new = pick(m.group(2))
        if new is None:
            if not m.group(2).startswith(('data:', BASE)):
                unresolved.append(m.group(2))
            return m.group(0)
        replaced += 1
        return m.group(1) + new

    out = HTML.sub(h, text or '')
    out = MD.sub(md, out)
    return out, replaced, unresolved


changes = []     # (kind, pk, code, old, new)
total_replaced, unres = 0, collections.Counter()
for p in Problem.objects.all().only('id', 'code', 'description'):
    new, n, un = rewrite(p.code, p.description)
    unres.update(un)
    if n and new != p.description:
        changes.append(('problem', p.pk, p.code, p.description, new)); total_replaced += n
for t in ProblemTranslation.objects.select_related('problem').only('id', 'language', 'description', 'problem__code', 'problem__id'):
    new, n, un = rewrite(t.problem.code, t.description)
    unres.update(un)
    if n and new != t.description:
        changes.append(('ptrans', t.pk, t.problem.code + ':' + t.language, t.description, new)); total_replaced += n

touched_problems = {c[2].split(':')[0] for c in changes}
print('texts to change: %d (problems %d, translations %d) | image refs replaced: %d | distinct problems touched: %d'
      % (len(changes), sum(c[0] == 'problem' for c in changes), sum(c[0] == 'ptrans' for c in changes),
         total_replaced, len(touched_problems)))
print('refs left unresolved (distinct urls %d, occurrences %d)' % (len(unres), sum(unres.values())))

if not APPLY:
    print('DRY RUN - nothing written')
    sys.exit(0)

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = '/home/ubuntu/joel-media/backup-descriptions-%s.json' % stamp
json.dump([{'kind': k, 'pk': pk, 'code': code, 'old': old} for k, pk, code, old, new in changes],
          open(backup, 'w'), ensure_ascii=False)
print('backup written:', backup, os.path.getsize(backup), 'bytes')

with transaction.atomic():
    for kind, pk, code, old, new in changes:
        if kind == 'problem':
            assert Problem.objects.filter(pk=pk, description=old).update(description=new) == 1, (kind, pk)
        else:
            assert ProblemTranslation.objects.filter(pk=pk, description=old).update(description=new) == 1, (kind, pk)
for code in sorted(touched_problems):
    problem_update(Problem, Problem.objects.get(code=code))
print('applied; cache cleared for', len(touched_problems), 'problems')
