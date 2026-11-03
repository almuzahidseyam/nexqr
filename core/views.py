import base64
import io
import logging
import re
from urllib.parse import urlsplit
import qrcode
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import DatabaseError
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import DailyBudget, DynamicQR, ScanAnalytics
from .artistic import generate_art

logger = logging.getLogger(__name__)


def error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)


def reserve_budget(key, limit):
    date = timezone.now().date()
    DailyBudget.objects.get_or_create(key=key, date=date)
    return (
        DailyBudget.objects.filter(key=key, date=date, used__lt=limit).update(
            used=F("used") + 1
        )
        == 1
    )


def artistic_available(user):
    return bool(
        user.is_staff
        and settings.ARTISTIC_ENABLED
        and settings.REPLICATE_API_TOKEN
        and re.fullmatch(r"[a-f0-9]{64}", settings.REPLICATE_MODEL_VERSION)
    )


@login_required
@require_GET
def dashboard(request):
    page = Paginator(
        DynamicQR.objects.filter(owner=request.user).order_by("-created_at"), 20
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard.html",
        {"qrs": page, "artistic_available": artistic_available(request.user)},
    )


def record_scan(request, qr):
    # Do not retain raw IP addresses or arbitrary user-agent text for new scans.
    device = (
        "Mobile"
        if "mobi" in request.META.get("HTTP_USER_AGENT", "").lower()
        else "Desktop"
    )
    try:
        ScanAnalytics.objects.create(qr_code=qr, device_type=device)
    except DatabaseError:
        logger.warning("Scan count could not be saved.")


def validate_url(url):
    if len(url) > 2000:
        raise ValidationError("URL is too long.")
    URLValidator(schemes=["http", "https"])(url)
    if urlsplit(url).username or urlsplit(url).password:
        raise ValidationError("Do not embed credentials in a URL.")


@require_GET
def redirect_qr(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code)
    if qr.is_encrypted:
        return redirect("secure_view", short_code=short_code)
    try:
        validate_url(qr.original_url)
    except (ValidationError, ValueError):
        return error("This destination is no longer valid.", 410)
    record_scan(request, qr)
    response = redirect(qr.original_url)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def secure_view(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code, is_encrypted=True)
    record_scan(request, qr)
    response = render(request, "secure.html", {"qr": qr})
    response["Cache-Control"] = "no-store"
    return response


@require_POST
def generate_qr(request):
    if not request.user.is_authenticated:
        return error("Sign in before creating a QR code.", 401)
    qr_type = request.POST.get("type", "standard")
    if qr_type not in {"standard", "dynamic", "secure", "artistic"}:
        return error("Unknown QR type.")
    name = request.POST.get("name", "").strip() or "Untitled QR"
    if len(name) > 100:
        return error("Use a name of at most 100 characters.")
    payload = request.POST.get("encrypted_payload", "")
    url = request.POST.get("url", "").strip()
    prompt = request.POST.get("prompt", "").strip()
    if qr_type == "secure":
        if not payload or len(payload) > 10000:
            return error(
                "An encrypted payload of at most 10,000 characters is required."
            )
    else:
        try:
            validate_url(url)
        except (ValidationError, ValueError):
            return error(
                "Enter a valid HTTP or HTTPS URL without credentials (maximum 2000 characters)."
            )
    if qr_type == "artistic":
        if not artistic_available(request.user):
            return error(
                "Artistic generation is disabled or unavailable for this account.", 403
            )
        if not prompt or len(prompt) > 500:
            return error("Enter an art prompt between 1 and 500 characters.")
    if not reserve_budget(f"qr:{request.user.pk}", settings.QR_DAILY_LIMIT):
        return error("Your daily QR creation limit has been reached.", 429)
    if qr_type == "artistic" and not reserve_budget(
        "artistic:global", settings.ARTISTIC_DAILY_LIMIT
    ):
        return error(
            "The server daily artistic-generation limit has been reached.", 429
        )
    entry = None
    try:
        target = url
        if qr_type != "standard":
            entry = DynamicQR.objects.create(
                owner=request.user,
                name=name,
                original_url=url or "SECURE_PAYLOAD",
                is_encrypted=qr_type == "secure",
                encrypted_payload=payload if qr_type == "secure" else "",
                is_artistic=qr_type == "artistic",
                prompt=prompt if qr_type == "artistic" else "",
            )
            route = "secure_view" if entry.is_encrypted else "redirect_qr"
            target = request.build_absolute_uri(reverse(route, args=[entry.short_code]))
        if qr_type == "artistic":
            image = generate_art(target, prompt)
        else:
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4
            )
            qr.add_data(target)
            qr.make(fit=True)
            buffer = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(
                buffer, format="PNG"
            )
            image = buffer.getvalue()
        return JsonResponse(
            {
                "status": "success",
                "qr_image": "data:image/png;base64," + base64.b64encode(image).decode(),
                "target_url": target,
            }
        )
    except Exception:
        if entry:
            entry.delete()
        logger.warning("QR generation failed; no provider details exposed.")
        return error(
            "Generation failed. Retry later. Artistic attempts still count toward the daily limit.",
            502,
        )


def api_generate_qr(request):
    return error("Open the signed-in dashboard to generate a QR code.", 410)


@login_required
@require_GET
def analytics_view(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code, owner=request.user)
    return render(
        request,
        "analytics.html",
        {
            "qr": qr,
            "total_scans": qr.scans.count(),
            "mobile": qr.scans.filter(device_type="Mobile").count(),
            "desktop": qr.scans.filter(device_type="Desktop").count(),
            "recent_scans": qr.scans.order_by("-scanned_at")[:20],
        },
    )
