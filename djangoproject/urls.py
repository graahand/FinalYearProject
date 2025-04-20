from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

def redirect_to_login_or_home(request):
    """Redirect to login page for non-authenticated users, home page for authenticated users."""
    if request.user.is_authenticated:
        return redirect('blog:home')
    else:
        return redirect('blog:login')

def redirect_process_image(request):
    # Redirect while preserving request method and data
    return redirect('/blog/process-image/', permanent=True)

urlpatterns = [
    # Redirect root URL to login page or home page based on authentication
    path('', redirect_to_login_or_home, name='root'),
    
    # Redirect old process-image URL to the correct one
    path('process-image/', csrf_exempt(redirect_process_image)),
    
    # Blog URLs
    path('blog/', include('blog.urls')),
    
    # Django admin
    path('admin/', admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Add static files handling during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)