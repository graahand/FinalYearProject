from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
import io
import base64
from django.utils import timezone
import logging
from .models import ImageAnalysis, DetectedObject
import os
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
import json
from django.urls import reverse
from django.db import connection
import torch
from django.core.cache import cache
from asgiref.sync import async_to_sync
import asyncio
import torch.multiprocessing as mp
from .model_handler import ModelHandler
try:
    import django_rq
except ImportError:
    raise ImportError("Please install django-rq: pip install django-rq")

# Set multiprocessing start method
mp.set_start_method('spawn', force=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up VIPS path
vips_bin_path = "/home/putu/Documents/vips-dev-w64-web-8.16.1/vips-dev-8.16/bin"
os.environ["PATH"] = vips_bin_path + os.pathsep + os.environ["PATH"]
logger.info(f"Added VIPS path: {vips_bin_path}")

def home(request):
    """Render the home page."""
    try:
        # Get the most recent analyses
        analyses = ImageAnalysis.objects.order_by('-upload_date')[:5]
        
        # Prepare context data
        context = {
            'analyses': analyses,
            'page_title': 'Home',
            'is_home': True  # Flag to identify home page in template
        }
        
        # Render the home template
        return render(request, 'blog/home.html', context)
    except Exception as e:
        logger.error(f"Error in home view: {str(e)}")
        return render(request, 'blog/home.html', {
            'analyses': [],
            'error': str(e),
            'page_title': 'Home',
            'is_home': True
        })

def history(request):
    """View function for the history page."""
    try:
        analyses = ImageAnalysis.objects.select_related().order_by('-upload_date')
        return render(request, 'blog/history.html', {'analyses': analyses})
    except Exception as e:
        logger.error(f"Error in history view: {str(e)}")
        return render(request, 'blog/history.html', {'analyses': [], 'error': str(e)})

def process_image_task(image_file):
    """Background task for processing images."""
    try:
        # Get model handler instance
        model_handler = ModelHandler.get_instance()
        
        # Process image
        image = Image.open(image_file).convert("RGB")
        logger.info(f"Processing image: {image_file}")
        
        # Generate captions and query result
        short_caption = model_handler.generate_short_caption(image)
        normal_caption = model_handler.generate_normal_caption(image)
        query_result = model_handler.process_query(image)
        
        # Create analysis record
        analysis = ImageAnalysis.objects.create(
            image=image_file,
            short_caption=short_caption,
            normal_caption=normal_caption,
            query_result=query_result
        )
        
        logger.info(f"Created analysis record with ID: {analysis.id}")
        return analysis.id
    except Exception as e:
        logger.error(f"Error in process_image_task: {str(e)}")
        return None

def process_image(request):
    """Handle image upload and processing."""
    try:
        if 'image' not in request.FILES:
            return JsonResponse({'error': 'No image file provided'}, status=400)
            
        # Get the image file
        image_file = request.FILES['image']
        
        # Get optional query text
        query_text = request.POST.get('query_text', '')
        
        # Enqueue the job
        queue = django_rq.get_queue('default')
        job = queue.enqueue(
            process_image_task,
            image_file,
            job_timeout=600  # 10 minutes timeout
        )
        
        # Return the job ID and initial response
        return JsonResponse({
            'job_id': job.id,
            'status': 'processing',
            'message': 'Image uploaded and processing started'
        })
        
    except Exception as e:
        logger.error(f"Error in process_image view: {str(e)}")
        return JsonResponse({
            'error': 'Error processing image',
            'details': str(e)
        }, status=500)

def login_view(request):
    # Check if user is already logged in
    if request.user.is_authenticated:
        logger.info(f"User {request.user.username} is already authenticated, redirecting to dashboard")
        return redirect('blog:admin_dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Log authentication attempt with detailed information
        logger.info(f"Login attempt for user: {username}")
        logger.info(f"CSRF verification: {request.META.get('CSRF_COOKIE', 'Not found')} - Token: {request.POST.get('csrfmiddlewaretoken', 'Not found')}")
        
        # Check if username and password are provided
        if not username or not password:
            logger.error("Username or password not provided")
            messages.error(request, 'Please provide both username and password')
            return render(request, 'blog/login.html')
            
        # Attempt authentication
        user = authenticate(request, username=username, password=password)
        
        logger.info(f"Authentication result for {username}: {'Success' if user else 'Failed'}")
        
        if user is not None:
            logger.info(f"Authentication successful for user: {username}")
            # Log user details to verify they exist
            logger.info(f"User details - ID: {user.id}, Username: {user.username}, Is Staff: {user.is_staff}, Is Superuser: {user.is_superuser}")
            
            # Explicitly log the user in
            login(request, user)
            
            # Verify user is now logged in
            logger.info(f"After login: User authenticated: {request.user.is_authenticated}, Username: {request.user.username}")
            
            # Add success message
            messages.success(request, f'Welcome, {username}!')
            
            # Use reverse to ensure correct URL
            dashboard_url = reverse('blog:admin_dashboard')
            logger.info(f"Redirecting to: {dashboard_url}")
            
            # Redirect to admin dashboard
            return redirect(dashboard_url)
        else:
            logger.error(f"Authentication failed for user: {username}")
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'blog/login.html')

def logout_view(request):
    logout(request)
    return redirect('blog:login')

@login_required(login_url='blog:login')
def admin_dashboard(request):
    """Render the admin dashboard with analytics."""
    try:
        # Log that we've reached the dashboard and authentication status
        logger.info(f"Admin dashboard accessed by user: {request.user.username}")
        logger.info(f"User authenticated: {request.user.is_authenticated}, Is staff: {request.user.is_staff}")
        
        # Proceed with dashboard data
        total_analyses = ImageAnalysis.objects.count()
        recent_analyses = ImageAnalysis.objects.select_related().order_by('-upload_date')[:5]
        
        # Calculate additional analytics data
        week_ago = timezone.now() - timedelta(days=7)
        recent_analyses_count = ImageAnalysis.objects.filter(upload_date__gte=week_ago).count()
        
        # Safely handle object counts - setting defaults 
        total_objects = 0
        recent_objects_count = 0
        
        # Set safe counts for recent analyses
        for analysis in recent_analyses:
            # Safely add object_count attribute for template use
            analysis.object_count = 0
        
        # Calculate success rate (assume all completed analyses are successful)
        success_rate = 100  # Default to 100% success
        recent_success_rate = 100
        
        context = {
            'total_analyses': total_analyses,
            'total_objects': total_objects,
            'recent_analyses': recent_analyses,
            'recent_analyses_count': recent_analyses_count,
            'recent_objects_count': recent_objects_count,
            'success_rate': success_rate,
            'recent_success_rate': recent_success_rate,
            'user': request.user,  # Make user available in template
        }
        return render(request, 'blog/admin_dashboard.html', context)
    except Exception as e:
        logger.error(f"Error in admin_dashboard view: {str(e)}")
        return render(request, 'blog/admin_dashboard.html', {
            'total_analyses': 0,
            'total_objects': 0,
            'recent_analyses': [],
            'recent_analyses_count': 0,
            'recent_objects_count': 0,
            'success_rate': 0,
            'recent_success_rate': 0,
            'error': str(e),
            'user': request.user,  # Make user available in template
        })

@login_required(login_url='blog:login')
def image_analyses(request):
    """Display list of all image analyses."""
    analyses = ImageAnalysis.objects.order_by('-upload_date')
    return render(request, 'blog/image_analyses.html', {'analyses': analyses})

@login_required
def analysis_list(request):
    try:
        analyses = ImageAnalysis.objects.all().order_by('-upload_date')
        
        # Prefetch related data safely
        for analysis in analyses:
            try:
                # Set a safe count attribute
                analysis.object_count = 0
            except Exception as e:
                logger.error(f"Error accessing detected objects for analysis {analysis.id}: {str(e)}")
                analysis.object_count = 0
                
        return render(request, 'blog/analysis_list.html', {'analyses': analyses})
    except Exception as e:
        logger.error(f"Error in analysis_list view: {str(e)}")
        return render(request, 'blog/analysis_list.html', {'analyses': [], 'error': str(e)})

@login_required
def analysis_detail(request, pk):
    try:
        analysis = get_object_or_404(ImageAnalysis, pk=pk)
        # Set empty queryset for detected objects due to schema mismatch
        detected_objects = []
        return render(request, 'blog/analysis_detail.html', {
            'analysis': analysis,
            'detected_objects': detected_objects
        })
    except Exception as e:
        logger.error(f"Error in analysis_detail view: {str(e)}")
        return render(request, 'blog/analysis_detail.html', {
            'error': str(e)
        })

@login_required
def analysis_delete(request, pk):
    if request.method == 'POST':
        analysis = get_object_or_404(ImageAnalysis, pk=pk)
        analysis.delete()
        messages.success(request, 'Analysis deleted successfully')
        return redirect('blog:analysis_list')
    return redirect('blog:analysis_list')

def get_model_prediction(image):
    cache_key = f"image_analysis_{hash(image.tobytes())}"
    result = cache.get(cache_key)
    if result is None:
        model_handler = ModelHandler.get_instance()
        result = model_handler.process_query(image)
        cache.set(cache_key, result, timeout=3600)
    return result

def optimize_image(image):
    # Use PIL's optimize flag
    optimized = image.copy()
    optimized.thumbnail((512, 512), Image.Resampling.BILINEAR)  # Faster than LANCZOS
    return optimized

def process_with_model(image):
    """Process an image with the Moondream model."""
    try:
        model_handler = ModelHandler.get_instance()
        result = model_handler.process_query(image)
        return result
    except Exception as e:
        logger.error(f"Error in process_with_model: {str(e)}")
        return None

async def generate_short_caption(image):
    """Generate a short caption for the image."""
    try:
        model_handler = ModelHandler.get_instance()
        result = model_handler.generate_short_caption(image)
        logger.info(f"Generated short caption: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in generate_short_caption: {str(e)}")
        return "Error generating short caption"

async def generate_normal_caption(image):
    """Generate a detailed caption for the image."""
    try:
        model_handler = ModelHandler.get_instance()
        result = model_handler.generate_normal_caption(image)
        logger.info(f"Generated normal caption: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in generate_normal_caption: {str(e)}")
        return "Error generating detailed caption"

async def process_query(image, query="What is in this image?"):
    """Process a specific query about the image."""
    try:
        model_handler = ModelHandler.get_instance()
        result = model_handler.process_query(image, query)
        logger.info(f"Generated query response: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in process_query: {str(e)}")
        return f"Error processing query: {query}"

def check_job_status(request, job_id):
    """Check the status of a background job."""
    try:
        # Get the job from Redis
        job = django_rq.get_queue().fetch_job(job_id)
        
        if job is None:
            return JsonResponse({
                'status': 'failed',
                'error': 'Job not found'
            }, status=404)
            
        if job.is_failed:
            return JsonResponse({
                'status': 'failed',
                'error': str(job.exc_info)
            })
            
        if job.is_finished:
            # Get the analysis ID from the job result
            analysis_id = job.result
            
            if analysis_id is None:
                return JsonResponse({
                    'status': 'failed',
                    'error': 'Processing failed'
                })
                
            # Get the analysis object
            try:
                analysis = ImageAnalysis.objects.get(id=analysis_id)
                return JsonResponse({
                    'status': 'completed',
                    'image_url': analysis.image.url,
                    'short_caption': analysis.short_caption,
                    'normal_caption': analysis.normal_caption,
                    'query_result': analysis.query_result
                })
            except ImageAnalysis.DoesNotExist:
                return JsonResponse({
                    'status': 'failed',
                    'error': 'Analysis not found'
                })
                
        # Job is still in progress
        return JsonResponse({
            'status': 'processing',
            'message': 'Image is still being processed'
        })
        
    except Exception as e:
        logger.error(f"Error checking job status: {str(e)}")
        return JsonResponse({
            'status': 'failed',
            'error': str(e)
        }, status=500) 