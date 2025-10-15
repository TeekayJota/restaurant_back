from django.contrib import admin
from .models import Order, OrderItem, Product, Table

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "is_active")
    search_fields = ("code",)
    list_filter = ("is_active",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "base_price")
    list_filter = ("category",)
    search_fields = ("name", "description")
    ordering = ("category", "name")
    readonly_fields = ("option_schema",)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "status", "created_at")
    list_filter = ("status", "created_at")
    inlines = [OrderItemInline]
    ordering = ("-created_at",)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "notes")
    search_fields = ("product_name", "notes")
