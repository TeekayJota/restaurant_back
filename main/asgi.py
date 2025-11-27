"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# --- 1. Importaciones nuevas de Channels ---
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
# --- 2. IMPORTACIÓN NUEVA DE SEGURIDAD ---
from channels.security.websocket import AllowedHostsOriginValidator
import orders.routing  # Importamos las rutas de nuestra app 'orders'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

# --- 3. Lógica del ProtocolTypeRouter MODIFICADA ---
application = ProtocolTypeRouter({

    # Caso 1: Solicitud HTTP (API, Admin, etc.)
    # Usa la configuración estándar de Django.
    "http": get_asgi_application(),

    # Caso 2: Solicitud WebSocket (ws://)
    # --- 4. ENVOLVEMOS LA PILA CON 'AllowedHostsOriginValidator' ---
    # Esto le dirá a Channels que acepte conexiones WebSocket
    # de los hosts listados en tu 'ALLOWED_HOSTS' de settings.py
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                # Apunta a las rutas WebSocket que definimos en la app 'orders'
                orders.routing.websocket_urlpatterns
            )
        )
    ),
})