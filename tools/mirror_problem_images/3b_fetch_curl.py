"""Same contract as fetch2.py but using curl (different TLS stack). usage: fetch_curl.py jobs.json staging out.json"""
import json, os, subprocess, sys
jobs_path, staging, out_json = sys.argv[1:4]
os.makedirs(staging, exist_ok=False)
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
out = []
for i, job in enumerate(json.load(open(jobs_path))):
    url = job['url']; full = job.get('fetch') or url
    path = os.path.join(staging, '%d.bin' % i)
    cmd = ['curl', '-sS', '-L', '-m', '30', '--max-filesize', '26000000', '-A', UA,
           '-H', 'Accept: image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.5',
           '-o', path, '-w', '%{http_code}|%{content_type}|%{url_effective}', full]
    if job.get('ref'):
        cmd[1:1] = ['-e', 'https://jo-el.es/']
    r = subprocess.run(cmd, capture_output=True, text=True)
    code, ctype, final = (r.stdout.split('|', 2) + ['', '', ''])[:3]
    ok = r.returncode == 0 and code == '200' and os.path.exists(path) and os.path.getsize(path) > 0
    out.append({'url': url, 'fetch': full, 'file': path if ok else None, 'status': int(code) if code.isdigit() else None,
                'bytes': os.path.getsize(path) if os.path.exists(path) else 0, 'ctype': ctype, 'final': final,
                'err': None if ok else (r.stderr.strip()[:100] or 'http ' + code)})
json.dump(out, open(out_json, 'w'), ensure_ascii=False, indent=1)
for o in out: print('OK ' if o['file'] else 'NO ', o['status'], (o['err'] or '')[:45], '|', o['url'][:80])
