from django.db import models


class Table(models.Model):
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'Nuevo'
        PREPARING = 'PREPARING', 'En preparación'
        READY = 'READY', 'Listo'

    table = models.ForeignKey('Table', on_delete=models.PROTECT, related_name='orders', null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - Mesa {self.table.code} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)
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
