from django.db import models
from decimal import Decimal
from django.utils import timezone
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator


class Table(models.Model):
    class Status(models.TextChoices):
        LIBRE = 'LIBRE', 'Libre'
        OCUPADA = 'OCUPADA', 'Ocupada'

    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LIBRE)

    session_token = models.UUIDField(null=True, blank=True)
    needs_assistance = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code} ({self.get_status_display()})"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'Nuevo'
        WAITER_EDITING = 'WAITER_EDITING', 'Mesero Editando'
        PREPARING = 'PREPARING', 'En preparación'
        CHANGE_REQUESTED = 'CHANGE_REQUESTED', 'Cambio Solicitado'
        READY = 'READY', 'Listo'
        # --- ¡ESTE ES EL QUE FALTABA! ---
        DELIVERED = 'DELIVERED', 'Entregado'
        # --------------------------------
        PAID = 'PAID', 'Pagado'

    table = models.ForeignKey('Table', on_delete=models.PROTECT, related_name='orders', null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    total_price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    proposed_changes = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - Mesa {self.table.code} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True, null=True)
    selected_options = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.product_name} (Order #{self.order.id})"


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('JUICE', 'Jugos'),
        ('SANDWICH', 'Sandwiches'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    option_schema = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Review(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.order_item.product_name} ({self.rating} stars)"