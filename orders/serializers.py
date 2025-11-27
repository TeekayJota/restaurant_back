from rest_framework import serializers
from .models import Order, OrderItem, Product, Table, Review
from decimal import Decimal
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .consumers import KITCHEN_GROUP_NAME
from django.db import transaction


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'unit_price', 'notes', 'selected_options']
        read_only_fields = ['unit_price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    proposed_changes = serializers.JSONField(read_only=True)

    table = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), write_only=True, required=False)
    table_code = serializers.CharField(source='table.code', read_only=True)
    table_code_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = [
            'id', 'table', 'table_code', 'table_code_input',
            'status', 'status_display', 'created_at', 'items',
            'total_price',
            'proposed_changes',
            'preparing_at', 'ready_at', 'delivered_at', 'paid_at'  # Timestamps
        ]
        read_only_fields = ['total_price', 'proposed_changes']

    # ... (MÉTODOS CREATE Y UPDATE SE MANTIENEN IGUAL QUE ANTES) ...
    # (Por brevedad, asumo que mantienes el create y update que ya funcionaban.
    # Si necesitas que te los pegue de nuevo completos dímelo, pero no cambian para esta historia).

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        table_obj = validated_data.pop('table', None)
        table_code_input = validated_data.pop('table_code_input', None)

        if not table_obj and table_code_input:
            try:
                table_obj = Table.objects.get(code=table_code_input)
            except Table.DoesNotExist:
                raise serializers.ValidationError({'table_code_input': 'Mesa no encontrada'})

        if not table_obj:
            raise serializers.ValidationError({'table': 'Debe indicar una mesa'})

        # --- LÓGICA DE TOKEN: SE MUEVE A LA VISTA ---
        # (El serializer solo crea la orden, el token lo manejamos mejor en la vista o dejamos que se cree aqui)
        # Para mantener coherencia con el plan anterior, lo haremos en la VISTA 'create' o aquí.
        # Dejémoslo aquí para asegurar que SIEMPRE que se crea una orden, se ocupa la mesa.

        if table_obj.status == 'LIBRE':
            table_obj.status = 'OCUPADA'
            # Importamos uuid dentro de la función para evitar ciclos si fuera necesario
            import uuid
            table_obj.session_token = uuid.uuid4()
            table_obj.save(update_fields=['status', 'session_token'])

        order = Order.objects.create(table=table_obj, total_price=Decimal('0.00'), **validated_data)
        order_total = Decimal('0.00')

        for item_data in items_data:
            product_name = item_data.get('product_name')
            try:
                product = Product.objects.get(name=product_name)
                item_price = product.base_price
            except Product.DoesNotExist:
                raise serializers.ValidationError({'items': f"El producto '{product_name}' no existe."})

            OrderItem.objects.create(order=order, unit_price=item_price, **item_data)
            order_total += item_price

        order.total_price = order_total
        order.save(update_fields=['total_price'])

        try:
            serializer_for_ws = self.__class__(order)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                KITCHEN_GROUP_NAME, {"type": "send.new.order", "order": serializer_for_ws.data}
            )
        except Exception:
            pass
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        # (Mismo código de update que ya tenías funcionando)
        items_data = validated_data.pop('items', None)
        if items_data is not None:
            instance.items.all().delete()
            order_total = Decimal('0.00')
            for item_data in items_data:
                product_name = item_data.get('product_name')
                try:
                    product = Product.objects.get(name=product_name)
                    item_price = product.base_price
                except Product.DoesNotExist:
                    raise serializers.ValidationError({'items': f"El producto '{product_name}' no existe."})
                OrderItem.objects.create(order=instance, unit_price=item_price, **item_data)
                order_total += item_price
            instance.total_price = order_total
            instance.save(update_fields=['total_price'])
        return super().update(instance, validated_data)


class ProductSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    option_schema = serializers.JSONField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'category_display', 'base_price', 'description', 'option_schema']


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "code", "is_active", "status", "needs_assistance"]


# --- NUEVOS SERIALIZADORES ---

class PublicTableSerializer(serializers.ModelSerializer):
    """Lo que ve el cliente al escanear el QR"""

    class Meta:
        model = Table
        # NO incluimos session_token aquí por seguridad
        fields = ['id', 'code', 'status', 'needs_assistance']


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['order_item', 'rating', 'comment']