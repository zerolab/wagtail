import json

from django.conf import settings
from django.contrib.admin.options import get_content_type_for_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from modelcluster.fields import ParentalKey
from taggit.models import Tag

# The edit_handlers module extends Page with some additional attributes required by
# wagtail admin (namely, base_form_class and get_edit_handler). Importing this within
# wagtail.admin.models ensures that this happens in advance of running wagtail.admin's
# system checks.
from wagtail.admin import edit_handlers  # NOQA
from wagtail.core.models import Page


def get_object_usage(obj):
    """Returns a queryset of pages that link to a particular object"""

    pages = Page.objects.none()

    # get all the relation objects for obj
    relations = [f for f in type(obj)._meta.get_fields(include_hidden=True)
                 if (f.one_to_many or f.one_to_one) and f.auto_created]
    for relation in relations:
        related_model = relation.related_model

        # if the relation is between obj and a page, get the page
        if issubclass(related_model, Page):
            pages |= Page.objects.filter(
                id__in=related_model._base_manager.filter(**{
                    relation.field.name: obj.id
                }).values_list('id', flat=True)
            )
        else:
            # if the relation is between obj and an object that has a page as a
            # property, return the page
            for f in related_model._meta.fields:
                if isinstance(f, ParentalKey) and issubclass(f.remote_field.model, Page):
                    pages |= Page.objects.filter(
                        id__in=related_model._base_manager.filter(
                            **{
                                relation.field.name: obj.id
                            }).values_list(f.attname, flat=True)
                    )

    return pages


def popular_tags_for_model(model, count=10):
    """Return a queryset of the most frequently used tags used on this model class"""
    content_type = ContentType.objects.get_for_model(model)
    return Tag.objects.filter(
        taggit_taggeditem_items__content_type=content_type
    ).annotate(
        item_count=Count('taggit_taggeditem_items')
    ).order_by('-item_count')[:count]


class LogEntryManager(models.Manager):

    def log_action(self, instance, action, **kwargs):
        """
        :param instance: The model instance we are logging an action for
        :param action: The action. Should be namespaced to app (e.g. wagtail.create, wagtail.workflow.start)
        :param kwargs: Addition fields to for the LogEntry model
            - user: The user performing the action
            - title: the instance title
            - data:
            - revision: a PageRevision instance, if the instance is a
            - created, published, unpublished, content_changed, deleted - Boolean flags
        :return: The new log entry
        """
        data = kwargs.pop('data', '')
        title = kwargs.pop('title', None)
        if not title:
            if hasattr(instance, 'get_admin_display_title'):
                title = instance.get_admin_display_title()
            else:
                title = str(instance)
        return self.model.objects.create(
            content_type=get_content_type_for_model(instance),
            object_id=instance.pk,
            object_title=title,
            action=action,
            timestamp=timezone.now(),
            data_json=json.dumps(data),
            **kwargs,
        )

    def get_for_model(self, model):
        # Return empty queryset if the given object is not valid.
        if not issubclass(model, models.Model):
            return self.none()

        ct = ContentType.objects.get_for_model(model)

        return self.filter(content_type=ct)

    def get_for_instance(self, instance):
        ct = get_content_type_for_model(instance)
        return self.filter(content_type=ct, object_id=instance.pk)

    def get_for_user(self, user_id):
        return self.filter(user=user_id)


class LogEntry(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        models.SET_NULL,
        verbose_name=_('content type'),
        blank=True, null=True,
        related_name='+',
    )
    object_id = models.CharField(max_length=255, blank=False, db_index=True)
    object_title = models.TextField()

    action = models.CharField(max_length=255, blank=True, db_index=True)
    data_json = models.TextField(blank=True)
    timestamp = models.DateTimeField("Timestamp (UTC)")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,  # Null if actioned by system
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name='+',
    )

    # Pointer to a specific page revision, if the object inherits from the Page model.
    revision = models.ForeignKey(
        'wagtailcore.PageRevision',
        null=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name='+',
    )

    # Flags for additional context to the 'action' made by the user (or system).
    created = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    unpublished = models.BooleanField(default=False)
    content_changed = models.BooleanField(default=False, db_index=True)
    deleted = models.BooleanField(default=False)

    objects = LogEntryManager()

    @cached_property
    def username(self):
        if self.user_id:
            try:
                return self.user.get_username()
            except self._meta.get_field('user').related_model.DoesNotExist:
                # User has been deleted
                return _('user {id} (deleted)').format(id=self.user_id)
        else:
            return _('system')

    @cached_property
    def data(self):
        if self.data_json:
            return json.loads(self.data_json)
        else:
            return {}
