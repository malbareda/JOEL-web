import os, sys, re, json, collections
sys.path.insert(0, '/home/ubuntu/educational-online-judge')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')
import django
django.setup()
from judge.models import Problem, ProblemTranslation
from judge.models import ProblemTask
try:
    from judge.models import ProblemTaskTranslation
except Exception:
    ProblemTaskTranslation = None

IMG_HTML = re.compile(r'<img\b[^>]*>', re.I | re.S)
IMG_MD = re.compile(r'!\[[^\]]*\]\(([^)\s]+)[^)]*\)')
SRC = re.compile(r'''src\s*=\s*["']?([^"'\s>]+)''', re.I)

rows = []   # (kind, owner id/code, field, url, tag)
def scan(kind, owner, text, field='description'):
    for m in IMG_HTML.finditer(text or ''):
        tag = m.group(0)
        s = SRC.search(tag)
        rows.append((kind, owner, field, s.group(1) if s else None, tag))
    for m in IMG_MD.finditer(text or ''):
        rows.append((kind, owner, field, m.group(1), m.group(0)))

for p in Problem.objects.all().only('id', 'code', 'description'):
    scan('problem', p.code, p.description)
for t in ProblemTranslation.objects.select_related('problem').only('language', 'description', 'problem__code'):
    scan('ptrans:' + t.language, t.problem.code, t.description)
print('tasks model:', ProblemTask, 'fields:', [f.name for f in ProblemTask._meta.fields])
for t in ProblemTask.objects.all():
    for f in ('description', 'about'):
        if hasattr(t, f):
            scan('task', t.name, getattr(t, f), f)
if ProblemTaskTranslation:
    print('tasktrans fields:', [f.name for f in ProblemTaskTranslation._meta.fields])
    for t in ProblemTaskTranslation.objects.all():
        for f in [f.name for f in ProblemTaskTranslation._meta.fields if f.get_internal_type() == 'TextField']:
            scan('ttrans:' + t.language, t.task_id, getattr(t, f) or '', f)

print('total img refs:', len(rows))
c = collections.Counter(r[0] for r in rows)
print(c)
def host(u):
    if not u: return '(none)'
    if u.startswith('data:'): return 'data:'
    m = re.match(r'(?:https?:)?//([^/]+)', u)
    return m.group(1) if m else 'relative:' + u.split('/')[1] if u.startswith('/') else 'relative'
h = collections.Counter(host(r[3]) for r in rows)
for k, v in h.most_common(40): print(v, k)
uniq = sorted({r[3] for r in rows if r[3]})
print('unique urls:', len(uniq))
json.dump(rows, open(os.path.join(os.environ.get('WORK', '.'), 'img_rows.json'), 'w'), ensure_ascii=False)
