from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.http import JsonResponse
from django.db import connection


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)

urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('studio.urls')),
]
