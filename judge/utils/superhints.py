"""
Client for the joel-pistes service (protocol v1, see importacions/PROTOCOL.md): given a failing submission,
it answers with one hint written in JOEL's voice. Used by the superhint button on the submission page, which
only shows up on a test case whose classic hint the student has already seen.

The service keeps nothing, so the previous superhints of this student on this problem are sent along every
time (`pistes_anteriors`) and it goes one step further instead of repeating itself.
"""
import logging
import random
import re
import time

import requests
from django.conf import settings
from django.core.cache import cache

from judge.utils.hints import parse_linecount_all, parse_rstripped

logger = logging.getLogger('judge.superhints')

PROTOCOL_VERSION = '1'
# Verdicts the service accepts. With anything else (AC, SC, AB...) there is nothing to give a hint about.
HINTABLE_VERDICTS = ('WA', 'IR', 'RTE', 'TLE', 'MLE', 'OLE', 'CE', 'IE')
# The linecount checker writes this for a line that is missing on one side.
MISSING_LINE = '✗'
MAX_CASES = 5
SCORE_FEEDBACK = re.compile(r'^\s*[\d.,]+\s*%\s*$')
MAX_PREVIOUS = 10


class SuperHintError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def is_configured():
    return bool(getattr(settings, 'JOEL_PISTES_URL', None) and getattr(settings, 'JOEL_PISTES_KEY', None))


HEALTH_CACHE_KEY = 'superhints:health'
HEALTH_CACHE_SECONDS = 60


def health():
    """State of the service for the status page, from its `GET /salut` (no key needed). Cached for a minute so
    the status page does not ask on every visit. Returns a dict with `state` ('ok', 'down' or 'off'), plus
    `ping_ms`, `protocol` and `error` when they apply."""
    if not is_configured():
        return {'state': 'off'}
    result = cache.get(HEALTH_CACHE_KEY)
    if result is not None:
        return result

    url = settings.JOEL_PISTES_URL.rsplit('/', 1)[0] + '/salut'
    start = time.monotonic()
    try:
        response = requests.get(url, timeout=5)
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        result = {'state': 'down', 'error': str(e)[:200]}
    else:
        ping_ms = (time.monotonic() - start) * 1000
        if response.status_code == 200 and body.get('estat') == 'ok':
            result = {'state': 'ok', 'ping_ms': ping_ms, 'protocol': body.get('versio_protocol')}
        else:
            result = {'state': 'down', 'ping_ms': ping_ms, 'error': 'HTTP %d' % response.status_code}
    if result.get('protocol') not in (None, PROTOCOL_VERSION):
        result['error'] = 'protocol %s, JOEL speaks %s' % (result['protocol'], PROTOCOL_VERSION)
    cache.set(HEALTH_CACHE_KEY, result, HEALTH_CACHE_SECONDS)
    return result


def _missing(text):
    return '(cap línia)' if text == MISSING_LINE else text


def failed_cases(case, checker, caseformat):
    """The failing records of `case`, the one the student saw with the classic hint first."""
    feedback = case.extended_feedback
    if not feedback:
        return []
    if checker == 'rstripped':
        parsed = parse_rstripped(feedback)
        return [{'entrada': '', 'sortida_esperada': parsed['expected'], 'sortida_obtinguda': parsed['yours']}]
    if checker == 'linecount':
        out = []
        for record in parse_linecount_all(feedback, caseformat, limit=MAX_CASES)['records']:
            out.append({
                'entrada': '\n'.join(record['wrong_input_lines']),
                'sortida_esperada': _missing(record['expected']),
                'sortida_obtinguda': _missing(record['actual']),
            })
        return out
    return []


def verdict_of(submission, case):
    for verdict in (case.status if case is not None else None, submission.result):
        if verdict in HINTABLE_VERDICTS:
            return verdict
    return None


def build_request(superhint, previous_hints):
    submission = superhint.submission
    problem = submission.problem
    case = superhint.case
    data_files = problem.data_files

    # A case's feedback is either a score ("80%", useless here) or a short note such as "imprimeixes MÉS línies".
    case_note = case.feedback if case is not None and not SCORE_FEEDBACK.match(case.feedback or '') else None
    error_message = [msg for msg in (submission.error, case_note) if msg]
    cases = failed_cases(case, data_files.checker, data_files.caseformat) if case is not None else []
    if case is not None and case.status != submission.result:
        for failed in cases:
            failed['veredicte'] = case.status

    return {
        'versio_protocol': PROTOCOL_VERSION,
        'id_peticio': 'superpista-%d' % superhint.id,
        'idioma': superhint.language,
        'problema': {
            'codi': problem.code,
            'titol': problem.name,
            'enunciat': problem.description,
            'categoria': problem.group.full_name if problem.group_id else None,
            'punts': problem.points,
        },
        'enviament': {
            'llenguatge': submission.language.key,
            'codi': submission.source.source,
            'veredicte': verdict_of(submission, case),
            'missatge_error': '\n'.join(error_message) or None,
        },
        'casos_fallits': cases,
        'pistes_anteriors': list(previous_hints)[-MAX_PREVIOUS:],
    }


def ask(payload, url=None, answer_field='pista'):
    """Sends `payload` and returns the service's answer (a dict with `estat` == 'ok' and the text in
    `answer_field`: `pista` for /pista, `missatge` for /xat). Retries as the protocol says: a 429 up to 3 times
    after 5-10 s, a 502/504 (or a dropped connection) once."""
    headers = {'Authorization': 'Bearer %s' % settings.JOEL_PISTES_KEY}
    timeout = getattr(settings, 'JOEL_PISTES_TIMEOUT', 60)
    busy_retries, model_retries = 3, 1
    while True:
        try:
            response = requests.post(url or settings.JOEL_PISTES_URL, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            if model_retries:
                model_retries -= 1
                continue
            raise SuperHintError('connexió: %s' % e)

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code == 200 and body.get('estat') == 'ok' and body.get(answer_field):
            return body

        code = (body.get('error') or {}).get('codi')
        message = (body.get('error') or {}).get('missatge') or response.text[:500]
        if response.status_code == 429 and busy_retries:
            busy_retries -= 1
            time.sleep(random.uniform(5, 10))
            continue
        if response.status_code in (502, 504) and model_retries:
            model_retries -= 1
            continue
        raise SuperHintError('HTTP %d %s: %s' % (response.status_code, code or '', message), code)
