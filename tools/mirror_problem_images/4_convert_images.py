"""Turn downloaded (untrusted) images into small, re-encoded, content-addressed files.

usage: python -I convert_images.py <img_rows.json> <out_dir> <manifest.json> <dl_out_1.json> [<dl_out_2.json> ...]

* Only files PIL itself can decode are accepted; the output is always freshly encoded by PIL
  (so EXIF/ICC/comments and anything odd inside the container are dropped).
* Never upscales. Target box = 2x the widest width the problem statements display it at
  (width="..." attribute or style width in px); if some use has no width, long side <= 800.
* Names are <sha256(bytes)[:20]>.<ext> -> immutable (nginx serves /media with `expires max`).
"""
import hashlib, io, json, os, re, sys
from PIL import Image, ImageOps

rows_path, out_dir, manifest_path = sys.argv[1:4]
dl_files = sys.argv[4:]
Image.MAX_IMAGE_PIXELS = 40_000_000
os.makedirs(out_dir, exist_ok=True)

rows = json.load(open(rows_path))
widths = {}      # url -> list of displayed widths (None when the tag gives none)
for kind, owner, field, url, tag in rows:
    if not url:
        continue
    w = None
    m = re.search(r'''\bwidth\s*=\s*["']?(\d+)''', tag, re.I)
    if m:
        w = int(m.group(1))
    else:
        m = re.search(r'width\s*:\s*(\d+)\s*px', tag, re.I)
        if m:
            w = int(m.group(1))
    widths.setdefault(url, []).append(w)


def target_box(url):
    url = re.sub(r'^override:[^:]+:', '', url)          # per-problem override keys: override:<code>:<url>
    ws = widths.get(url.strip(), widths.get(url, [None]))
    if not ws or any(w is None for w in ws):
        return 800, 800
    mw = min(max(ws) * 2, 1000)
    return max(mw, 160), 1000


def has_alpha(im):
    if im.mode in ('RGBA', 'LA'):
        return im.getchannel('A').getextrema()[0] < 255
    if im.mode == 'P' and 'transparency' in im.info:
        return True
    return False


def encode(im, src_fmt):
    """returns (bytes, ext)"""
    alpha = has_alpha(im)
    if alpha:
        im = im.convert('RGBA')
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
        return buf.getvalue(), 'png'
    rgb = im.convert('RGB')
    if src_fmt == 'JPEG':
        buf = io.BytesIO(); rgb.save(buf, 'JPEG', quality=85, optimize=True, progressive=True)
        return buf.getvalue(), 'jpg'
    pbuf = io.BytesIO(); rgb.save(pbuf, 'PNG', optimize=True)
    if len(pbuf.getvalue()) > 250_000:
        jbuf = io.BytesIO(); rgb.save(jbuf, 'JPEG', quality=88, optimize=True, progressive=True)
        if len(jbuf.getvalue()) < 0.6 * len(pbuf.getvalue()):
            return jbuf.getvalue(), 'jpg'
    return pbuf.getvalue(), 'png'


manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
FORCE = set(json.load(open(os.environ['FORCE_URLS']))) if os.environ.get('FORCE_URLS') else set()
report = {'ok': 0, 'skipped': []}
for dl in dl_files:
    for rec in json.load(open(dl)):
        url, path = rec['url'], rec['file']
        if not path or (url in manifest and url not in FORCE):
            continue
        try:
            raw = open(path, 'rb').read()
            im = Image.open(io.BytesIO(raw))
            src_fmt = im.format
            if src_fmt not in ('JPEG', 'PNG', 'GIF', 'WEBP', 'BMP'):
                raise ValueError('format ' + str(src_fmt))
            animated = getattr(im, 'n_frames', 1) > 1
            if animated and src_fmt == 'GIF':
                # keep animated GIFs byte-for-byte (verified decodable below), if small enough
                if len(raw) > 3_000_000:
                    im.seek(0); animated = False      # too big: use first frame as a still
                else:
                    im.verify()
                    name = hashlib.sha256(raw).hexdigest()[:20] + '.gif'
                    with open(os.path.join(out_dir, name), 'wb') as f:
                        f.write(raw)
                    manifest[url] = {'file': name, 'w': im.size[0], 'h': im.size[1], 'bytes': len(raw),
                                     'orig_bytes': len(raw), 'src': 'GIF(animated)', 'from': rec['final']}
                    report['ok'] += 1
                    continue
            im.load()
            im = ImageOps.exif_transpose(im)
            if im.size[0] < 8 or im.size[1] < 8:
                raise ValueError('tiny image %s' % (im.size,))
            if im.mode == 'P':
                im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')
            elif im.mode in ('CMYK', 'I', 'I;16', 'F', 'L', 'LA', '1'):
                im = im.convert('RGBA' if im.mode == 'LA' else 'RGB')
            bw, bh = target_box(url)
            if im.size[0] > bw or im.size[1] > bh:
                im.thumbnail((bw, bh), Image.LANCZOS)
            data, ext = encode(im, src_fmt)
            name = hashlib.sha256(data).hexdigest()[:20] + '.' + ext
            with open(os.path.join(out_dir, name), 'wb') as f:
                f.write(data)
            manifest[url] = {'file': name, 'w': im.size[0], 'h': im.size[1], 'bytes': len(data),
                             'orig_bytes': len(raw), 'src': src_fmt, 'from': rec['final']}
            report['ok'] += 1
        except Exception as e:
            report['skipped'].append({'url': url, 'why': type(e).__name__ + ': ' + str(e)[:100]})

json.dump(manifest, open(manifest_path, 'w'), indent=1, ensure_ascii=False)
print('converted', report['ok'], '| skipped', len(report['skipped']))
for s in report['skipped']:
    print('  SKIP', s['why'][:60], '|', s['url'][:90])
tot = sum(m['bytes'] for m in manifest.values())
orig = sum(m['orig_bytes'] for m in manifest.values())
print('manifest entries', len(manifest), '| total %.1f MB (was %.1f MB)' % (tot / 1e6, orig / 1e6))
