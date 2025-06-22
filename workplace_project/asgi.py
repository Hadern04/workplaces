import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workplace_project.settings')

django_application = get_asgi_application()

def get_application():
    import tracker.routing  # Теперь импорт после инициализации Django
    return ProtocolTypeRouter({
        "http": django_application,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                tracker.routing.websocket_urlpatterns
            )
        ),
    })

application = get_application()