from rest_framework import serializers
from .models import Order, OrderItem, Product, Table


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'notes', 'selected_options']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    table = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), write_only=True, required=False)
    table_code = serializers.CharField(source='table.code', read_only=True)
    table_code_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = ['id', 'table', 'table_code', 'table_code_input', 'status', 'status_display', 'created_at', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        # Resolver mesa por id o por código
        table_obj = validated_data.pop('table', None)
        table_code_input = validated_data.pop('table_code_input', None)

        if not table_obj and table_code_input:
            try:
                table_obj = Table.objects.get(code=table_code_input)
            except Table.DoesNotExist:
                raise serializers.ValidationError({'table_code_input': 'Mesa no encontrada'})

        if not table_obj:
            raise serializers.ValidationError({'table': 'Debe indicar una mesa'})

        order = Order.objects.create(table=table_obj, **validated_data)
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
        return order


class ProductSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    option_schema = serializers.JSONField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'category_display', 'base_price', 'description', 'option_schema']


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "code", "is_active"]