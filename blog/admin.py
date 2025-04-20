from django.contrib import admin
from django.utils.html import format_html
from .models import ImageAnalysis, DetectedObject, UserProfile

class DetectedObjectInline(admin.TabularInline):
    model = DetectedObject
    extra = 0
    readonly_fields = ['label', 'confidence', 'x_min', 'y_min', 'x_max', 'y_max']
    fields = ['label', 'confidence', 'position']
    
    def position(self, obj):
        return f"({obj.x_min:.2f}, {obj.y_min:.2f}) to ({obj.x_max:.2f}, {obj.y_max:.2f})"
    
    position.short_description = "Bounding Box"

@admin.register(ImageAnalysis)
class ImageAnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'thumbnail', 'short_caption_preview', 'upload_date']
    list_display_links = ['id', 'thumbnail']
    search_fields = ['short_caption', 'query_text', 'query_result']
    list_filter = ['upload_date']
    readonly_fields = ['image_preview', 'upload_date', 'short_caption', 'query_text', 'query_result']
    fieldsets = [
        ('Image', {
            'fields': ['image', 'image_preview', 'upload_date']
        }),
        ('Generated Content', {
            'fields': ['short_caption'],
            'classes': ['wide']
        }),
        ('Visual Query', {
            'fields': ['query_text', 'query_result'],
            'classes': ['wide']
        })
    ]
    inlines = [DetectedObjectInline]
    
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No Image"
    
    thumbnail.short_description = "Image"
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 500px; max-height: 500px;" />', obj.image.url)
        return "No Image"
    
    image_preview.short_description = "Image Preview"
    
    def short_caption_preview(self, obj):
        if obj.short_caption:
            # Truncate long captions for the list view
            max_length = 50
            return (obj.short_caption[:max_length] + '...') if len(obj.short_caption) > max_length else obj.short_caption
        return "No caption"
    
    short_caption_preview.short_description = "Caption"


@admin.register(DetectedObject)
class DetectedObjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'label', 'confidence_display', 'analysis_link']
    list_filter = ['label']
    search_fields = ['label']
    
    def confidence_display(self, obj):
        # Show confidence as percentage
        return f"{obj.confidence * 100:.1f}%"
    
    confidence_display.short_description = "Confidence"
    
    def analysis_link(self, obj):
        if obj.image_analysis:
            return format_html('<a href="{}">{}</a>', 
                          f"/admin/blog/imageanalysis/{obj.image_analysis.id}/change/", 
                          f"Analysis #{obj.image_analysis.id}")
        return "No image analysis"
    
    analysis_link.short_description = "Analysis"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['username', 'full_name', 'email', 'display_profile_pic', 'date_joined']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    list_filter = ['date_joined']
    readonly_fields = ['date_joined', 'user', 'profile_pic_preview']
    
    def username(self, obj):
        return obj.user.username
    
    def full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    
    def email(self, obj):
        return obj.user.email
    
    def display_profile_pic(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 50%;" />', obj.profile_picture.url)
        return "No Image"
    
    display_profile_pic.short_description = "Profile Picture"
    
    def profile_pic_preview(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" style="max-width: 300px; max-height: 300px;" />', obj.profile_picture.url)
        return "No Image"
    
    profile_pic_preview.short_description = "Profile Picture Preview"
