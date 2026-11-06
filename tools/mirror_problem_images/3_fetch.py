"""Download images into a NEW staging dir (untrusted bytes: saved, never opened or executed here).

usage: fetch2.py <jobs.json> <staging_dir> <out_json>
jobs.json: [{"url": <original url as stored in the DB>, "fetch": <url to actually GET>, "ref": true|false}]
Polite: one request at a time (with a pause) to rate-limited hosts, Retry-After honoured on 429.
"""
import json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests

jobs_path, staging, out_json = sys.argv[1:4]
os.makedirs(staging, exist_ok=False)
UA_BROWSER = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/124.0 Safari/537.36')
UA_BOT = 'JOEL-image-mirror/1.0 (educational judge; self-hosting images of its own problem statements)'
MAX_BYTES = 25 * 1024 * 1024
STRICT = {'i.imgur.com': 1.5, 'i.ibb.co': 1.5, 'upload.wikimedia.org': 1.0, 'web.archive.org': 4.0,
          'commons.wikimedia.org': 1.0, 'www.dropbox.com': 0.3}

jobs = json.load(open(jobs_path))
locks, lock_g = {}, threading.Lock()
last = {}


def host_of(u):
    m = re.match(r'https?://([^/]+)', u)
    return m.group(1) if m else 'x'


def gate(host):
    with lock_g:
        lk = locks.setdefault(host, threading.Semaphore(1 if host in STRICT else 2))
    return lk


def pause(host):
    gap = STRICT.get(host)
    if gap:
        with lock_g:
            wait = last.get(host, 0) + gap - time.time()
            last[host] = max(time.time(), last.get(host, 0) + gap)
        if wait > 0:
            time.sleep(wait)


def one(args):
    i, job = args
    url = job['url']
    full = job.get('fetch') or url
    full = urljoin('https://jo-el.es/', full.strip())
    host = host_of(full)
    ua = UA_BOT if host in ('upload.wikimedia.org', 'commons.wikimedia.org', 'web.archive.org') else UA_BROWSER
    # No avif/webp in Accept: CDNs then send png/jpeg/gif, which PIL 7.2 here can decode.
    headers = {'User-Agent': ua, 'Accept': 'image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.5'}
    if job.get('ref'):
        headers['Referer'] = 'https://jo-el.es/'
    path = os.path.join(staging, '%d.bin' % i)
    err, status, n, ctype, final = None, None, 0, '', full
    for attempt in range(1, 5):
        try:
            with gate(host):
                pause(host)
                r = requests.get(full, headers=headers, timeout=(8, 25), stream=True, allow_redirects=True)
                status, ctype, final = r.status_code, r.headers.get('Content-Type', ''), r.url
                if status in (429, 503):
                    ra = r.headers.get('Retry-After', '')
                    r.close()
                    time.sleep(min(int(ra) if ra.isdigit() else 8 * attempt, 60))
                    continue
                n = 0
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(65536):
                        n += len(chunk)
                        if n > MAX_BYTES:
                            raise ValueError('too big')
                        f.write(chunk)
                r.close()
            err = None
            break
        except Exception as e:
            err = type(e).__name__ + ': ' + str(e)[:120]
            if attempt >= 2:
                break
            time.sleep(3)
    ok = status == 200 and err is None and n > 0
    return {'url': url, 'fetch': full, 'file': path if ok else None, 'status': status, 'bytes': n,
            'ctype': ctype, 'final': final, 'err': err}


t0 = time.time()
out = []
with ThreadPoolExecutor(max_workers=10) as ex:
    for k, res in enumerate(ex.map(one, enumerate(jobs)), 1):
        out.append(res)
        if k % 25 == 0:
            print(k, '/', len(jobs), round(time.time() - t0), 's', flush=True)
json.dump(out, open(out_json, 'w'), ensure_ascii=False, indent=1)
print('DONE', len(out), 'ok', sum(1 for o in out if o['file']), round(time.time() - t0), 's')
