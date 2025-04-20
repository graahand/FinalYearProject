from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
import io
import base64
from django.utils import timezone
import logging
from .models import ImageAnalysis, DetectedObject, UserProfile
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
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
from .speech_to_text import SpeechRecognizer
import threading

# Set multiprocessing start method
mp.set_start_method('spawn', force=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up VIPS path
vips_bin_path = "/home/putu/Documents/vips-dev-w64-web-8.16.1/vips-dev-8.16/bin"
os.environ["PATH"] = vips_bin_path + os.pathsep + os.environ["PATH"]
logger.info(f"Added VIPS path: {vips_bin_path}")

# Create a global speech recognizer instance with a shorter timeout
speech_recognizer = None
speech_lock = threading.Lock()

def get_speech_recognizer():
    global speech_recognizer
    if speech_recognizer is None:
        try:
            speech_recognizer = SpeechRecognizer(recording_time=15)
            logger.info("Speech recognizer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize speech recognizer: {str(e)}")
    return speech_recognizer

def home(request):
    """Render the home page."""
    try:
        # Get analyses based on authentication status
        if request.user.is_authenticated:
            # Get the most recent analyses for the logged-in user
            analyses = ImageAnalysis.objects.filter(user=request.user).order_by('-upload_date')[:5]
        else:
            # No analyses for unauthenticated users
            analyses = []
        
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

def process_image_task(image_file, query_text="", user_id=None):
    """Background task for processing images."""
    try:
        # Get model handler instance
        model_handler = ModelHandler.get_instance()
        
        # Process image
        image = Image.open(image_file).convert("RGB")
        logger.info(f"Processing image: {image_file}")
        
        # Generate short caption 
        short_caption = model_handler.generate_short_caption(image)
        
        # Process the query if provided, otherwise use default query
        if query_text.strip():
            logger.info(f"Processing custom query: {query_text}")
            query_result = model_handler.process_query(image, query_text)
        else:
            # Only generate the caption without a specific query
            query_result = None
        
        # Create analysis record
        analysis_data = {
            'image': image_file,
            'short_caption': short_caption,
            'query_text': query_text if query_text.strip() else None,
            'query_result': query_result
        }
        
        # Associate with user if user_id is provided
        if user_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(id=user_id)
                analysis_data['user'] = user
                logger.info(f"Associating analysis with user: {user.username}")
            except User.DoesNotExist:
                logger.warning(f"User with ID {user_id} not found")
        
        analysis = ImageAnalysis.objects.create(**analysis_data)
        
        logger.info(f"Created analysis record with ID: {analysis.id}")
        return analysis.id
    except Exception as e:
        logger.error(f"Error in process_image_task: {str(e)}")
        return None

@login_required(login_url='blog:login')
def process_image(request):
    """Handle image upload and processing."""
    try:
        if 'image' not in request.FILES:
            return JsonResponse({'error': 'No image file provided'}, status=400)
            
        # Get the image file
        image_file = request.FILES['image']
        
        # Get optional query text
        query_text = request.POST.get('query_text', '')
        
        # Get user ID if user is authenticated
        user_id = request.user.id
        logger.info(f"Processing image for user: {request.user.username}")
        
        # Enqueue the job with required arguments
        try:
            queue = django_rq.get_queue('default')
            job = queue.enqueue(
                'blog.views.process_image_task',  # Use string reference to avoid import issues
                args=(image_file, query_text, user_id),  # Pass user_id as third argument
                job_timeout=1200,  # 20 minutes timeout (increased from 10)
                result_ttl=86400  # Results stored for 24 hours
            )
            
            # Return the job ID and initial response
            return JsonResponse({
                'job_id': job.id,
                'status': 'processing',
                'message': 'Image uploaded and processing started'
            })
        except Exception as redis_error:
            logger.error(f"Redis error: {str(redis_error)}")
            # Fall back to direct processing without Redis
            try:
                # Process directly without Redis
                analysis_id = process_image_task(image_file, query_text, user_id)
                if analysis_id:
                    analysis = ImageAnalysis.objects.get(id=analysis_id)
                    return JsonResponse({
                        'status': 'completed',
                        'message': 'Image processed directly (Redis unavailable)',
                        'image_url': analysis.image.url,
                        'short_caption': analysis.short_caption,
                        'query_text': analysis.query_text,
                        'query_result': analysis.query_result
                    })
                else:
                    return JsonResponse({
                        'status': 'failed',
                        'error': 'Failed to process image directly'
                    }, status=500)
            except Exception as direct_error:
                logger.error(f"Direct processing error: {str(direct_error)}")
                return JsonResponse({
                    'error': 'Error processing image (Redis and direct processing failed)',
                    'details': str(direct_error)
                }, status=500)
        
    except Exception as e:
        logger.error(f"Error in process_image view: {str(e)}")
        return JsonResponse({
            'error': 'Error processing image',
            'details': str(e)
        }, status=500)

def register(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect('blog:home')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Don't automatically log the user in
            messages.success(request, f'Account created successfully! Please log in.')
            # Redirect to login page instead of home
            return redirect('blog:login')
    else:
        form = UserRegistrationForm()
        
    return render(request, 'blog/register.html', {'form': form})

def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('blog:home')
        
    next_url = request.GET.get('next', 'blog:home')
        
    if request.method == 'POST':
        form = UserLoginForm(request=request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request=request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                # Use the next parameter if available, otherwise go to home
                next_page = request.POST.get('next', next_url)
                return redirect(next_page)
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
        
    context = {
        'form': form,
        'next': next_url,
    }
    return render(request, 'blog/login.html', context)

def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('blog:home')

@login_required(login_url='blog:login')
def profile(request):
    """Display and update user profile."""
    user_profile = request.user.profile
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('blog:profile')
    else:
        form = UserProfileForm(instance=user_profile)
        
    # Get user's analyses
    user_analyses = ImageAnalysis.objects.filter(user=request.user).order_by('-upload_date')[:5]
    
    context = {
        'form': form,
        'user_profile': user_profile,
        'user_analyses': user_analyses
    }
    
    return render(request, 'blog/profile.html', context)

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

# async def generate_normal_caption(image):
#     """Generate a detailed caption for the image."""
#     try:
#         model_handler = ModelHandler.get_instance()
#         # result = model_handler.generate_normal_caption(image)
#         logger.info(f"Generated normal caption: {result}")
#         return result
#     except Exception as e:
#         logger.error(f"Error in generate_normal_caption: {str(e)}")
#         return "Error generating detailed caption"

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
        try:
            job = django_rq.get_queue().fetch_job(job_id)
        except Exception as redis_error:
            logger.error(f"Redis error in check_job_status: {str(redis_error)}")
            return JsonResponse({
                'status': 'failed',
                'error': 'Redis connection error. Please try again.'
            }, status=500)
        
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
                    'query_text': analysis.query_text,
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

@csrf_exempt
@login_required
def speech_to_text(request):
    """Handle speech-to-text conversion."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            recognizer = get_speech_recognizer()
            if not recognizer:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Speech recognition service is not available'
                }, status=503)
            
            with speech_lock:  # Use lock to prevent concurrent access
                if action == 'start':
                    # Start the speech recognition
                    success = recognizer.start_recording()
                    return JsonResponse({
                        'status': 'recording' if success else 'error',
                        'message': 'Recording started' if success else 'Failed to start recording'
                    })
                
                elif action == 'stop':
                    # Stop the speech recognition
                    recognizer.stop_recording()
                    text = recognizer.get_text()
                    return JsonResponse({
                        'status': 'success',
                        'text': text
                    })
                    
                elif action == 'status':
                    # Get the current status
                    return JsonResponse({
                        'status': 'recording' if recognizer.is_recording else 'idle',
                        'text': recognizer.get_text()
                    })
                    
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid action'
                    }, status=400)
                    
        except Exception as e:
            logger.error(f"Error in speech_to_text view: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405) 