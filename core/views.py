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

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

def dashboard(request):
    dynamic_qrs = DynamicQR.objects.all().order_by('-created_at')
    return render(request, 'dashboard.html', {'qrs': dynamic_qrs})

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def redirect_qr(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code)
    
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

def generate_qr(request):
    if request.method == 'POST':
        try:
            qr_type = request.POST.get('type', 'standard')
            qr_name = request.POST.get('name', 'Untitled QR')
            
            if len(qr_name) > 100: qr_name = qr_name[:100]
            
            target_url = ""
            url_validator = URLValidator()
            
            if qr_type == 'secure':
                encrypted_payload = request.POST.get('encrypted_payload', '')
                if not encrypted_payload:
                    return JsonResponse({'status': 'error', 'message': 'Payload is required'})
                
                if len(encrypted_payload) > 10000:
                    return JsonResponse({'status': 'error', 'message': 'Payload is too large. Maximum 10KB allowed.'})
                
                dynamic_qr = DynamicQR.objects.create(
                    name=qr_name, 
                    original_url='SECURE_PAYLOAD',
                    is_encrypted=True,
                    encrypted_payload=encrypted_payload
                )
                target_url = request.build_absolute_uri(f'/secure/{dynamic_qr.short_code}/')
                
            else:
                url = request.POST.get('url', '')
                if not url: 
                    return JsonResponse({'status': 'error', 'message': 'URL is required'})
                    
                if len(url) > 2000:
                    return JsonResponse({'status': 'error', 'message': 'URL is too long. Maximum 2000 characters allowed.'})
                
                if not url.startswith('http://') and not url.startswith('https://'):
                    url = 'https://' + url
                    
                try:
                    url_validator(url)
                except ValidationError:
                    return JsonResponse({'status': 'error', 'message': 'Invalid URL format. Please enter a valid website link.'})
                    
                target_url = url
                
                if qr_type == 'dynamic' or qr_type == 'artistic':
                    prompt = request.POST.get('prompt', '') if qr_type == 'artistic' else ''
                    if len(prompt) > 500: prompt = prompt[:500]
                    
                    dynamic_qr = DynamicQR.objects.create(name=qr_name, original_url=url, is_artistic=(qr_type=='artistic'), prompt=prompt)
                    target_url = request.build_absolute_uri(f'/r/{dynamic_qr.short_code}/')
                    
                    if qr_type == 'artistic':
                        if not REPLICATE_API_TOKEN:
                            return JsonResponse({
                                'status': 'error', 
                                'message': 'API Key Missing: Please set REPLICATE_API_TOKEN in your environment or .env'
                            })
                        
                        try:
                            import replicate
                            os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
                            
                            output = replicate.run(
                                "nateraw/qrcode-stable-diffusion:9cdabf8f8a991351960c7ce2105de2909514b40bd27ac202dba57935b07d29d4",
                                input={
                                    "prompt": prompt,
                                    "qr_code_content": target_url,
                                    "negative_prompt": "ugly, disfigured, low quality, blurry",
                                    "guidance_scale": 7.5,
                                    "controlnet_conditioning_scale": 1.5
                                }
                            )
                            
                            if isinstance(output, list) and len(output) > 0:
                                image_url = output[0]
                                if not image_url.startswith('https://replicate.delivery/') and not image_url.startswith('https://replicate.com/'):
                                    raise Exception("Blocked SSRF attempt: Invalid image host.")
                                
                                response = requests.get(image_url, timeout=10)
                                img_b64 = base64.b64encode(response.content).decode()
                                
                                return JsonResponse({
                                    'status': 'success',
                                    'qr_image': f"data:image/png;base64,{img_b64}",
                                    'target_url': target_url
                                })
                        except requests.exceptions.Timeout:
                            return JsonResponse({'status': 'error', 'message': 'AI Image download timed out.'})
                        except Exception as e:
                            return JsonResponse({'status': 'error', 'message': f'AI Generation Failed: {str(e)}'})

            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(target_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            
            return JsonResponse({
                'status': 'success', 
                'qr_image': f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}",
                'target_url': target_url
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Server Error: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
def api_generate_qr(request):
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
    return resp

def analytics_view(request, short_code):
    qr = get_object_or_404(DynamicQR, short_code=short_code)
    
    recent_scans = []
    for scan in qr.scans.order_by('-scanned_at')[:10]:
        masked_ip = "Unknown"
        if scan.ip_address:
            parts = scan.ip_address.split('.')
            if len(parts) == 4:
                masked_ip = f"{parts[0]}.{parts[1]}.*.*"
            else:
                masked_ip = "Hidden (IPv6)"
        scan.masked_ip = masked_ip
        recent_scans.append(scan)
        
    return render(request, 'analytics.html', {
        'qr': qr,
        'total_scans': qr.scans.count(),
        'desktop': qr.scans.filter(device_type='Desktop').count(),
        'mobile': qr.scans.filter(device_type='Mobile').count(),
        'recent_scans': recent_scans
    })
