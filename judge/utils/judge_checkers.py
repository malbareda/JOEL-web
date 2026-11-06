"""Loads checkers of the judge engine (site-packages/dmoj/checkers) from the site.

This repo has its own `dmoj` package (the site settings) that shadows the engine's, so `import dmoj.checkers...`
can't reach them. The site still wants the very code that grades submissions, e.g. to validate a reference before
a problem is created, so the checker files are loaded by path, with the few engine modules they import stubbed
while they load.
"""
import importlib.util
import os
import sys
import types

_loaded = {}


class _CheckerResult(object):
    def __init__(self, passed, points, feedback=None, extended_feedback=None):
        self.passed, self.points, self.feedback, self.extended_feedback = passed, points, feedback, extended_feedback


def _path(name):
    for directory in sys.path:
        candidate = os.path.join(directory, 'dmoj', 'checkers', '%s.py' % name) if directory else None
        if candidate and os.path.exists(candidate):
            return candidate
    raise ImportError("Could not find the judge engine's dmoj/checkers/%s.py in sys.path" % name)


def load_judge_checker(name):
    """The judge's dmoj/checkers/<name>.py as a module (loaded once). Supports checkers that import from
    dmoj.checkers.sql, dmoj.result and dmoj.judgeenv."""
    if name in _loaded:
        return _loaded[name]
    stubs = {'dmoj.judgeenv': types.SimpleNamespace(get_problem_root=None),
             'dmoj.result': types.SimpleNamespace(CheckerResult=_CheckerResult)}
    if name != 'sql':
        stubs['dmoj.checkers.sql'] = load_judge_checker('sql')
    saved = {key: sys.modules.get(key) for key in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location('judge_engine_checker_%s' % name, _path(name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for key, old in saved.items():
            if old is None:
                del sys.modules[key]
            else:
                sys.modules[key] = old
    _loaded[name] = module
    return module
