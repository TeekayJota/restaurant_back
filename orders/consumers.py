import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer

# El nombre del grupo para la cocina (constante)
KITCHEN_GROUP_NAME = "kitchen"


class KitchenConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Unimos este cliente al grupo "kitchen"
        await self.channel_layer.group_add(
            KITCHEN_GROUP_NAME,
            self.channel_name
        )
        await self.accept()
        print(f"WebSocket: Cocina conectada: {self.channel_name}")

    async def disconnect(self, close_code):
        # Sacamos a este cliente del grupo
        await self.channel_layer.group_discard(
            KITCHEN_GROUP_NAME,
            self.channel_name
        )
        print(f"WebSocket: Cocina desconectada: {self.channel_name}")

    # Este método maneja el evento "send.new.order" enviado desde la vista
    async def send_new_order(self, event):
        # Enviamos el mensaje JSON al cliente WebSocket (React)
        await self.send_json({
            "type": "NEW_ORDER",
            "order": event["order"]
        })

    # Este método maneja el evento "send.status.update"
    async def send_status_update(self, event):
        await self.send_json({
            "type": "STATUS_UPDATE",
            "order": event["order"]
        })

    # Manejo de alertas de mesero (Si usamos el mismo canal por ahora)
    async def waiter_call(self, event):
        await self.send_json({
            "type": "WAITER_CALL",
            "table_code": event["table_code"],
            "status": event.get("status")
        })


# --- NUEVO CONSUMER PARA CLIENTES EN MESAS ---
class TableConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Obtenemos el código de la mesa de la URL (ej. M-01)
        # La URL en routing.py es: ws/table/(?P<table_code>...)/
        self.table_code = self.scope['url_route']['kwargs']['table_code']
        self.group_name = f"table_{self.table_code}"

        # Unimos al cliente al grupo específico de esa mesa
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Este método maneja los mensajes enviados desde las vistas (close_table)
    async def table_status_update(self, event):
        # Enviamos el mensaje al WebSocket del cliente (React)
        # event['data'] contiene { type: "TABLE_CLOSED", ... }
        await self.send_json(event['data'])