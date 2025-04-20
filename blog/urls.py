from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'blog'  # Namespace for main site URLs

# Main site URL patterns
urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('history/', views.history, name='history'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    
    # Image processing
    path('process-image/', views.process_image, name='process_image'),
    
    # Admin/Dashboard pages
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('analyses/', views.image_analyses, name='image_analyses'),
    path('analysis/list/', views.analysis_list, name='analysis_list'),
    path('analysis/<int:pk>/', views.analysis_detail, name='analysis_detail'),
    path('analysis/<int:pk>/delete/', views.analysis_delete, name='analysis_delete'),
    path('check-job/<str:job_id>/', views.check_job_status, name='check_job_status'),
]