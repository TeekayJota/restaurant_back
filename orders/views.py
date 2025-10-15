# orders/views.py
from rest_framework import viewsets, mixins, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as drf_status

from .models import Order, Product, Table
from .serializers import OrderSerializer, ProductSerializer, TableSerializer


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = (
            Order.objects
            .select_related("table")
            .prefetch_related("items")
            .order_by("-created_at")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=True, methods=["patch"])
    def set_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")
        valid = {c[0] for c in Order.Status.choices}
        if new_status not in valid:
            return Response(
                {"detail": "status inválido"},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        order.status = new_status
        order.save(update_fields=["status"])
        return Response(self.get_serializer(order).data)


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.all().order_by("category", "name")
        cat = self.request.query_params.get("category")
        q = self.request.query_params.get("q")
        if cat:
            qs = qs.filter(category=cat)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class TableListView(generics.ListAPIView):
    serializer_class = TableSerializer

    def get_queryset(self):
        qs = Table.objects.all().order_by("code")
        active = self.request.query_params.get("active")
        if active in ("1", "true", "True"):
            qs = qs.filter(is_active=True)
        return qs
