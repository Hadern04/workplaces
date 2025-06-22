from django.db import models
import uuid

class Workplace(models.Model):
    """Модель для хранения информации о рабочих местах."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Название")
    # Используем JSONField для хранения координат и истории времени
    bbox = models.JSONField(verbose_name="Координаты (x,y,w,h)")
    times = models.JSONField(default=list, verbose_name="История занятости")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Рабочее место"
        verbose_name_plural = "Рабочие места"
        ordering = ['created_at']

