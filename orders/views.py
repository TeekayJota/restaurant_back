# orders/views.py
from rest_framework import viewsets, mixins, generics, status as drf_status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Sum, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDate
from rest_framework.permissions import IsAuthenticated

from .models import Order, OrderItem, Product, Table, Review
from .serializers import (
    OrderSerializer, ProductSerializer, TableSerializer, OrderItemSerializer,
    PublicTableSerializer, ReviewSerializer
)

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

KITCHEN_GROUP_NAME = "kitchen"


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    def get_queryset(self):
        qs = (
            Order.objects
            .select_related("table")
            .prefetch_related("items")
            .order_by("-created_at")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            status_list = status_param.split(',')
            qs = qs.filter(status__in=status_list)
        return qs

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if order.status not in [Order.Status.NEW, Order.Status.PREPARING, Order.Status.WAITER_EDITING]:
            return Response(
                {"detail": "El pedido no puede ser modificado en este estado."},
                status=drf_status.HTTP_403_FORBIDDEN
            )

        previous_status = request.data.get('previous_status_on_edit')
        items_data = request.data.get('items')

        if not items_data:
            return Response(
                {"detail": "No se enviaron items."},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        if previous_status == Order.Status.PREPARING:
            order.proposed_changes = {"items": items_data}
            order.status = Order.Status.CHANGE_REQUESTED
            order.save(update_fields=['status', 'proposed_changes'])
            self.send_websocket_update(self.get_serializer(order).data)
            return Response(self.get_serializer(order).data)

        else:
            request.data['status'] = Order.Status.NEW
            response = super().update(request, *args, **kwargs)
            order.refresh_from_db()
            order.proposed_changes = {}
            order.save(update_fields=['proposed_changes'])
            self.send_websocket_update(response.data)
            return response

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status not in [Order.Status.NEW, Order.Status.WAITER_EDITING]:
            return Response({"detail": "Solo se pueden borrar pedidos nuevos."}, status=drf_status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def set_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")

        valid_statuses = {c[0] for c in Order.Status.choices}
        if new_status not in valid_statuses:
            return Response({"detail": "status inválido"}, status=drf_status.HTTP_400_BAD_REQUEST)

        if new_status == Order.Status.WAITER_EDITING:
            if order.status not in [Order.Status.NEW, Order.Status.PREPARING]:
                return Response({"detail": "Solo se puede editar un pedido 'NUEVO' o 'EN PREPARACIÓN'."},
                                status=drf_status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        if new_status == Order.Status.PREPARING and not order.preparing_at:
            order.preparing_at = now
        elif new_status == Order.Status.READY and not order.ready_at:
            order.ready_at = now

        order.status = new_status
        order.save()

        self.send_websocket_update(self.get_serializer(order).data)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["patch"], url_path='mark-delivered')
    def mark_as_delivered(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.READY:
            return Response({"detail": "Solo se pueden entregar pedidos 'LISTOS'."},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        order.status = Order.Status.DELIVERED
        order.delivered_at = timezone.now()
        order.save()

        self.send_websocket_update(self.get_serializer(order).data)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'], url_path='accept-change')
    @transaction.atomic
    def accept_change(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.CHANGE_REQUESTED:
            return Response({"detail": "El pedido no está en solicitud de cambio."},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        items_data = order.proposed_changes.get('items')
        if not items_data:
            return Response({"detail": "Datos corruptos."}, status=drf_status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            OrderItem.objects.filter(order=order).delete()
            order_total = Decimal('0.00')
            for item_data in items_data:
                item_price = Decimal(str(item_data.get('unit_price', '0.00')))
                OrderItem.objects.create(
                    order=order,
                    unit_price=item_price,
                    product_name=item_data.get('product_name'),
                    notes=item_data.get('notes'),
                    selected_options=item_data.get('selected_options', {}),
                )
                order_total += item_price

            order.total_price = order_total
            order.status = Order.Status.PREPARING
            order.proposed_changes = {}
            order.save()

        self.send_websocket_update(self.get_serializer(order).data)
        return Response({"detail": "Cambios aceptados."}, status=drf_status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject-change')
    @transaction.atomic
    def reject_change(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.CHANGE_REQUESTED:
            return Response({"detail": "El pedido no está en solicitud de cambio."},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        order.proposed_changes = {}
        order.status = Order.Status.PREPARING
        order.save()

        self.send_websocket_update(self.get_serializer(order).data)
        return Response({"detail": "Cambios rechazados."}, status=drf_status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path='close-table')
    @transaction.atomic
    def close_table(self, request):
        table_id = request.data.get("table_id")
        if not table_id: return Response({"detail": "Falta table_id"}, status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            table_obj = Table.objects.get(id=table_id)
        except Table.DoesNotExist:
            return Response({"detail": "Mesa no encontrada"}, status=drf_status.HTTP_404_NOT_FOUND)

        orders_to_close = table_obj.orders.filter(~Q(status=Order.Status.PAID))
        total = Decimal('0.00')
        updated_order_ids = []

        if orders_to_close.exists():
            total = orders_to_close.aggregate(total=Sum('total_price', default=Decimal('0.00')))['total']
            now = timezone.now()
            for order in orders_to_close:
                order.status = Order.Status.PAID
                order.paid_at = now
                order.save()
                updated_order_ids.append(order.id)
                self.send_websocket_update(self.get_serializer(order).data)

        # Limpieza
        table_obj.status = Table.Status.LIBRE
        table_obj.session_token = None
        table_obj.needs_assistance = False
        table_obj.save(update_fields=['status', 'session_token', 'needs_assistance'])

        # WS CLIENTE (MESA CERRADA)
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"table_{table_obj.code}",
                {
                    "type": "table.status.update",
                    "data": {"type": "TABLE_CLOSED", "message": "Mesa cerrada"}
                }
            )
        except Exception:
            pass

        return Response({"detail": "Mesa cerrada.", "total_billed": total}, status=drf_status.HTTP_200_OK)

    def send_websocket_update(self, order_data):
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                KITCHEN_GROUP_NAME, {"type": "send.status.update", "order": order_data}
            )
        except Exception as e:
            print(f"Error WS: {e}")


# --- VISTAS CLIENTE ---
class CustomerViewSet(viewsets.GenericViewSet):
    permission_classes = []

    @action(detail=False, methods=['get'], url_path='table/(?P<code>[^/.]+)')
    def check_session(self, request, code=None):
        try:
            table = Table.objects.get(code=code)
        except Table.DoesNotExist:
            return Response({"detail": "Mesa no existe"}, status=404)

        recent_paid_orders = Order.objects.filter(
            table=table, status=Order.Status.PAID, updated_at__gte=timezone.now() - timedelta(minutes=30)
        )
        can_rate = recent_paid_orders.exists() and table.status == 'LIBRE'
        data = PublicTableSerializer(table).data
        data['can_rate'] = can_rate

        if table.status == 'OCUPADA':
            data['session_token'] = table.session_token

        if can_rate:
            items = []
            seen = set()
            for order in recent_paid_orders:
                for item in order.items.all():
                    if item.product_name not in seen:
                        items.append({"item_id": item.id, "product_name": item.product_name, "order_id": order.id})
                        seen.add(item.product_name)
            data['items_to_rate'] = items

        return Response(data)

    @action(detail=False, methods=['post'], url_path='table/(?P<code>[^/.]+)/call')
    def call_waiter(self, request, code=None):
        try:
            table = Table.objects.get(code=code)
        except Table.DoesNotExist:
            return Response(status=404)

        client_token = request.data.get('token')
        if str(table.session_token) != str(client_token):
            return Response({"detail": "Sesión inválida."}, status=403)

        table.needs_assistance = True
        table.save(update_fields=['needs_assistance'])

        # WS PARA AVISAR AL MESERO QUE EL CLIENTE LLAMA
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "kitchen",  # Usamos el grupo 'kitchen' porque los meseros también escuchan ahí
                {
                    "type": "waiter.call",
                    "table_code": table.code,
                    "status": "ON"  # Encender alerta
                }
            )
        except Exception:
            pass

        return Response({"detail": "Mesero notificado"})

    @action(detail=False, methods=['post'], url_path='rate')
    def rate_item(self, request):
        serializer = ReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Gracias!"})
        return Response(serializer.errors, status=400)


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.all().order_by("category", "name")
        cat = self.request.query_params.get("category")
        if cat: qs = qs.filter(category=cat)
        return qs


class TableViewSet(viewsets.ModelViewSet):
    serializer_class = TableSerializer
    queryset = Table.objects.all()

    def get_queryset(self):
        qs = Table.objects.all().order_by("code")
        active = self.request.query_params.get("active")
        status_param = self.request.query_params.get("status")
        if active in ("1", "true", "True"): qs = qs.filter(is_active=True)
        if status_param: qs = qs.filter(status=status_param)
        return qs

    # --- AQUÍ ESTÁ LA CORRECCIÓN CRUCIAL ---
    @action(detail=True, methods=['post'])
    def mark_attended(self, request, pk=None):
        table = self.get_object()
        table.needs_assistance = False
        table.save()

        # 1. AVISAR AL CLIENTE (QR) -> "El mesero viene"
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"table_{table.code}",
                {
                    "type": "table.status.update",
                    "data": {
                        "type": "WAITER_COMING",
                        "message": "El mesero va en camino."
                    }
                }
            )
        except Exception:
            pass

        # 2. AVISAR A OTROS MESEROS -> Apagar alerta naranja
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "kitchen",
                {
                    "type": "waiter.call",
                    "table_code": table.code,
                    "status": "OFF"
                }
            )
        except Exception:
            pass

        return Response({'status': 'attended'})


class DashboardViewSet(viewsets.ViewSet):
    """
    Versión con CÁLCULO MANUAL para asegurar compatibilidad total con fechas.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        # 1. TRAER PEDIDOS (Pagados o Entregados)
        target_statuses = [Order.Status.PAID, Order.Status.DELIVERED]

        # Traemos TODOS los objetos ordenados.
        # Nota: Al no usar .values() ni .annotate() de la DB, evitamos el error de SQLite.
        orders = Order.objects.filter(status__in=target_statuses).order_by('created_at')

        # --- VARIABLES PARA ACUMULAR DATOS ---
        total_sales = Decimal('0.00')
        sales_by_date_dict = {}  # Ejemplo: {"2025-11-26": 50.00}

        prep_times = []  # Lista de segundos
        prep_times_by_product = {}  # {"Hamburguesa": [600, 500]}

        product_counts = {}  # {"Jugo": 5}

        # --- BUCLE PRINCIPAL (Procesamos en Python) ---
        for order in orders:
            # A. Ventas Totales
            total_sales += order.total_price

            # B. Historial de Ventas
            if order.created_at:
                # Convertimos a string "YYYY-MM-DD" respetando zona horaria local
                local_date = timezone.localtime(order.created_at).strftime("%Y-%m-%d")

                if local_date not in sales_by_date_dict:
                    sales_by_date_dict[local_date] = Decimal('0.00')
                sales_by_date_dict[local_date] += order.total_price

            # C. Productos y Tiempos
            # (Nota: Esto hace consultas adicionales, pero para reportes de admin es aceptable)
            items = order.items.all()

            for item in items:
                # Conteo Top Productos
                p_name = item.product_name
                if p_name not in product_counts:
                    product_counts[p_name] = 0
                product_counts[p_name] += 1

                # Tiempos (Solo si la orden tiene inicio y fin)
                if order.ready_at and order.created_at:
                    duration = (order.ready_at - order.created_at).total_seconds()
                    prep_times.append(duration)

                    if p_name not in prep_times_by_product:
                        prep_times_by_product[p_name] = []
                    prep_times_by_product[p_name].append(duration)

        # --- FORMATO DE SALIDA PARA EL FRONTEND ---

        # 1. Historial de Ventas (Lista ordenada)
        sales_history = [
            {"date": date, "total": total}
            for date, total in sales_by_date_dict.items()
        ]
        sales_history.sort(key=lambda x: x['date'])  # Ordenar cronológicamente

        # 2. KPI: Tiempo Promedio Global (minutos)
        avg_minutes = 0
        if prep_times:
            avg_seconds = sum(prep_times) / len(prep_times)
            avg_minutes = round(avg_seconds / 60, 1)

        # 3. Gráfico: Tiempo por Producto
        prep_time_chart = []
        for name, times in prep_times_by_product.items():
            avg_prod_seconds = sum(times) / len(times)
            prep_time_chart.append({
                "product": name,
                "minutes": round(avg_prod_seconds / 60, 1)
            })
        # Ordenar los más lentos primero y tomar Top 10
        prep_time_chart.sort(key=lambda x: x['minutes'], reverse=True)
        prep_time_chart = prep_time_chart[:10]

        # 4. Top Ventas
        top_products_list = [
            {"product_name": name, "total": count}
            for name, count in product_counts.items()
        ]
        top_products_list.sort(key=lambda x: x['total'], reverse=True)
        top_products_list = top_products_list[:5]

        return Response({
            "kpi": {
                "total_sales": total_sales,
                "orders_count": orders.count(),
                "avg_prep_time_minutes": avg_minutes,
            },
            "top_products": top_products_list,
            "prep_time_by_product": prep_time_chart,
            "sales_history": sales_history
        })