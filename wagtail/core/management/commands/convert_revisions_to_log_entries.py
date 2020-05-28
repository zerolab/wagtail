import json

from django.core.management.base import BaseCommand
from wagtail.core.models import LogEntry, PageRevision


class Command(BaseCommand):
    def handle(self, *args, **options):
        current_page_id = None

        revisions_that_were_once_live = set()
        revision_that_got_log_entries = set()
        for revision in PageRevision.objects.order_by('page_id', 'created_at').select_related('page').iterator():
            is_new_page = revision.page_id != current_page_id
            current_page_id = revision.page_id
            if is_new_page:
                previous_revision_content = None

            content = json.loads(revision.content_json)

            if content.get('live_revision'):
                revisions_that_were_once_live.add(content['live_revision'])

            for ignored_field in ['live', 'has_unpublished_changes', 'url_path', 'path', 'depth', 'numchild', 'latest_revision_created_at', 'live_revision', 'draft_title', 'owner', 'locked']:
                del content[ignored_field]

            if not LogEntry.objects.filter(revision=revision).exists():
                revision_that_got_log_entries.add(revision.id)
                content_changed = not is_new_page and previous_revision_content != content
                published = revision.id == revision.page.live_revision_id

                if content_changed or published:
                    LogEntry.objects.log_action(
                        instance=revision.page.specific,
                        action='wagtail.publish' if published else 'wagtail.edit',
                        data='',
                        revision=revision,
                        user=revision.user,
                        timestamp=revision.created_at,
                        created=is_new_page,
                        content_changed=content_changed,
                        published=revision.id == revision.page.live_revision_id,
                    )

            previous_revision_content = content

        LogEntry.objects.filter(
            revision_id__in=revisions_that_were_once_live.intersection(revision_that_got_log_entries), published=False
        ).update(published=True)
