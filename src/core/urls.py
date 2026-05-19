"""
URL configuration for core project.

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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from subscription.webhooks import easypay_webhook
from core.admin_dummy_data import import_dummy_data_view

urlpatterns = [
    path('admin/import-dummy-data/', import_dummy_data_view, name='import_dummy_data'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('courses/', include('course.urls')),
    path('plans/', include('subscription.urls')),
    path('exams/', include('exam.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('api/webhook/easypay/', easypay_webhook, name='easypay_webhook_root'),
    path('api/webhook/easypay/<str:api_key>/', easypay_webhook, name='easypay_webhook_with_key'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
