# P1-02: HTTPS Enforcement

**Status:** ✅ Complete  
**Priority:** P1 (High)  
**Complexity:** Low  
**Test Coverage:** 13 tests passing

---

## Overview

This security enhancement enforces HTTPS connections in production, ensuring all traffic is encrypted and protected against man-in-the-middle attacks. It complements P1-01 (Password Complexity) by ensuring passwords are never transmitted over unencrypted connections.

---

## Implementation Details

### Settings Configuration

All HTTPS enforcement settings are controlled via the `ENFORCE_HTTPS` environment variable, which defaults to `False` for development and should be set to `True` in production.

**File:** `backend/app/settings.py`

```python
# HTTPS Enforcement (P1-02)
ENFORCE_HTTPS = env.bool("ENFORCE_HTTPS", default=False)

if ENFORCE_HTTPS:
    # Redirect all HTTP requests to HTTPS
    SECURE_SSL_REDIRECT = True

    # Trust X-Forwarded-Proto header from reverse proxy
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
else:
    # Development: Allow HTTP
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Cookie security (always enforced)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
```

---

## Environment Configuration

### Development (.env)

```bash
# Development: Allow HTTP
ENFORCE_HTTPS=False
```

### Production (.env)

```bash
# Production: Enforce HTTPS
ENFORCE_HTTPS=True
```

---

## Features Implemented

### 1. HTTPS Redirect

- **What:** Automatically redirects all HTTP requests to HTTPS
- **Setting:** `SECURE_SSL_REDIRECT = True`
- **When:** Production only (`ENFORCE_HTTPS=True`)
- **Behavior:** Returns 301 Permanent Redirect from `http://` to `https://`

### 2. HSTS (HTTP Strict Transport Security)

- **What:** Tells browsers to only use HTTPS for future requests
- **Duration:** 1 year (31,536,000 seconds)
- **Subdomains:** Includes all subdomains
- **Preload:** Eligible for browser preload lists
- **Headers Added:**
  ```
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  ```

### 3. Reverse Proxy Support

- **What:** Trusts `X-Forwarded-Proto` header from reverse proxies
- **Setting:** `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- **Why:** Needed when Django is behind nginx, Apache, or cloud load balancers
- **Behavior:** Django treats request as HTTPS if header is present

### 4. Secure Cookies

- **Session Cookie:** Only sent over HTTPS (`SESSION_COOKIE_SECURE = True`)
- **CSRF Token:** Only sent over HTTPS (`CSRF_COOKIE_SECURE = True`)
- **HTTPOnly:** Prevents JavaScript access (always enabled)
- **SameSite:** Set to "Lax" to prevent CSRF attacks (always enabled)

### 5. Additional Security Headers

- **X-Content-Type-Options:** Prevents MIME-sniffing
- **X-XSS-Protection:** Enables browser XSS filtering (legacy support)

---

## Testing

### Test Coverage

**File:** `backend/tests/test_https_enforcement.py`

#### HTTPS Enforcement Tests (9 tests)

- ✅ HTTP redirects to HTTPS when enforced
- ✅ HTTP allowed in development mode
- ✅ HSTS header present in production
- ✅ HSTS header includes subdomains and preload
- ✅ No HSTS header in development
- ✅ Respects X-Forwarded-Proto header
- ✅ Secure cookies in production
- ✅ Insecure cookies in development
- ✅ SecurityMiddleware installed

#### Cookie Security Tests (2 tests)

- ✅ HTTPOnly flag set on cookies
- ✅ SameSite attribute configured

#### Integration Tests (2 tests)

- ✅ Admin endpoints redirect to HTTPS
- ✅ Development mode works with HTTP

### Running Tests

```bash
# Run all HTTPS tests
cd backend
python -m pytest tests/test_https_enforcement.py -v

