from django.conf.urls import patterns, include, url
from django.contrib import admin

#django discovery
admin.autodiscover()

urlpatterns = patterns('djparking.manager.views',
    url(r'^$','search', name="manager_default_search"),
    #url(r'^display/(?P<pid>\d+)/$','display', name="manager_display"),
    url(r'^search/$','search', name="manager_search"),
    url(r'^search/(?P<redir_id>\d+)/(?P<redir_acad_yr>\d{4})/$', 'search', name="manager_search_redirect"),
    url(r'^create/$','create', name="manager_create"),
    url(r'^update/$','update', name="manager_update"),
    url(r'^ajax/lots/','ajaxLots',name="ajax_lots"),
    url(r'^ajax/makes/$','ajaxCarMakes',name="ajax_carMakes"),
    url(r'^ajax/models/$','ajaxCarModels', name="ajax_carModels"),
    url(r'^ajax/permits/$','ajaxStickers',name='ajax_stickers'),
    url(r'^ajax/search/$','ajaxSearch',name="ajax_search"),
    #url(r'^manager/admin/(.*)', admin.site.root),
)
