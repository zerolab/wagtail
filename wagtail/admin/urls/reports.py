from django.conf.urls import url

from wagtail.admin.views import reports

app_name = 'wagtailadmin_reports'
urlpatterns = [
    url(r'^locked/$', reports.LockedPagesView.as_view(), name='locked_pages'),
    url(r'^workflow/$', reports.WorkflowView.as_view(), name='workflow'),
    url(r'^workflow_tasks/$', reports.WorkflowTasksView.as_view(), name='workflow_tasks'),
    url(r'^workflow/tasks/$', reports.WorkflowTasksView.as_view(), name='workflow_tasks'),
    url(r'^site-history/$', reports.LogEntriesView.as_view(), name='site_history'),
]