# Run full test suite (should show 75 passing)
python -m pytest -q
```

### Expected Results

```
13 passed in ~4s  # HTTPS tests
75 passed in ~50s # Full suite
```

---

## Deployment Guide

### Prerequisites

1. **Valid SSL/TLS Certificate**

   - Let's Encrypt (free, automated)
   - Commercial CA certificate
   - Cloudflare SSL (if using Cloudflare)

2. **Reverse Proxy Configuration**
   - Nginx, Apache, or cloud load balancer
   - Must forward `X-Forwarded-Proto` header

### Step-by-Step Deployment

#### 1. Configure Reverse Proxy (Nginx Example)

**File:** `/etc/nginx/sites-available/statuswatch`

```nginx
server {
    listen 80;
    server_name statuswatch.example.com *.statuswatch.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name statuswatch.example.com *.statuswatch.example.com;

    # SSL Certificate
    ssl_certificate /etc/letsencrypt/live/statuswatch.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/statuswatch.example.com/privkey.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Forward protocol to Django
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Host $host;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }

    location /static/ {
        alias /path/to/statuswatch/staticfiles/;
    }
}
```

#### 2. Update Environment Variables

**Production .env:**

```bash
ENFORCE_HTTPS=True
ALLOWED_HOSTS=statuswatch.example.com,.statuswatch.example.com
```

#### 3. Test Configuration

```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Test Django settings
cd backend
python manage.py check --deploy
```

#### 4. Verify HTTPS Enforcement

```bash
# Should redirect to HTTPS
curl -I http://statuswatch.example.com

# Should return 200 with HSTS header
curl -I https://statuswatch.example.com

# Check for HSTS header
curl -I https://statuswatch.example.com | grep -i strict-transport
```

Expected output:

```
HTTP/1.1 301 Moved Permanently
Location: https://statuswatch.example.com/

HTTP/2 200
strict-transport-security: max-age=31536000; includeSubDomains; preload
```

---

## Reverse Proxy Configurations

### Apache

```apache
<VirtualHost *:80>
    ServerName statuswatch.example.com
    Redirect permanent / https://statuswatch.example.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName statuswatch.example.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/statuswatch.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/statuswatch.example.com/privkey.pem

    # Forward protocol to Django
    RequestHeader set X-Forwarded-Proto "https"

    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

### Cloudflare

If using Cloudflare:

1. Set SSL/TLS mode to **Full (strict)** in Cloudflare dashboard
2. Enable **Always Use HTTPS**
3. Enable **HSTS** in Cloudflare (Edge Certificates > HSTS)
4. Django will automatically trust `X-Forwarded-Proto` from Cloudflare

---

## HSTS Preload Submission

After HTTPS is stable for several weeks, submit your domain to the HSTS preload list:

1. Visit: https://hstspreload.org/
2. Enter your domain
3. Verify requirements:
   - ✅ Valid certificate
   - ✅ HTTPS redirect from HTTP
   - ✅ HSTS header with sufficient max-age (≥31536000)
   - ✅ includeSubDomains directive
   - ✅ preload directive
4. Submit for inclusion in browser preload lists

**Warning:** HSTS preload is difficult to undo. Only submit when you're confident HTTPS will be permanent.

---

## Troubleshooting

### Issue: "Mixed Content" Warnings

**Symptom:** Browser console shows mixed content warnings

**Cause:** Page loaded over HTTPS contains HTTP resources (images, scripts, etc.)

**Solution:**

```python
# Ensure all URLs use relative paths or HTTPS
<script src="/static/js/app.js"></script>  # Good: relative
<script src="https://cdn.example.com/lib.js"></script>  # Good: HTTPS
<script src="http://cdn.example.com/lib.js"></script>  # Bad: HTTP
```

### Issue: Redirect Loop

**Symptom:** Browser shows "Too many redirects" error

**Cause:** Reverse proxy not sending `X-Forwarded-Proto` header

**Solution:**

1. Check nginx/Apache config includes `proxy_set_header X-Forwarded-Proto $scheme;`
2. Verify header reaches Django: `print(request.META.get('HTTP_X_FORWARDED_PROTO'))`
3. Restart reverse proxy after config changes

### Issue: CSRF Token Errors After Enabling HTTPS

**Symptom:** POST requests fail with "CSRF verification failed"

**Cause:** Cookies set over HTTP are not sent over HTTPS

**Solution:**

1. Clear browser cookies
2. Log out and log back in to get new secure cookies
3. Verify `CSRF_COOKIE_SECURE = True` in production

### Issue: Local Development Breaks

**Symptom:** Development server doesn't work after deploying HTTPS

**Cause:** `ENFORCE_HTTPS=True` set in development

**Solution:**

```bash
# Local .env should have:
ENFORCE_HTTPS=False

# Production .env should have:
ENFORCE_HTTPS=True
```

