from django.contrib import admin
from django.utils.html import format_html
from .models import ImageAnalysis, DetectedObject

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
    search_fields = ['short_caption', 'normal_caption', 'query_text', 'query_result']
    list_filter = ['upload_date']
    readonly_fields = ['image_preview', 'upload_date', 'short_caption', 'normal_caption', 'query_text', 'query_result']
    fieldsets = [
        ('Image', {
            'fields': ['image', 'image_preview', 'upload_date']
        }),
        ('Generated Content', {
            'fields': ['short_caption', 'normal_caption'],
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
        link = format_html('<a href="{}">{}</a>', 
                          f"/admin/blog/imageanalysis/{obj.analysis.id}/change/", 
                          f"Analysis #{obj.analysis.id}")
        return link
    
    analysis_link.short_description = "Analysis"
