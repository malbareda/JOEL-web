import logging

from celery import shared_task

from judge.models import HelpChatMessage
from judge.utils.helpchat import ask_reply
from judge.utils.superhints import SuperHintError

__all__ = ('request_help_chat_reply',)

logger = logging.getLogger('judge.superhints')


def _fail(reply, error):
    HelpChatMessage.objects.filter(id=reply.id, status=HelpChatMessage.PENDING) \
        .update(status=HelpChatMessage.ERROR, error=error)


@shared_task
def request_help_chat_reply(reply_id):
    """Asks the service for the answer to the pending JOEL row `reply_id` and fills it in. Written as updates on
    the pending row, so an answer that arrives after the page gave up on it does not overwrite anything."""
    reply = HelpChatMessage.objects.select_related(
        'user__language', 'problem__data_files', 'problem__group',
    ).get(id=reply_id)
    if reply.status != HelpChatMessage.PENDING:
        return

    try:
        answer = ask_reply(reply)
    except SuperHintError as e:
        logger.warning('Help chat reply %d failed: %s', reply.id, e)
        _fail(reply, str(e))
        return
    except Exception as e:
        logger.exception('Help chat reply %d failed', reply.id)
        _fail(reply, repr(e))
        return

    HelpChatMessage.objects.filter(id=reply.id, status=HelpChatMessage.PENDING).update(
        status=HelpChatMessage.OK, text=answer['missatge'], revision=(answer.get('revisio') or '')[:20],
    )
