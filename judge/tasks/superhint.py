import logging

from celery import shared_task

from judge.models import SuperHint
from judge.utils.superhints import SuperHintError, ask, build_request

__all__ = ('request_superhint',)

logger = logging.getLogger('judge.superhints')


@shared_task
def request_superhint(superhint_id):
    superhint = SuperHint.objects.select_related(
        'submission__problem__data_files', 'submission__problem__group', 'submission__language',
        'submission__source', 'case',
    ).get(id=superhint_id)
    previous = SuperHint.objects.filter(
        submission__user_id=superhint.submission.user_id, submission__problem_id=superhint.submission.problem_id,
        status=SuperHint.OK, id__lt=superhint.id,
    ).order_by('id').values_list('text', flat=True)

    try:
        answer = ask(build_request(superhint, previous))
    except SuperHintError as e:
        logger.warning('Superhint %d failed: %s', superhint.id, e)
        superhint.status = SuperHint.ERROR
        superhint.error = str(e)
        superhint.save(update_fields=['status', 'error'])
        return
    except Exception as e:
        logger.exception('Superhint %d failed', superhint.id)
        superhint.status = SuperHint.ERROR
        superhint.error = repr(e)
        superhint.save(update_fields=['status', 'error'])
        return

    superhint.status = SuperHint.OK
    superhint.level = answer.get('nivell')
    superhint.text = answer['pista']
    superhint.error_category = (answer.get('categoria_error') or '')[:30]
    superhint.teacher_diagnosis = answer.get('diagnosi_professorat') or ''
    superhint.revision = (answer.get('revisio') or '')[:20]
    superhint.save()
