from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from judge.models import HelpChatMessage, Problem, Profile
from judge.tasks import request_help_chat_reply as request_help_chat_reply_task
from judge.utils import helpchat

__all__ = ['help_chat', 'help_chat_send', 'help_chat_reply']


def _problem_for(request, code):
    problem = get_object_or_404(Problem, code=code)
    if not problem.is_accessible_by(request.user):
        raise Http404()
    return problem


def _unavailable(request, problem):
    """Why the chat cannot be used on `problem` right now, or None."""
    if getattr(request, 'in_contest', False):
        return _('El xat d\'ajuda no està disponible durant un concurs.')
    if not helpchat.is_enabled(problem):
        return _('Aquest problema no té xat d\'ajuda.')
    return None


def _state(request, problem):
    used = HelpChatMessage.student_messages_of(request.profile, problem).count()
    return {
        'left': max(helpchat.max_student_messages() - used, 0),
        'max': helpchat.max_student_messages(),
        'busy': HelpChatMessage.pending_of(request.profile, problem).exists(),
    }


def _render(request, problem, messages):
    return render_to_string('problem/helpchat-messages.html', {
        'problem': problem,
        'chat_rows': [(m, helpchat.render_text(m.text) if m.role == HelpChatMessage.JOEL else None) for m in messages],
    }, request=request)


def _error(message, status=400):
    return JsonResponse({'success': False, 'error': str(message)}, status=status)


@login_required
def help_chat(request, problem):
    """The student's conversation on this problem, for the panel when it is opened."""
    problem = _problem_for(request, problem)
    reason = _unavailable(request, problem)
    if reason:
        return _error(reason, 403)
    rows = list(HelpChatMessage.conversation(request.profile, problem))
    for row in rows:
        row.give_up_if_stale()
    # An answer that failed is only shown while it is the last thing in the chat: sending anything else replaces it.
    shown = [row for i, row in enumerate(rows) if not (row.status == HelpChatMessage.ERROR and i < len(rows) - 1)]
    return JsonResponse(dict(_state(request, problem), success=True, html=_render(request, problem, shown),
                             empty=not shown))


@login_required
@require_POST
def help_chat_send(request, problem):
    """A new student message and the pending JOEL answer to it. With no text it retries the last answer, if that
    one failed (it does not use up a message)."""
    problem = _problem_for(request, problem)
    reason = _unavailable(request, problem)
    if reason:
        return _error(reason, 403)

    text = (request.POST.get('text') or '').strip()
    if len(text) > helpchat.max_message_length():
        return _error(_('El missatge és massa llarg (màxim %(max)s caràcters).') % {'max': helpchat.max_message_length()})
    language = (request.LANGUAGE_CODE or 'ca')[:10]

    created = []
    error = None
    with transaction.atomic():
        # Lock the student's profile row: the limit is per problem and two quick requests must not both pass it.
        Profile.objects.select_for_update().get(id=request.profile.id)
        last = HelpChatMessage.conversation(request.profile, problem).last()
        if HelpChatMessage.pending_of(request.profile, problem).exists():
            error = _('El JOEL encara està responent. Espera la seva resposta abans d\'escriure un altre missatge.')
        elif text:
            if HelpChatMessage.student_messages_of(request.profile, problem).count() >= helpchat.max_student_messages():
                error = _('Ja has fet servir tots els missatges del xat en aquest problema.')
            else:
                created.append(HelpChatMessage.objects.create(
                    user=request.profile, problem=problem, role=HelpChatMessage.STUDENT, text=text, language=language))
        elif last is None or last.role != HelpChatMessage.JOEL or last.status != HelpChatMessage.ERROR:
            error = _('Escriu un missatge.')

        if error is None:
            reply = HelpChatMessage.objects.create(
                user=request.profile, problem=problem, role=HelpChatMessage.JOEL, status=HelpChatMessage.PENDING,
                language=language)
            created.append(reply)
            transaction.on_commit(lambda: request_help_chat_reply_task.delay(reply.id))

    if error is not None:
        return _error(error)
    return JsonResponse(dict(_state(request, problem), success=True, html=_render(request, problem, created),
                             reply_id=reply.id))


@login_required
def help_chat_reply(request, problem, message):
    """Where the page asks, every few seconds, whether the JOEL answer it is waiting for has arrived."""
    problem = _problem_for(request, problem)
    row = get_object_or_404(HelpChatMessage, id=int(message), problem=problem, user=request.profile,
                            role=HelpChatMessage.JOEL)
    row.give_up_if_stale()
    return JsonResponse(dict(_state(request, problem), success=True, status=row.status,
                             html=_render(request, problem, [row])))
