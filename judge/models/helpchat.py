from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

__all__ = ['HelpChatMessage']


class HelpChatMessage(models.Model):
    """One message of the help chat ("No sé ni per on començar") of a student on a problem, with the AI of the
    joel-pistes service (see judge/utils/helpchat.py). The conversation of a student on a problem is all their rows,
    in order of `id`; the service keeps nothing, so every turn sends the whole thing. A reply being asked for is a
    JOEL row in state PENDING, filled in (or marked ERROR) by the Celery task `request_help_chat_reply`."""
    STUDENT = 'A'
    JOEL = 'J'
    ROLE = (
        (STUDENT, _('Student')),
        (JOEL, _('JOEL')),
    )

    PENDING = 'P'
    OK = 'OK'
    ERROR = 'E'
    STATUS = (
        (PENDING, _('Pending')),
        (OK, _('OK')),
        (ERROR, _('Error')),
    )

    user = models.ForeignKey('Profile', verbose_name=_('user'), related_name='help_chat_messages',
                             on_delete=models.CASCADE)
    problem = models.ForeignKey('Problem', verbose_name=_('problem'), related_name='help_chat_messages',
                                on_delete=models.CASCADE)
    role = models.CharField(max_length=1, verbose_name=_('role'), choices=ROLE)
    status = models.CharField(max_length=2, verbose_name=_('status'), choices=STATUS, default=OK)
    language = models.CharField(max_length=10, verbose_name=_('language'), default='ca')
    text = models.TextField(verbose_name=_('message'), blank=True)
    revision = models.CharField(max_length=20, verbose_name=_('review result'), blank=True)
    error = models.TextField(verbose_name=_('request error'), blank=True)
    created = models.DateTimeField(verbose_name=_('created'), auto_now_add=True)

    # A reply still pending after this long is given up on (the service answers in 3-10 s, 60 s at most, plus
    # retries), so a lost Celery task does not leave the student's chat locked.
    STALE_AFTER = timedelta(minutes=3)

    @classmethod
    def conversation(cls, profile, problem):
        return cls.objects.filter(user=profile, problem=problem).order_by('id')

    @classmethod
    def student_messages_of(cls, profile, problem):
        return cls.objects.filter(user=profile, problem=problem, role=cls.STUDENT)

    @classmethod
    def pending_of(cls, profile, problem):
        """Replies being waited for, not counting the ones given up on."""
        return cls.objects.filter(user=profile, problem=problem, role=cls.JOEL, status=cls.PENDING,
                                  created__gte=timezone.now() - cls.STALE_AFTER)

    def give_up_if_stale(self):
        if self.status == self.PENDING and self.created < timezone.now() - self.STALE_AFTER:
            self.status = self.ERROR
            self.error = 'timed out waiting for the Celery task'
            self.save(update_fields=['status', 'error'])

    class Meta:
        verbose_name = _('help chat message')
        verbose_name_plural = _('help chat messages')
        index_together = (('user', 'problem'),)
