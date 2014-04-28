from django.conf.urls.defaults import *
from django.contrib import admin

#django discovery
admin.autodiscover()

urlpatterns = patterns('djparking.manager.views',
    url(r'^$','search', name="manager_default_search"),
    url(r'^display/(?P<pid>\d+)/$','display', name="manager_display"),
    url(r'^search/$','search', name="manager_search"),
    url(r'^create/$','create', name="manager_create"),
    url(r'^update/$','update', name="manager_update"),
    url(r'^ajax/makes/(?P<year>\d{4})/$','ajaxCarMakes', name="ajax_carMakes"),
    url(r'^ajax/models/(?P<year>\d{4})/(?P<make>\w+)/$','ajaxCarModels', name="ajax_carModels"),
    url(r'^ajax/permits/(?P<acadYear>\d{4})/(?P<lotcode>\w+)/$','ajaxStickers', name='ajax_stickers'),
    url(r'^ajax/search/(?P<acadYear>\d{4})/$','ajaxSearch',name="ajax_search"),
    #url(r'^manager/admin/(.*)', admin.site.root),
)
