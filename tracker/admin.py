from django.contrib import admin
from .models import Workplace

@admin.register(Workplace)
class WorkplaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'bbox', 'created_at')
    search_fields = ('name',)
    # Поле 'times' может быть большим, поэтому не выводим его в списке
    # readonly_fields = ('id', 'created_at', 'times')
