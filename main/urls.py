# main/urls.py
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings

# 1. IMPORTAR VISTAS DE JWT
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from orders.views import OrderViewSet, ProductListView, TableViewSet, CustomerViewSet, DashboardViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'customer', CustomerViewSet, basename='customer')
router.register(r'tables', TableViewSet, basename='tables')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/products/", ProductListView.as_view()),

    # --- 2. NUEVAS RUTAS DE AUTENTICACIÓN ---
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # Login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Refrescar sesión
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()