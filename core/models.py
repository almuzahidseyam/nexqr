from django.db import models
import string
import random

def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

class DynamicQR(models.Model):
    name = models.CharField(max_length=255, default="Untitled QR")
    original_url = models.URLField(max_length=2000)
    short_code = models.CharField(max_length=10, unique=True, blank=True)
    
    is_encrypted = models.BooleanField(default=False)
    encrypted_payload = models.TextField(blank=True, null=True)
    
    is_artistic = models.BooleanField(default=False)
    prompt = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def save(self, *args, **kwargs):
        if not self.short_code:
            # Collision-proof short code generation
            code = generate_short_code()
            while DynamicQR.objects.filter(short_code=code).exists():
                code = generate_short_code()
            self.short_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.short_code})"

class ScanAnalytics(models.Model):
    qr_code = models.ForeignKey(DynamicQR, on_delete=models.CASCADE, related_name='scans')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    device_type = models.CharField(max_length=50, default="Desktop")
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)




