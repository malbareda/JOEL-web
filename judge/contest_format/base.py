from abc import ABCMeta, abstractmethod, abstractproperty
from datetime import timedelta

from django.utils import six
from django.utils.html import format_html
from django.utils.timezone import now
from django.utils.translation import gettext


class abstractclassmethod(classmethod):
    __isabstractmethod__ = True

    def __init__(self, callable):
        callable.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable)


class BaseContestFormat(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def __init__(self, contest, config):
        self.config = config
        self.contest = contest

    @abstractproperty
    def name(self):
        """
        Name of this contest format. Should be invoked with gettext_lazy.

        :return: str
        """
        raise NotImplementedError()

    @abstractclassmethod
    def validate(cls, config):
        """
        Validates the contest format configuration.

        :param config: A dictionary containing the configuration for this contest format.
        :return: None
        :raises: ValidationError
        """
        raise NotImplementedError()

    @abstractmethod
    def update_participation(self, participation):
        """
        Updates a ContestParticipation object's score, cumtime, and format_data fields based on this contest format.
        Implementations should call ContestParticipation.save().

        :param participation: A ContestParticipation object.
        :return: None
        """
        raise NotImplementedError()

    @abstractmethod
    def display_user_problem(self, participation, contest_problem):
        """
        Returns the HTML fragment to show a user's performance on an individual problem. This is expected to use
        information from the format_data field instead of computing it from scratch.

        :param participation: The ContestParticipation object linking the user to the contest.
        :param contest_problem: The ContestProblem object representing the problem in question.
        :return: An HTML fragment, marked as safe for Jinja2.
        """
        raise NotImplementedError()

    @abstractmethod
    def display_participation_result(self, participation):
        """
        Returns the HTML fragment to show a user's performance on the whole contest. This is expected to use
        information from the format_data field instead of computing it from scratch.

        :param participation: The ContestParticipation object.
        :return: An HTML fragment, marked as safe for Jinja2.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_problem_breakdown(self, participation, contest_problems):
        """
        Returns a machine-readable breakdown for the user's performance on every problem.

        :param participation: The ContestParticipation object.
        :param contest_problems: The list of ContestProblem objects to display performance for.
        :return: A list of dictionaries, whose content is to be determined by the contest system.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_label_for_problem(self, index):
        """
        Returns the problem label for a given zero-indexed index.

        :param index: The zero-indexed problem index.
        :return: A string, the problem label.
        """
        raise NotImplementedError()

    @classmethod
    def best_solution_state(cls, points, total):
        if not points:
            return 'failed-score'
        if points == total:
            return 'full-score'
        return 'partial-score'

    # -- Shared support for scoreboard freezing (Contest.freeze_time) and the "first blood" /
    # "solved in the last 2 minutes" cell highlights. Concrete formats call these from their own
    # display_user_problem() -- see default.py/icpc.py. Not part of the abstract interface, so
    # formats that never call them (atcoder/ioi/ecoo/legacy_ioi) are unaffected.

    def pending_cell_html(self):
        """The cell shown, while frozen, for a problem that has a submission at/after the freeze
        cutoff: it must never reveal whether that submission was correct."""
        return format_html('<td class="frozen-pending" title="{title}">?</td>',
                           title=gettext('Submitted after the scoreboard froze'))

    def _compute_first_blood_map(self, cutoff):
        # Local import to avoid a circular import (judge.models imports contest_format indirectly
        # via Contest.format_name's choices).
        from judge.models import ContestSubmission

        contest_problems = list(self.contest.contest_problems.all())
        problem_points = {cp.id: cp.points for cp in contest_problems}

        qs = ContestSubmission.objects.filter(
            participation__contest=self.contest, participation__virtual=0, points__gt=0,
        ).select_related('submission')
        if cutoff is not None:
            qs = qs.filter(submission__date__lt=cutoff)

        best = {}  # contest_problem_id -> (date, participation_id)
        for cs in qs.iterator():
            full = problem_points.get(cs.problem_id)
            if not full or cs.points < full:
                continue
            date = cs.submission.date
            current = best.get(cs.problem_id)
            if current is None or date < current[0]:
                best[cs.problem_id] = (date, cs.participation_id)

        return {problem_id: participation_id for problem_id, (date, participation_id) in best.items()}

    def first_blood_map(self, cutoff):
        """contest_problem_id -> participation_id of whoever got full points on it first, counting
        only submissions strictly before `cutoff` (None means no cutoff -- the real, true state).
        Memoized per (format instance, cutoff): the format instance lives only for one request
        (Contest.format is a cached_property on a Contest instance Django fetches fresh per
        request), so this never leaks stale data across requests/contests."""
        cache = getattr(self, '_first_blood_cache', None)
        if cache is None:
            cache = self._first_blood_cache = {}
        if cutoff not in cache:
            cache[cutoff] = self._compute_first_blood_map(cutoff)
        return cache[cutoff]

    def solve_extra_classes(self, participation, contest_problem, format_data, cutoff):
        """CSS classes to layer on top of the normal solved/failed/partial state: 'first-blood' if
        this participation was the first to get full points on this problem (within whatever is
        currently visible, i.e. respecting `cutoff`), and 'recent-solve' if that happened in the
        last 2 real minutes (never true for anything hidden behind the freeze -- pulsing a cell
        would itself leak that "something just happened" on a problem the freeze is supposed to
        keep quiet)."""
        classes = []
        if not format_data or not contest_problem.points or format_data['points'] != contest_problem.points:
            return classes

        if self.first_blood_map(cutoff).get(contest_problem.id) == participation.id:
            classes.append('first-blood')

        solve_time = participation.start + timedelta(seconds=format_data['time'])
        if cutoff is None or solve_time < cutoff:
            if now() - solve_time <= timedelta(minutes=2):
                classes.append('recent-solve')

        return classes
