"""
URL configuration for AgriConnect project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.conf.urls.static import static

@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """Health check endpoint for deployment monitoring and Docker health checks."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'AgriConnect',
        'version': '1.0.0'
    })

urlpatterns = [
    path('health/', health_check, name='health'),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
