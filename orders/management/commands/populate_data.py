import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from orders.models import Product, Table, Order, OrderItem


class Command(BaseCommand):
    help = 'Genera datos dummy históricos para probar el Dashboard'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando generación de datos falsos...'))

        if Product.objects.count() == 0:
            self.stdout.write("Creando productos base...")
            products_data = [
                ("Jugo de Fresa", "JUICE", 12.00),
                ("Jugo de Mango", "JUICE", 14.00),
                ("Jugo de Papaya", "JUICE", 10.00),
                ("Surtido Especial", "JUICE", 15.00),
                ("Hamburguesa Royal", "SANDWICH", 25.00),
                ("Hamburguesa Clásica", "SANDWICH", 18.00),
                ("Club Sandwich", "SANDWICH", 28.00),
                ("Pollo Deshilachado", "SANDWICH", 16.00),
            ]
            for name, cat, price in products_data:
                Product.objects.create(name=name, category=cat, base_price=Decimal(price))

        products = list(Product.objects.all())

        # 2. ASEGURAR MESAS
        if Table.objects.count() == 0:
            self.stdout.write("Creando mesas...")
            for i in range(1, 11):
                Table.objects.create(code=f"M-{i:02d}", status='LIBRE')

        tables = list(Table.objects.all())

        # 3. GENERAR PEDIDOS HISTÓRICOS
        # Generaremos 100 pedidos en los últimos 30 días
        TOTAL_ORDERS = 100

        for _ in range(TOTAL_ORDERS):
            # A. Elegir fecha aleatoria en el pasado (entre hace 30 días y hoy)
            days_ago = random.randint(0, 30)
            # Hora aleatoria entre 8am y 10pm
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)

            # Fecha base de creación (Created At)
            fake_created = timezone.now() - timedelta(days=days_ago)
            fake_created = fake_created.replace(hour=hour, minute=minute)

            # B. Calcular tiempos realistas
            # Prep time: entre 5 y 25 minutos después de crear
            prep_minutes = random.randint(5, 25)
            fake_ready = fake_created + timedelta(minutes=prep_minutes)

            # Delivery time: entre 1 y 10 minutos después de estar listo
            deliver_minutes = random.randint(1, 10)
            fake_delivered = fake_ready + timedelta(minutes=deliver_minutes)

            # Pay time: entre 10 y 60 minutos después de entregar (el cliente come)
            pay_minutes = random.randint(10, 60)
            fake_paid = fake_delivered + timedelta(minutes=pay_minutes)

            # C. Crear la orden
            table = random.choice(tables)

            order = Order.objects.create(
                table=table,
                status=Order.Status.PAID,  # Para que salga en los reportes
                total_price=Decimal('0.00')
            )

            # IMPORTANTE: Django auto_now_add sobreescribe la fecha al crear.
            # Debemos forzar la actualización manual de las fechas después de crear.
            order.created_at = fake_created
            order.preparing_at = fake_created + timedelta(minutes=1)
            order.ready_at = fake_ready
            order.delivered_at = fake_delivered
            order.paid_at = fake_paid

            # D. Agregar Items (1 a 4 productos por pedido)
            num_items = random.randint(1, 4)
            order_total = Decimal('0.00')

            for _ in range(num_items):
                prod = random.choice(products)
                qty = 1  # Simplificamos a cantidad 1 por item row

                OrderItem.objects.create(
                    order=order,
                    product_name=prod.name,
                    unit_price=prod.base_price,
                    notes="Generado automáticamente"
                )
                order_total += prod.base_price

            # Actualizar precio y guardar fechas forzadas
            order.total_price = order_total
            order.save()

        self.stdout.write(self.style.SUCCESS(f'¡Éxito! Se generaron {TOTAL_ORDERS} pedidos históricos.'))