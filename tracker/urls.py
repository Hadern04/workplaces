from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/workplaces/', views.workplace_api, name='workplace-api'),
    path('api/workplaces/<uuid:pk>/', views.workplace_detail_api, name='workplace-detail-api'),
    path('api/workplaces/<uuid:pk>/confirm/', views.workplace_confirm_api, name='workplace-confirm-api'),
    path('api/workplaces/<uuid:pk>/report/', views.workplace_report_api, name='workplace-report-api'),
]