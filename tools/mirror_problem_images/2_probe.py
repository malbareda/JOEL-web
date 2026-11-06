"""Probe every image URL (read-only: headers + first bytes, nothing saved).

Two passes per URL, to tell "broken for the student" from "broken only for hotlinkers":
  user  = as a student's browser would load it from jo-el.es (browser UA + Referer)
  plain = browser UA, no Referer (only tried if the user-style request failed)
"""
import json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests

SP = os.environ.get('WORK', '.').rstrip('/') + '/'
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0 Safari/537.36')
rows = json.load(open(SP + 'img_rows.json'))
urls = sorted({r[3] for r in rows if r[3] and not r[3].startswith('data:')})

host_sem = {}
host_lock = threading.Lock()


def sem_for(url):
    h = re.match(r'(?:https?:)?//([^/]+)', url)
    h = h.group(1) if h else 'local'
    with host_lock:
        return host_sem.setdefault(h, threading.Semaphore(2))


def sniff(b):
    if b[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if b[:3] == b'\xff\xd8\xff': return 'jpeg'
    if b[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP': return 'webp'
    if b[:2] == b'BM': return 'bmp'
    if b.lstrip()[:5].lower() in (b'<?xml', b'<svg ') or b'<svg' in b[:300].lower(): return 'svg'
    if b[:15].lower().startswith(b'<!doctype html') or b[:6].lower().startswith(b'<html'): return 'html'
    if b[4:12] in (b'ftypavif', b'ftypavis'): return 'avif'
    return 'other'


def fetch(url, referer):
    full = urljoin('https://jo-el.es/', url)
    if full.startswith('//'):
        full = 'https:' + full
    headers = {'User-Agent': UA, 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'}
    if referer:
        headers['Referer'] = 'https://jo-el.es/'
    try:
        with sem_for(full):
            r = requests.get(full, headers=headers, timeout=(8, 20), stream=True, allow_redirects=True)
            head = next(r.iter_content(2048), b'')
            r.close()
        return {'status': r.status_code, 'ctype': r.headers.get('Content-Type', ''),
                'clen': r.headers.get('Content-Length'), 'final': r.url, 'kind': sniff(head), 'err': None}
    except Exception as e:  # network / TLS / timeout
        return {'status': None, 'ctype': '', 'clen': None, 'final': full, 'kind': None,
                'err': type(e).__name__ + ': ' + str(e)[:120]}


def ok(res):
    return res['status'] == 200 and res['kind'] in ('png', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'avif')


def probe(url):
    user = fetch(url, True)
    out = {'url': url, 'user': user, 'user_ok': ok(user)}
    if not out['user_ok']:
        plain = fetch(url, False)
        out['plain'] = plain
        out['plain_ok'] = ok(plain)
    return out


t0 = time.time()
results = []
with ThreadPoolExecutor(max_workers=12) as ex:
    for i, res in enumerate(ex.map(probe, urls), 1):
        results.append(res)
        if i % 50 == 0:
            print(i, '/', len(urls), round(time.time() - t0), 's', flush=True)
json.dump(results, open(SP + 'probe.json', 'w'), ensure_ascii=False, indent=1)
print('DONE', len(results), round(time.time() - t0), 's')
