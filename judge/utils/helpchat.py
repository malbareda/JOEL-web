"""
Help chat ("No sé ni per on començar") for the very first problems: the student talks with the AI of the
joel-pistes service (`POST /xat`, same key and base URL as the superhints; see importacions/PROTOCOL.md).

The service keeps nothing, so every turn sends the problem, its test cases, the student's last submission and the
whole conversation so far; its answer is stored as the next JOEL message. Only problems with
`ProblemData.help_chat` turned on have the button, and never inside a contest.
"""
import html
import re
from zipfile import BadZipfile, ZipFile

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.safestring import mark_safe

from judge.models import HelpChatMessage, Submission
from judge.utils.superhints import HINTABLE_VERDICTS, PROTOCOL_VERSION, SuperHintError, ask, is_configured

MAX_CASES = 10
MAX_FIELD = 3000
MAX_MESSAGES_SENT = 100
# Verdicts the service accepts for the student's last submission; AC is fine here, unlike for a hint.
CHAT_VERDICTS = ('AC',) + HINTABLE_VERDICTS


def xat_url():
    return getattr(settings, 'JOEL_XAT_URL', None) or settings.JOEL_PISTES_URL.rsplit('/', 1)[0] + '/xat'


def max_student_messages():
    return getattr(settings, 'HELP_CHAT_MAX_MESSAGES', 20)


def max_message_length():
    return getattr(settings, 'HELP_CHAT_MAX_LENGTH', 1000)


def is_enabled(problem):
    """Whether `problem` has the chat turned on and the service is set up."""
    if not is_configured():
        return False
    try:
        return bool(problem.data_files.help_chat)
    except ObjectDoesNotExist:
        return False


def statement(problem, language):
    """The statement the student reads: its translation into their language, if there is one."""
    translation = problem.translations.filter(language=language).first()
    return translation.description if translation is not None else problem.description


_TAG = re.compile(r'<[^>]*>')


def _lines(text):
    """The non-empty lines of `text`, trimmed and without HTML tags, so that an example written as a table row
    (`<td>1991</td>` / `<td>nah</td>`) compares equal to the case file's lines."""
    lines = (_TAG.sub('', line).strip() for line in (text or '').replace('\r\n', '\n').split('\n'))
    return [line for line in lines if line]


def _contains_block(haystack, needle):
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def _read(zipfile, name):
    """Text of `name` in the data zip: '' for a blank name, None if the file is not there."""
    if not name:
        return ''
    try:
        return zipfile.read(name).decode('utf-8', errors='replace')
    except KeyError:
        return None


def test_cases(problem, statement_text):
    """The problem's cases, whole (input and output files), for the service. A case is `public` (the AI may show its
    output) only when its input and output are printed one right after the other in the statement, as an example
    row; the rest are private, which the service uses to understand the problem without giving their output
    away. When in doubt, private."""
    data = problem.data_files
    if not data.zipfile:
        return []
    haystack = _lines(statement_text) + ['\0'] + _lines(problem.description)
    out = []
    try:
        with ZipFile(data.zipfile.path) as z:
            for case in problem.cases.filter(type='C').order_by('order')[:MAX_CASES]:
                entrada, sortida = _read(z, case.input_file), _read(z, case.output_file)
                if entrada is None or sortida is None:
                    continue
                in_lines, out_lines = _lines(entrada), _lines(sortida)
                public = bool(out_lines) and _contains_block(haystack, in_lines + out_lines)
                if public and not in_lines and sum(len(line) for line in out_lines) < 8:
                    public = False  # a tiny output ("3", "OK") shows up in any statement
                out.append({'entrada': entrada[:MAX_FIELD], 'sortida': sortida[:MAX_FIELD], 'public': public})
    except (BadZipfile, OSError, ValueError):
        return []
    return out


def last_submission(profile, problem):
    """The student's latest submission on `problem` as the service wants it: just the language if they have not
    submitted yet; otherwise also their code and, once judged, the verdict and the compiler's message."""
    submission = (Submission.objects.filter(user=profile, problem=problem).select_related('language', 'source')
                  .order_by('-id').first())
    if submission is None:
        return {'llenguatge': getattr(profile.language, 'key', None) or 'PY3'}
    data = {'llenguatge': submission.language.key, 'codi': submission.source.source}
    if submission.status in ('D', 'CE', 'IE') and submission.result in CHAT_VERDICTS:
        data['veredicte'] = submission.result
    if submission.error:
        data['missatge_error'] = submission.error[:MAX_FIELD]
    return data


def build_request(reply):
    """The `/xat` request for the JOEL reply row `reply` (pending): everything the student said and the AI answered
    before it, ending with the student's new message."""
    profile, problem = reply.user, reply.problem
    text = statement(problem, reply.language)
    history = list(HelpChatMessage.conversation(profile, problem).filter(status=HelpChatMessage.OK, id__lt=reply.id))
    if not history or history[-1].role != HelpChatMessage.STUDENT:
        raise SuperHintError('la conversa no acaba amb un missatge de l\'alumne')
    return {
        'versio_protocol': PROTOCOL_VERSION,
        'id_peticio': 'xat-%d' % reply.id,
        'idioma': reply.language,
        'problema': {
            'codi': problem.code,
            'titol': problem.name,
            'enunciat': text,
            'categoria': problem.group.full_name if problem.group_id else None,
            'punts': problem.points,
        },
        'casos_prova': test_cases(problem, text),
        'enviament': last_submission(profile, problem),
        'missatges': [{'rol': 'alumne' if m.role == HelpChatMessage.STUDENT else 'joel', 'text': m.text}
                      for m in history][-MAX_MESSAGES_SENT:],
    }


def ask_reply(reply):
    """Asks the service for the answer to `reply` and returns its body (`missatge`, `revisio`, ...)."""
    return ask(build_request(reply), url=xat_url(), answer_field='missatge')


_CODE_BLOCK = re.compile(r'```[^\n`]*\n?(.*?)```', re.S)
_INLINE_CODE = re.compile(r'`([^`\n]+)`')
_BOLD = re.compile(r'\*\*([^*\n]+)\*\*')


def render_text(text):
    """The model's simple Markdown (inline code, a short code block, bold) as HTML. Everything else, including
    any HTML in the text, is escaped, so the page never shows markup the student or the model typed."""
    escaped = html.escape((text or '').replace('\0', ''), quote=False)
    blocks = []

    def keep_block(match):
        blocks.append('<pre><code>%s</code></pre>' % match.group(1).strip('\n'))
        return '\0%d\0' % (len(blocks) - 1)

    escaped = _CODE_BLOCK.sub(keep_block, escaped)
    escaped = _INLINE_CODE.sub(r'<code>\1</code>', escaped)
    escaped = _BOLD.sub(r'<strong>\1</strong>', escaped)
    escaped = escaped.replace('\n', '<br>')
    for i, block in enumerate(blocks):
        escaped = escaped.replace('\0%d\0' % i, block)
    return mark_safe(escaped)
