from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
import qrcode
import io
import base64
import os
import requests
from .models import DynamicQR, ScanAnalytics

# NOTE: Replicate API token should be stored in env vars in production
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

def dashboard(request):
    dynamic_qrs = DynamicQR.objects.all().order_by('-created_at')
    return render(request, 'dashboard.html', {'qrs': dynamic_qrs})

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def redirect_qr(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code)
    
    # Logic Flaw Fix: Prevent Double-Counting for Secure QRs
    # If a user visits the /r/ link for a secure QR, do NOT log here, 
    # because secure_view will log the scan. Otherwise, analytics get double-counted.
    if not qr.is_encrypted:
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        try:
            ScanAnalytics.objects.create(
                qr_code=qr,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                device_type="Mobile" if "mobi" in ua else "Desktop"
            )
        except Exception:
            pass
            
    if qr.is_encrypted:
        return redirect('secure_view', short_code=qr.short_code)
        
    return redirect(qr.original_url)

def secure_view(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code, is_encrypted=True)
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    
    try:
        ScanAnalytics.objects.create(
            qr_code=qr,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown'),
            device_type="Mobile" if "mobi" in ua else "Desktop"
        )
    except Exception:
        pass
        
    return render(request, 'secure.html', {'qr': qr})

@csrf_exempt
def api_generate_qr(request):
    # Security: Restrict CORS to only Chrome Extensions to prevent malicious websites from flooding the local DB
    origin = request.META.get('HTTP_ORIGIN', '')
    allowed_origin = origin if origin.startswith('chrome-extension://') else 'null'

    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = allowed_origin
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'POST':
        url = request.POST.get('url', '')
        qr_name = request.POST.get('name', 'Extension Generated QR')
        
        if not url:
            resp = JsonResponse({'status': 'error', 'message': 'URL is required'})
            resp['Access-Control-Allow-Origin'] = allowed_origin
            return resp
            
        try:
            # Validate URL
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            URLValidator()(url)
            
            dynamic_qr = DynamicQR.objects.create(name=qr_name, original_url=url)
            target_url = request.build_absolute_uri(f'/r/{dynamic_qr.short_code}/')

            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(target_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            
            resp = JsonResponse({
                'status': 'success', 
                'qr_image': f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}",
                'target_url': target_url
            })
            resp['Access-Control-Allow-Origin'] = allowed_origin
            return resp
        except Exception as e:
            resp = JsonResponse({'status': 'error', 'message': str(e)})
            resp['Access-Control-Allow-Origin'] = allowed_origin
            return resp
            
    resp = JsonResponse({'status': 'error', 'message': 'Invalid request'})
    resp['Access-Control-Allow-Origin'] = allowed_origin
    return response

    if request.method == 'POST':
        url = request.POST.get('url', '')
        qr_name = request.POST.get('name', 'Extension Generated QR')
        
        if not url:
            resp = JsonResponse({'status': 'error', 'message': 'URL is required'})
            resp['Access-Control-Allow-Origin'] = '*'
            return resp
            
        dynamic_qr = DynamicQR.objects.create(name=qr_name, original_url=url)
        target_url = request.build_absolute_uri(f'/r/{dynamic_qr.short_code}/')

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(target_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        
        resp = JsonResponse({
            'status': 'success', 
            'qr_image': f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}",
            'target_url': target_url
        })
        resp['Access-Control-Allow-Origin'] = '*'
        return resp
            
    resp = JsonResponse({'status': 'error', 'message': 'Invalid request'})
    resp['Access-Control-Allow-Origin'] = '*'
    return resp






