from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    # API эндпоинты
    path('api/workplaces/', views.workplace_api, name='workplace-api'),
    path('api/workplaces/<uuid:pk>/', views.workplace_detail_api, name='workplace-detail-api'),
]
