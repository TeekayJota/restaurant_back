"""
URL configuration for main project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings

# --- IMPORTACIÓN CORREGIDA ---
# Ahora importamos TableViewSet en lugar de TableListView
from orders.views import OrderViewSet, ProductListView, TableViewSet, CustomerViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'customer', CustomerViewSet, basename='customer')
router.register(r'tables', TableViewSet, basename='tables') # Registramos el ViewSet

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/products/", ProductListView.as_view()),
    # La antigua ruta de api/tables ya no es necesaria, el router la maneja
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()