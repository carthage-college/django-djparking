from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView

from django.contrib import admin

admin.autodiscover()

handler404 = 'djtools.views.errors.four_oh_four_error'
handler500 = 'djtools.views.errors.server_error'

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    # my app
    url(r'^manager/', include('djparking.manager.urls')),
    # redirect
    url(r'^$', RedirectView.as_view(url="/foobar/")),
)
