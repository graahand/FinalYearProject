from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)
    date_joined = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class ImageAnalysis(models.Model):
    image = models.ImageField(upload_to='uploads/')
    upload_date = models.DateTimeField(default=timezone.now)
    short_caption = models.TextField(blank=True)
    normal_caption = models.TextField(blank=True)
    query_text = models.TextField(blank=True, null=True)
    query_result = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='analyses')
    
    class Meta:
        ordering = ['-upload_date']
        verbose_name_plural = 'Image Analyses'
    
    def __str__(self):
        return f"Analysis {self.id} - {self.upload_date.strftime('%Y-%m-%d %H:%M')}"

class DetectedObject(models.Model):
    image_analysis = models.ForeignKey(ImageAnalysis, on_delete=models.CASCADE, related_name='detected_objects', null=True, blank=True)
    label = models.CharField(max_length=100)
    confidence = models.FloatField()
    x_min = models.FloatField()
    y_min = models.FloatField()
    x_max = models.FloatField()
    y_max = models.FloatField()
    
    class Meta:
        verbose_name_plural = 'Detected Objects'
    
    def __str__(self):
        return f"{self.label} ({self.confidence:.2f})"
# Create your models here.