### Issue: Django Check Warnings

**Symptom:** `python manage.py check --deploy` shows security warnings

**Solution:**

```bash
# In production with ENFORCE_HTTPS=True, this should return no warnings:
python manage.py check --deploy --settings=app.settings

# Common warnings and their fixes:
# - SECURE_SSL_REDIRECT: Set ENFORCE_HTTPS=True
# - SECURE_HSTS_SECONDS: Already set to 31536000
# - SESSION_COOKIE_SECURE: Already enabled with ENFORCE_HTTPS
```

---

## Security Considerations

### Development vs Production

| Setting               | Development | Production  |
| --------------------- | ----------- | ----------- |
| ENFORCE_HTTPS         | False       | **True**    |
| SECURE_SSL_REDIRECT   | False       | **True**    |
| SESSION_COOKIE_SECURE | False       | **True**    |
| CSRF_COOKIE_SECURE    | False       | **True**    |
| HSTS Headers          | Disabled    | **Enabled** |

### HSTS Ramp-Up Strategy

When first enabling HTTPS, consider a gradual HSTS rollout:

```python
# Week 1: Test with short duration
SECURE_HSTS_SECONDS = 3600  # 1 hour

# Week 2-4: Increase to 1 week
SECURE_HSTS_SECONDS = 604800  # 7 days

# Month 2+: Full deployment
SECURE_HSTS_SECONDS = 31536000  # 1 year
```

### Cookie Security

All cookies are protected with:

- **Secure flag:** Only sent over HTTPS (production)
- **HttpOnly flag:** JavaScript cannot access (always)
- **SameSite=Lax:** Prevents CSRF attacks (always)

---

## Testing Checklist

### Pre-Deployment

- [ ] Valid SSL certificate installed
- [ ] Reverse proxy configured with X-Forwarded-Proto
- [ ] `ENFORCE_HTTPS=True` in production .env
- [ ] All 75 backend tests passing
- [ ] `python manage.py check --deploy` shows no warnings

### Post-Deployment

- [ ] HTTP redirects to HTTPS: `curl -I http://yourdomain.com`
- [ ] HSTS header present: `curl -I https://yourdomain.com | grep -i strict`
- [ ] Login works over HTTPS
- [ ] No mixed content warnings in browser console
- [ ] Cookies are marked as Secure in browser dev tools
- [ ] CSRF tokens work in forms

### Browser Testing

- [ ] Chrome/Edge: Check padlock icon, view certificate
- [ ] Firefox: Check security icon, view connection details
- [ ] Safari: Check security indicators
- [ ] Mobile browsers: Test on actual devices

---

## Performance Impact

### Negligible Impact

- **Redirect overhead:** ~5-10ms per initial HTTP request (one-time)
- **HSTS checking:** Client-side, no server impact
- **Cookie headers:** <1KB additional per request

### Benefits

- ✅ Eliminates MITM attacks
- ✅ Prevents packet sniffing
- ✅ Protects user credentials
- ✅ Improves SEO (Google prefers HTTPS)
- ✅ Required for modern web features (Service Workers, HTTP/2, etc.)

---

## Related Documentation

- **P1-01:** Password Complexity (requires HTTPS to be secure)
- **P1-03:** Security Headers (complements HTTPS enforcement)
- **P1-05:** JWT Token Rotation (tokens must be sent over HTTPS)

---

## References

- [Django Security Documentation](https://docs.djangoproject.com/en/stable/topics/security/)
- [OWASP HTTPS Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.html)
- [HSTS Preload List](https://hstspreload.org/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)

---

## Implementation Summary

**Files Modified:**

- `backend/app/settings.py` - HTTPS enforcement settings
- `backend/.env.example` - Environment variable documentation
- `backend/tests/test_https_enforcement.py` - 13 comprehensive tests

**Test Results:**

- ✅ 13/13 HTTPS enforcement tests passing
- ✅ 75/75 total backend tests passing
- ✅ No breaking changes to existing functionality

**Deployment Status:**

- ✅ Ready for production deployment
- ✅ Tested with reverse proxy configuration
- ✅ Safe for development (HTTP still works with ENFORCE_HTTPS=False)

---

**Completed:** October 19, 2025  
**Author:** GitHub Copilot + Marcel  
**Status:** ✅ Production Ready
