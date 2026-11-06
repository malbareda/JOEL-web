"""Shrinks the picture an author uploads as the "problem image".

The statement shows it at most 300 px wide, so a bigger original is wasted bandwidth. The upload is
re-encoded here (admin form `clean_image`) with these rules:

* longest side at most `MAX_SIDE` px (twice the displayed size, for high-density screens), never upscaled;
* the EXIF rotation is applied and all metadata (GPS, camera...) is dropped;
* the smaller of PNG and JPEG is kept (PNG for diagrams / transparency, JPEG for photos);
* animated GIFs are kept as they are (re-encoding would drop the animation), but with a size limit;
* the file gets a content-hash name, never the name the author's computer used.
"""
import hashlib
import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

__all__ = ['shrink_problem_image', 'MAX_SIDE']

MAX_SIDE = 600
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_ANIMATED_BYTES = 2 * 1024 * 1024
ALLOWED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}


def _has_alpha(im):
    return im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)


def shrink_problem_image(upload):
    """`upload` is a Django UploadedFile. Returns an InMemoryUploadedFile with the shrunk picture,
    or raises ValidationError if it is not an image we accept."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(_('The image is too big (%(mb)d MB maximum).') % {'mb': MAX_UPLOAD_BYTES // 2 ** 20})
    try:
        upload.seek(0)
        raw = upload.read()
        im = Image.open(io.BytesIO(raw))
        fmt = im.format
        im.load()
    except Exception:
        raise ValidationError(_('This file is not a valid image.'))
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(_('Only JPEG, PNG, GIF and WebP images are accepted.'))

    animated = getattr(im, 'n_frames', 1) > 1
    if animated:
        if len(raw) > MAX_ANIMATED_BYTES:
            raise ValidationError(_('The animated image is too big (%(mb)d MB maximum).')
                                  % {'mb': MAX_ANIMATED_BYTES // 2 ** 20})
        data, ext, ctype = raw, ('gif' if fmt == 'GIF' else fmt.lower()), 'image/' + fmt.lower()
    else:
        im = ImageOps.exif_transpose(im)
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        candidates = []
        png = io.BytesIO()
        (im if im.mode in ('RGB', 'RGBA', 'L', 'LA', 'P') else im.convert('RGBA')).save(png, 'PNG', optimize=True)
        candidates.append((png.getvalue(), 'png', 'image/png'))
        if not _has_alpha(im):
            jpg = io.BytesIO()
            im.convert('RGB').save(jpg, 'JPEG', quality=85, optimize=True)
            candidates.append((jpg.getvalue(), 'jpg', 'image/jpeg'))
        data, ext, ctype = min(candidates, key=lambda c: len(c[0]))

    name = '%s.%s' % (hashlib.sha256(data).hexdigest()[:20], ext)
    return InMemoryUploadedFile(io.BytesIO(data), 'image', name, ctype, len(data), None)
