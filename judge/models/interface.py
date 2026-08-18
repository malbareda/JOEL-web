import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from judge.models.profile import Profile

__all__ = ['MiscConfig', 'validate_regex', 'NavigationBar', 'BlogPost', 'BlogPostTranslation',
          'FlatPageTranslation']


class MiscConfig(models.Model):
    key = models.CharField(max_length=30, db_index=True)
    value = models.TextField(blank=True)

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = _('configuration item')
        verbose_name_plural = _('miscellaneous configuration')


def validate_regex(regex):
    try:
        re.compile(regex, re.VERBOSE)
    except re.error as e:
        raise ValidationError('Invalid regex: %s' % e.message)


class NavigationBar(MPTTModel):
    class Meta:
        verbose_name = _('navigation item')
        verbose_name_plural = _('navigation bar')

    class MPTTMeta:
        order_insertion_by = ['order']

    order = models.PositiveIntegerField(db_index=True, verbose_name=_('order'))
    key = models.CharField(max_length=10, unique=True, verbose_name=_('identifier'))
    label = models.CharField(max_length=20, verbose_name=_('label'))
    path = models.CharField(max_length=255, verbose_name=_('link path'))
    regex = models.TextField(verbose_name=_('highlight regex'), validators=[validate_regex])
    parent = TreeForeignKey('self', verbose_name=_('parent item'), null=True, blank=True,
                            related_name='children', on_delete=models.CASCADE)

    def __str__(self):
        return self.label

    @property
    def pattern(self, cache={}):
        # A cache with a bad policy is an alias for memory leak
        # Thankfully, there will never be too many regexes to cache.
        if self.regex in cache:
            return cache[self.regex]
        else:
            pattern = cache[self.regex] = re.compile(self.regex, re.VERBOSE)
            return pattern


class BlogPost(models.Model):
    title = models.CharField(verbose_name=_('post title'), max_length=100)
    authors = models.ManyToManyField(Profile, verbose_name=_('authors'), blank=True)
    slug = models.SlugField(verbose_name=_('slug'))
    visible = models.BooleanField(verbose_name=_('public visibility'), default=False)
    sticky = models.BooleanField(verbose_name=_('sticky'), default=False)
    publish_on = models.DateTimeField(verbose_name=_('publish after'))
    content = models.TextField(verbose_name=_('post content'))
    summary = models.TextField(verbose_name=_('post summary'), blank=True)
    og_image = models.CharField(verbose_name=_('openGraph image'), default='', max_length=150, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog_post', args=(self.id, self.slug))

    def can_see(self, user):
        if self.visible and self.publish_on <= timezone.now():
            return True
        return self.is_editable_by(user)

    def is_editable_by(self, user):
        if not user.is_authenticated:
            return False
        if user.has_perm('judge.edit_all_post'):
            return True
        return user.has_perm('judge.change_blogpost') and self.authors.filter(id=user.profile.id).exists()

    def _get_translation(self, language):
        # Cached per-instance so a single page render (list or detail) only ever queries the
        # translation once per post, even if title/content/summary are each asked for separately.
        cache = self.__dict__.setdefault('_translation_cache', {})
        if language not in cache:
            cache[language] = self.translations.filter(language=language).first()
        return cache[language]

    def get_translated_title(self, language):
        translation = self._get_translation(language)
        return translation.title if translation else self.title

    def get_translated_content(self, language):
        translation = self._get_translation(language)
        return translation.content if translation else self.content

    def get_translated_summary(self, language):
        translation = self._get_translation(language)
        if translation:
            return translation.summary or translation.content
        return self.summary or self.content

    class Meta:
        permissions = (
            ('edit_all_post', _('Edit all posts')),
        )
        verbose_name = _('blog post')
        verbose_name_plural = _('blog posts')


class BlogPostTranslation(models.Model):
    post = models.ForeignKey(BlogPost, verbose_name=_('post'), related_name='translations', on_delete=CASCADE)
    language = models.CharField(verbose_name=_('language'), max_length=7, choices=settings.LANGUAGES)
    title = models.CharField(verbose_name=_('translated title'), max_length=100)
    content = models.TextField(verbose_name=_('translated content'))
    summary = models.TextField(verbose_name=_('translated summary'), blank=True,
                               help_text=_('Leave blank to fall back to the translated content, '
                                           'same as the untranslated post.'))

    class Meta:
        unique_together = ('post', 'language')
        verbose_name = _('blog post translation')
        verbose_name_plural = _('blog post translations')


class FlatPageTranslation(models.Model):
    page = models.ForeignKey('flatpages.FlatPage', verbose_name=_('page'), related_name='translations',
                             on_delete=CASCADE)
    language = models.CharField(verbose_name=_('language'), max_length=7, choices=settings.LANGUAGES)
    title = models.CharField(verbose_name=_('translated title'), max_length=200)
    content = models.TextField(verbose_name=_('translated content'), blank=True)

    class Meta:
        unique_together = ('page', 'language')
        verbose_name = _('flat page translation')
        verbose_name_plural = _('flat page translations')
