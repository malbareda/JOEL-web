"""
Parsing of the ad-hoc "extended feedback" blob produced by the linecount/rstripped
checkers for the hint system. Ported from templates/submission/status-testcases.html,
where this used to be re-parsed (twice, once per audience) on every template render.

The blob uses three private-use unicode characters as separators:
  FIELD_SEP   (✙) separates top-level fields.
  RECORD_SEP  (✡) separates one wrong-answer record from the next.
  SUBFIELD_SEP(✠) separates the fields *within* one wrong-answer record
              (failed case index, expected answer, actual answer).
"""

FIELD_SEP = '✙'
RECORD_SEP = '✡'
SUBFIELD_SEP = '✠'


def parse_rstripped(extended_feedback):
    parts = extended_feedback.split(FIELD_SEP)
    return {
        'type': 'rstripped',
        'expected': parts[0],
        'yours': parts[1] if len(parts) > 1 else '',
    }


def _wrong_input_lines(listinputs, firstwa, ninputs, noutputs, caseformat):
    """Returns the slice of `listinputs` (list of str) that was the wrong input
    for the record at index `firstwa`, per the case format / input-output ratio."""
    if caseformat == 'multicas':
        cn, ck = -1, 0
        result = []
        for inpc in listinputs[1:]:
            if ck == 0:
                cn += 1
                ck = int(inpc.split()[0])
                if cn == firstwa:
                    result.append(inpc)
            elif cn == firstwa:
                result.append(inpc)
                ck -= 1
            else:
                ck -= 1
        return result
    if caseformat == 'indiv':
        return list(listinputs)
    if ninputs == noutputs or (ninputs - 1 == noutputs and caseformat == 'stop'):
        return [listinputs[firstwa]]
    if ninputs - 1 == noutputs:
        return [listinputs[firstwa + 1]]
    if ninputs % noutputs == 0 or ((ninputs - 1) % noutputs == 0 and caseformat == 'stop'):
        div = ninputs // noutputs
        return listinputs[firstwa * div:firstwa * div + div]
    if (ninputs - 1) % noutputs == 0:
        div = (ninputs - 1) // noutputs
        return listinputs[firstwa * div + 1:firstwa * div + 1 + div]
    if noutputs % (ninputs - 1) == 0:
        div = noutputs // (ninputs - 1)
        return listinputs[firstwa // div + 1:firstwa // div + 1 + div]
    return []


def _linecount_common(extended_feedback):
    parts = extended_feedback.split(FIELD_SEP)
    ninputs = int(parts[2])
    noutputs = int(parts[3])
    listinputs = parts[0].split('\n')
    return parts, ninputs, noutputs, listinputs


def parse_linecount_single(extended_feedback, caseformat):
    """The one wrong-answer record a student sees after using a hint on this case."""
    parts, ninputs, noutputs, listinputs = _linecount_common(extended_feedback)
    record = parts[1]
    firstwa_str = record.split(SUBFIELD_SEP)[0]
    # Jinja's `|int` filter defaults to 0 for a non-numeric value (e.g. empty string);
    # matched here so the wrong-input slice below is computed the same way either way.
    firstwa = int(firstwa_str) if firstwa_str else 0
    your_answer = record.split(SUBFIELD_SEP)[2].split(RECORD_SEP)[0] if firstwa_str else ''
    return {
        'type': 'linecount',
        'wrong_input_lines': _wrong_input_lines(listinputs, firstwa, ninputs, noutputs, caseformat),
        'your_answer': your_answer,
    }


def parse_linecount_all(extended_feedback, caseformat, limit=5):
    """All wrong-answer records (up to `limit`), for teacher/evaluator review."""
    parts, ninputs, noutputs, listinputs = _linecount_common(extended_feedback)
    records = parts[1].strip().split(RECORD_SEP)
    out = []
    for record in records[:limit]:
        if not record:
            continue
        fields = record.split(SUBFIELD_SEP)
        firstwa = int(fields[0])
        out.append({
            'wrong_input_lines': _wrong_input_lines(listinputs, firstwa, ninputs, noutputs, caseformat),
            'expected': fields[1] if len(fields) > 1 else '',
            'actual': fields[2] if len(fields) > 2 else '',
        })
    return {'type': 'linecount-all', 'records': out}


def parse_generic_teacher(extended_feedback, limit=5):
    """Teacher/evaluator view for checkers other than rstripped/linecount."""
    parts = extended_feedback.split(FIELD_SEP)
    records = parts[1].split(RECORD_SEP) if len(parts) > 1 else []
    out = []
    for record in records[:limit]:
        if not record:
            continue
        fields = record.split(SUBFIELD_SEP)
        out.append({
            'case': fields[0] if len(fields) > 0 else '',
            'expected': fields[1] if len(fields) > 1 else '',
            'actual': fields[2] if len(fields) > 2 else '',
        })
    return {'type': 'generic', 'input': parts[0], 'records': out}
