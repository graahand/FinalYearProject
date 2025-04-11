from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
import io
import base64
from django.utils import timezone
import logging
from .models import ImageAnalysis, DetectedObject
from transformers import AutoModelForCausalLM, AutoProcessor
import os
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
import json
from django.urls import reverse
from django.db import connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up VIPS path
vips_bin_path = "/home/putu/Documents/vips-dev-w64-web-8.16.1/vips-dev-8.16/bin"
os.environ["PATH"] = vips_bin_path + os.pathsep + os.environ["PATH"]
logger.info(f"Added VIPS path: {vips_bin_path}")

# Initialize the model at module level
moondream_model = None
processor = None

def initialize_moondream_model():
    global moondream_model, processor
    try:
        processor = AutoProcessor.from_pretrained("vikhyatk/moondream2", trust_remote_code=True)
        moondream_model = AutoModelForCausalLM.from_pretrained("vikhyatk/moondream2", trust_remote_code=True)
        logger.info("Successfully loaded Moondream2 model via transformers")
        return True
    except Exception as e:
        logger.error(f"Error loading Moondream2 model via transformers: {e}")
        return False

# Try to initialize the model when the module is loaded
initialize_moondream_model()

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

def process_image(request):
    """Process uploaded image and return analysis results."""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    # Log request details for debugging
    logger.info(f"Request method: {request.method}")
    logger.info(f"Files in request: {request.FILES}")
    logger.info(f"POST data: {request.POST}")

    try:
        # Check if model is initialized
        if moondream_model is None:
            logger.error("Model not initialized")
            return JsonResponse({"error": "Model not initialized. Please try again later."}, status=500)

        # Get the image file
        image_file = request.FILES.get('image')
        if not image_file:
            logger.error("No image file in request")
            return JsonResponse({"error": "No image file provided"}, status=400)

        # Validate file type
        if not image_file.content_type.startswith('image/'):
            logger.error(f"Invalid file type: {image_file.content_type}")
            return JsonResponse({"error": "Invalid file type. Please upload an image file."}, status=400)

        # Get query text if provided
        query_text = request.POST.get('query_text', '').strip()
        logger.info(f"Query text: {query_text}")

        try:
            # Open and validate image
            image = Image.open(image_file).convert("RGB")
            
            # Create two versions:
            # 1. 512x512 for model processing
            image_for_model = image.copy()
            image_for_model.thumbnail((512, 512), Image.Resampling.LANCZOS)
            
            # 2. 640x480 for display
            display_image = image.copy()
            display_image.thumbnail((640, 480), Image.Resampling.LANCZOS)
            
            # Convert display version to base64
            buffered = io.BytesIO()
            display_image.save(buffered, format="JPEG", quality=90)
            img_str = base64.b64encode(buffered.getvalue()).decode()

            try:
                # Use the model version for processing
                short_caption = moondream_model.caption(image_for_model, length="short")["caption"]
                normal_caption = "".join(moondream_model.caption(image_for_model, length="normal", stream=True)["caption"])
                
                # Handle the query if provided
                query_result = None
                if query_text:
                    query_result = moondream_model.query(image_for_model, query_text)["answer"]
                
                # Save to database
                analysis = ImageAnalysis.objects.create(
                    image=image_file,
                    short_caption=short_caption,
                    normal_caption=normal_caption,
                    query_text=query_text if query_text else None,
                    query_result=query_result,
                    upload_date=timezone.now()
                )

                # Prepare response data
                response_data = {
                    'status': 'success',
                    'analysis_id': analysis.id,
                    'image_url': f"data:image/jpeg;base64,{img_str}",
                    'short_caption': short_caption,
                    'normal_caption': normal_caption,
                    'visual_query': query_result if query_result else "No query provided"
                }

                logger.info("Successfully processed image")
                return JsonResponse(response_data)

            except Exception as e:
                logger.error(f"Error in model processing: {str(e)}")
                return JsonResponse({"error": f"Error analyzing image content: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return JsonResponse({"error": f"Error processing image: {str(e)}"}, status=500)

    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)

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