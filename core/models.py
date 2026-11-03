from django.db import models
from django.conf import settings
import string
import secrets


def generate_short_code():
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(10)
    )


class DynamicQR(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="qrs",
    )
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
            # The unique database constraint is authoritative under concurrency.
            code = generate_short_code()
            while DynamicQR.objects.filter(short_code=code).exists():
                code = generate_short_code()
            self.short_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class ScanAnalytics(models.Model):
    qr_code = models.ForeignKey(
        DynamicQR, on_delete=models.CASCADE, related_name="scans"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    device_type = models.CharField(max_length=50, default="Desktop")
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)


class DailyBudget(models.Model):
    key = models.CharField(max_length=100)
    date = models.DateField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "date"], name="unique_daily_budget")
        ]
