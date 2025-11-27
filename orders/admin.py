from django.contrib import admin
from .models import Order, OrderItem, Product, Table, Review

# --- IMPORTACIONES PARA EXPORTAR A EXCEL ---
import openpyxl
import json
from django.http import HttpResponse
from django.utils import timezone


# --- ACCIÓN DE EXPORTAR A EXCEL (Ya la tenías) ---
@admin.action(description="Exportar seleccionados a Excel (XLSX)")
def export_to_excel(modeladmin, request, queryset):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Items de Pedidos"

    columns = ["Item ID", "Order ID", "Mesa", "Producto", "Precio Unitario", "Fecha de Creación"]
    ws.append(columns)

    for item in queryset:
        row_data = [
            item.id,
            item.order.id,
            str(item.order.table.code) if item.order.table else "N/A",
            item.product_name,
            item.unit_price,
            item.order.created_at.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M")
        ]
        ws.append(row_data)

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    filename = f"reporte_items_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response["Content-Disposition"] = f"attachment; filename={filename}"
    wb.save(response)
    return response


# --- REGISTROS DEL ADMIN ---

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    # Añadimos los campos nuevos para que puedas ver el token y si piden ayuda
    list_display = ("id", "code", "status", "needs_assistance", "is_active")
    search_fields = ("code",)
    list_filter = ("status", "needs_assistance", "is_active")
    readonly_fields = ("session_token",)  # El token es mejor que sea solo lectura


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
    fields = ('product_name', 'unit_price', 'notes', 'selected_options')
    readonly_fields = ('product_name', 'unit_price', 'notes', 'selected_options')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # --- AQUÍ AGREGAMOS LOS TIMESTAMPS PARA QUE SE VEAN EN LA LISTA ---
    list_display = (
        "id",
        "table",
        "status",
        "total_price",
        "created_at",
        "ready_at",  # Hora de listo
        "delivered_at"  # Hora de entrega
    )
    list_filter = ("status", "created_at")
    inlines = [OrderItemInline]
    ordering = ("-created_at",)
    # Hacemos que todos los tiempos sean visibles en el detalle
    readonly_fields = (
        'total_price', 'proposed_changes',
        'preparing_at', 'ready_at', 'delivered_at', 'paid_at'
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "unit_price", "notes")
    search_fields = ("product_name", "notes")
    actions = [export_to_excel]


# --- NUEVO REGISTRO: CALIFICACIONES (Reviews) ---
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "get_product_name", "rating", "comment", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "order_item__product_name")

    # Función auxiliar para mostrar el nombre del producto en la lista
    @admin.display(description='Producto')
    def get_product_name(self, obj):
        return obj.order_item.product_name