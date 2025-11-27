from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/kitchen/$', consumers.KitchenConsumer.as_asgi()),

    # --- CAMBIO RECOMENDADO ---
    # Usar [^/]+ acepta "M-01", "Barra1", "VIP", etc.
    re_path(r'ws/table/(?P<table_code>[^/]+)/$', consumers.TableConsumer.as_asgi()),
]