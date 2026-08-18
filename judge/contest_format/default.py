from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.base import BaseContestFormat
from judge.contest_format.registry import register_contest_format
from judge.utils.timedelta import nice_repr


@register_contest_format('default')
class DefaultContestFormat(BaseContestFormat):
    name = gettext_lazy('Default')

    @classmethod
    def validate(cls, config):
        if config is not None and (not isinstance(config, dict) or config):
            raise ValidationError('default contest expects no config or empty dict as config')

    def __init__(self, contest, config):
        super(DefaultContestFormat, self).__init__(contest, config)

    def _count_tries(self, submissions, problem_id, best_time, best_points):
        """Number of wrong/incomplete attempts at a problem: every non-IE/CE submission up to and
        including the best one, minus the best one itself if it actually scored something --
        otherwise (never scored at all) every attempt counts as a try. `submissions` is whatever
        queryset the caller considers "visible" (all of them normally, or only those before
        freeze_time while frozen)."""
        subs = submissions.exclude(submission__result__isnull=True) \
                          .exclude(submission__result__in=['IE', 'CE']) \
                          .filter(problem_id=problem_id)
        if best_points:
            return subs.filter(submission__date__lte=best_time).count() - 1
        return subs.count()

    def update_participation(self, participation):
        cumtime = 0
        points = 0
        format_data = {}

        for result in participation.submissions.values('problem_id').annotate(
                time=Max('submission__date'), points=Max('points'),
        ):
            dt = (result['time'] - participation.start).total_seconds()
            if result['points']:
                cumtime += dt
            tries = self._count_tries(participation.submissions, result['problem_id'], result['time'], result['points'])
            format_data[str(result['problem_id'])] = {'time': dt, 'points': result['points'], 'tries': tries}
            points += result['points']

        participation.cumtime = max(cumtime, 0)
        participation.score = points
        participation.tiebreaker = 0
        participation.format_data = format_data
        participation.save()

    def get_frozen_state(self, participation, freeze_time):
        # Mirrors update_participation, but considering only submissions strictly before
        # freeze_time -- the persisted participation.score/cumtime/format_data are never touched
        # here, this is purely a throwaway snapshot for scoreboard display while frozen.
        cumtime = 0
        points = 0
        format_data = {}
        pending = set(
            participation.submissions.filter(submission__date__gte=freeze_time)
                                     .values_list('problem_id', flat=True),
        )

        frozen_subs = participation.submissions.filter(submission__date__lt=freeze_time)
        for result in frozen_subs.values('problem_id').annotate(
                time=Max('submission__date'), points=Max('points'),
        ):
            dt = (result['time'] - participation.start).total_seconds()
            if result['points']:
                cumtime += dt
            tries = self._count_tries(frozen_subs, result['problem_id'], result['time'], result['points'])
            format_data[str(result['problem_id'])] = {'time': dt, 'points': result['points'], 'tries': tries}
            points += result['points']

        return format_data, points, max(cumtime, 0), 0, pending

    def display_user_problem(self, participation, contest_problem):
        if contest_problem.id in (getattr(participation, '_frozen_pending', None) or ()):
            return self.pending_cell_html()

        format_data = (participation.format_data or {}).get(str(contest_problem.id))
        if format_data:
            cutoff = getattr(participation, '_frozen_cutoff', None)
            base_state = self.best_solution_state(format_data['points'], contest_problem.points)
            if self.contest.run_pretests_only and contest_problem.is_pretested:
                base_state = 'pretest-' + base_state
            extra = self.solve_extra_classes(participation, contest_problem, format_data, cutoff)
            tries = format_data.get('tries', 0)
            tries_html = format_html('<small style="color:red"> ({tries})</small>',
                                     tries=floatformat(tries)) if tries else ''
            return format_html(
                u'<td class="{state}"><a href="{url}">{points}{tries}<div class="solving-time">{time}</div></a></td>',
                state=' '.join([base_state] + extra),
                url=reverse('contest_user_submissions',
                            args=[self.contest.key, participation.user.user.username, contest_problem.problem.code]),
                points=floatformat(format_data['points']),
                tries=tries_html,
                time=nice_repr(timedelta(seconds=format_data['time']), 'noday'),
            )
        else:
            return mark_safe('<td></td>')

    def display_participation_result(self, participation):
        return format_html(
            u'<td class="user-points"><a href="{url}">{points}<div class="solving-time">{cumtime}</div></a></td>',
            url=reverse('contest_all_user_submissions',
                        args=[self.contest.key, participation.user.user.username]),
            points=floatformat(participation.score),
            cumtime=nice_repr(timedelta(seconds=participation.cumtime), 'noday'),
        )

    def get_problem_breakdown(self, participation, contest_problems):
        return [(participation.format_data or {}).get(str(contest_problem.id)) for contest_problem in contest_problems]

    def get_label_for_problem(self, index):
        return str(index + 1)
