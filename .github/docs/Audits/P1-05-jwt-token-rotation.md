# P1-05: JWT Token Rotation & Blacklisting

## Overview

Implements secure JWT token rotation with short-lived access tokens, automatic refresh token rotation, and token blacklisting on logout. This enhances security by limiting token exposure time and preventing token reuse after logout.

## Implementation Status

### ✅ Backend (Complete)

- JWT configuration with token rotation
- Token blacklisting infrastructure
- Logout endpoint with token invalidation
- Database tables for blacklist tracking
- Comprehensive test coverage (17 tests)

### ⏸️ Frontend (Pending)

- Awaiting login/authentication UI implementation
- Will add: Axios interceptor for auto-refresh, logout functionality

---

## Backend Configuration

### JWT Settings (`app/settings.py`)

```python
SIMPLE_JWT = {
    # Token Lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived for security
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),     # Longer for user convenience

    # Token Rotation
    "ROTATE_REFRESH_TOKENS": True,                   # Issue new refresh token on refresh
    "BLACKLIST_AFTER_ROTATION": True,                # Invalidate old refresh token

    # Security
    "UPDATE_LAST_LOGIN": True,                       # Track user activity
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),

    # Token Claims
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}
```

### Token Blacklist

Added to `SHARED_APPS` (public schema):

```python
SHARED_APPS = [
    # ...
    "rest_framework_simplejwt.token_blacklist",  # P1-05: JWT token blacklist
    # ...
]
```

**Database Tables Created:**

- `token_blacklist_outstandingtoken` - Tracks all issued refresh tokens
- `token_blacklist_blacklistedtoken` - Records invalidated tokens

---

## API Endpoints

### 1. Obtain Token Pair (Login)

```http
POST /api/auth/token/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200 OK):**

```json
{
  "access": "eyJhbGci...",
  "refresh": "eyJhbGci..."
}
```

**Notes:**

- Returns both access and refresh tokens
- Access token expires in 15 minutes
- Refresh token expires in 7 days
- Outstanding token record created in database

---

### 2. Refresh Access Token

```http
POST /api/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGci..."
}
```

**Response (200 OK):**

```json
{
  "access": "eyJhbGci...", // New access token
  "refresh": "eyJhbGci..." // New refresh token (rotation enabled)
}
```

**Notes:**

- Returns new access token AND new refresh token (rotation)
- Old refresh token is automatically blacklisted
- Attempting to use old refresh token will fail with 401

---

### 3. Logout (Blacklist Token)

```http
POST /api/auth/logout/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh": "eyJhbGci..."
}
```

**Response (205 Reset Content):**

```json
{
  "detail": "Logout successful."
}
```

**Error Responses:**

**401 Unauthorized** (no access token):

```json
{
  "detail": "Authentication credentials were not provided."
}
```

**400 Bad Request** (no refresh token in body):

```json
{
  "error": "Refresh token is required."
}
```

**400 Bad Request** (invalid/blacklisted token):

```json
{
  "error": "Invalid token: Token is blacklisted"
}
```

**Notes:**

- Requires valid access token in Authorization header
- Blacklists the refresh token to prevent reuse
- Access token expires naturally (cannot be revoked server-side)
- Blacklisted token record created in database

---

## Security Features

### 1. Short-lived Access Tokens (15 minutes)

- Limits exposure if token is compromised
- Forces regular refresh, allowing rotation
- Cannot be revoked server-side (by design)

### 2. Token Rotation

- New refresh token issued on every refresh
- Old refresh token automatically blacklisted
- Prevents token replay attacks
- Detects stolen tokens (if both user and attacker refresh)

### 3. Token Blacklisting

- Refresh tokens blacklisted on logout
- Old tokens blacklisted after rotation
- Database-backed (persistent across restarts)
- Prevents token reuse after logout

### 4. Database Tracking

- `OutstandingToken`: All issued refresh tokens
- `BlacklistedToken`: Invalidated tokens (logout + rotation)
- Enables audit trail and token management

---

## Testing

### Test Coverage (17 tests, all passing)

**Configuration Tests (4):**

- ✅ Access token lifetime is 15 minutes
- ✅ Refresh token lifetime is 7 days
- ✅ Token rotation enabled
- ✅ Blacklist after rotation enabled

**Token Obtain Tests (2):**

- ✅ Valid credentials return token pair
- ✅ Invalid credentials rejected (401)

**Token Refresh Tests (4):**

- ✅ Refresh returns new access token
- ✅ Refresh returns new refresh token (rotation)
- ✅ Old refresh token blacklisted after rotation
- ✅ Invalid refresh token rejected (401)

**Token Blacklist Tests (5):**

- ✅ Logout blacklists refresh token
- ✅ Blacklisted token cannot be used
- ✅ Logout requires authentication
- ✅ Logout requires refresh token in body
- ✅ Logout handles invalid tokens gracefully

**Model Tests (2):**

- ✅ Outstanding token created on login
- ✅ Blacklisted token created on logout

### Run Tests

```bash
cd backend
python -m pytest tests/test_jwt_rotation.py -v
```

---

## Manual Testing

### 1. Login and Get Tokens

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "TestPass123!"}'

# Response: {"access":"...", "refresh":"..."}
```

### 2. Refresh Token

```bash
curl -X POST http://localhost:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<REFRESH_TOKEN>"}'

# Response: {"access":"...", "refresh":"..."}  (both new!)
```

### 3. Logout (Blacklist)

```bash
curl -X POST http://localhost:8000/api/auth/logout/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{"refresh":"<REFRESH_TOKEN>"}'

# Response: {"detail":"Logout successful."}
```

### 4. Verify Blacklist

```bash
# Try to use the blacklisted refresh token
curl -X POST http://localhost:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<BLACKLISTED_TOKEN>"}'

# Response: {"detail":"Token is blacklisted","code":"token_not_valid"}
```

---

## Frontend Integration (Future)

### Token Storage

```typescript
// Store tokens after login
localStorage.setItem("access_token", data.access);
localStorage.setItem("refresh_token", data.refresh);
```

### Axios Interceptor (Auto-refresh)

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: `${window.location.origin}/api`,
});

// Request interceptor: Add access token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        // Refresh tokens
        const { data } = await api.post("/auth/token/refresh/", {
          refresh: refreshToken,
        });

        // Store new tokens (both access AND refresh due to rotation)
        localStorage.setItem("access_token", data.access);
        localStorage.setItem("refresh_token", data.refresh);

        // Retry original request with new access token
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed - redirect to login
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

### Logout Function

```typescript
const logout = async () => {
  try {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      await api.post("/auth/logout/", { refresh: refreshToken });
    }
  } catch (error) {
    console.error("Logout error:", error);
  } finally {
    // Clear tokens regardless of API call success
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate({ to: "/login" });
  }
};
```

### Proactive Refresh (Optional)

```typescript
// Decode JWT to check expiry (requires jwt-decode package)
import { jwtDecode } from "jwt-decode";

const shouldRefreshToken = () => {
  const token = localStorage.getItem("access_token");
  if (!token) return false;

  try {
    const decoded = jwtDecode(token);
    const now = Date.now() / 1000;
    // Refresh if less than 2 minutes remaining
    return decoded.exp - now < 120;
  } catch {
    return false;
  }
};

// Call before important API requests
const makeImportantRequest = async () => {
  if (shouldRefreshToken()) {
    await refreshTokens(); // Trigger refresh
  }
  return api.post("/important-endpoint", data);
};
```

---

## Token Lifecycle

### Normal Flow

```
1. Login → Access (15min) + Refresh (7 days)
2. Use Access Token for API calls
3. Access Token expires (15 min)
4. Auto-refresh → New Access + New Refresh (rotation!)
5. Old Refresh Token blacklisted automatically
6. Repeat steps 2-5 until user logs out
7. Logout → Blacklist current Refresh Token
```

### Security Scenarios

**Scenario 1: Token Stolen After Logout**

- User logs out → Refresh token blacklisted
- Attacker tries to use stolen token → 401 "Token is blacklisted"
- ✅ Protected

**Scenario 2: Refresh Token Stolen (Active Session)**

- Legitimate user refreshes → New tokens issued, old blacklisted
- Attacker tries to use old token → 401 "Token is blacklisted"
- Legitimate user continues normally with new tokens
- ✅ Protected (attacker detected)

**Scenario 3: Access Token Stolen**

- Access token valid for max 15 minutes
- Cannot be revoked server-side (stateless design)
- Expires quickly, limiting exposure window
- ⚠️ 15-minute exposure window (acceptable trade-off)

---

## Database Management

### Check Outstanding Tokens

```python
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

# Count tokens per user
for user in User.objects.all():
    count = OutstandingToken.objects.filter(user=user).count()
    print(f"{user.username}: {count} tokens")
```

### Check Blacklisted Tokens

```python
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

# Count blacklisted tokens
print(f"Blacklisted tokens: {BlacklistedToken.objects.count()}")
```

### Cleanup Old Tokens (Management Command)

```bash
# Django provides a built-in command to flush expired tokens
python manage.py flushexpiredtokens
```

**Recommendation:** Run this as a periodic task (e.g., weekly cron job) to prevent table growth.

---

## Troubleshooting

### Issue: "Token is blacklisted" immediately after refresh

**Cause:** Token rotation blacklisted the token, but client is using old refresh token.

**Solution:** Ensure frontend updates BOTH access AND refresh tokens after refresh:

```typescript
localStorage.setItem("access_token", data.access);
localStorage.setItem("refresh_token", data.refresh); // Don't forget this!
```

---

### Issue: Users logged out after 15 minutes

**Cause:** Access token expired, no auto-refresh interceptor.

**Solution:** Implement Axios response interceptor (see Frontend Integration above).

---

### Issue: "No installed app with label 'token_blacklist'"

**Cause:** App not in INSTALLED_APPS (or only in SHARED_APPS but not properly merged).

**Solution:**

1. Verify `rest_framework_simplejwt.token_blacklist` in SHARED_APPS
2. Check INSTALLED_APPS includes SHARED_APPS content
3. Run migrations: `python manage.py migrate`

---

### Issue: Logout fails with 404

**Cause:** URL not configured or tenant routing issue.

**Solution:**

1. Verify `api/urls.py` has logout path
2. Ensure tests use `ensure_public_domain` fixture
3. Check tenant middleware configuration

---

## Performance Considerations

### Database Growth

- Outstanding tokens table grows with each login
- Blacklisted tokens table grows with each logout/refresh
- **Mitigation:** Run `flushexpiredtokens` periodically (weekly recommended)

### Query Performance

- Token validation queries blacklist table on every refresh
- **Current Scale:** Acceptable for thousands of active users
- **Future:** Consider indexing strategies if >100k active tokens

---

## Future Enhancements

### 1. Token Expiry Notifications

- Notify user before access token expires
- Offer "Stay logged in?" prompt

### 2. Refresh Token Families

- Track token lineage (parent-child relationships)
- Detect token theft more reliably
- Invalidate entire token family on suspicious activity

### 3. Device Management

- Store device info with outstanding tokens
- Allow users to view/revoke active sessions
- "Logout from all devices" feature

### 4. Configurable Token Lifetimes

- Per-user or per-role token lifetimes
- Admin users: shorter tokens (higher security)
- Regular users: longer tokens (convenience)

---

## Security Best Practices

### ✅ Implemented

- Short-lived access tokens (15 minutes)
- Refresh token rotation
- Token blacklisting on logout
- Secure token storage (localStorage)
- HTTPS enforcement (see P1-02)
- Strong password requirements (see P1-01)

### 🔜 Future

- Refresh token families (detection of stolen tokens)
- Device fingerprinting
- Anomaly detection (IP changes, unusual patterns)
- Rate limiting on token endpoints
- Token binding to client (PKCE-like mechanism)

---

## Related Documentation

- **P1-01:** Password Complexity & Validation
- **P1-02:** HTTPS Enforcement
- **SimpleJWT Docs:** https://django-rest-framework-simplejwt.readthedocs.io/
- **JWT Best Practices:** https://tools.ietf.org/html/rfc8725

---

## Changelog

**2025-10-19 - Initial Implementation**

- Configured JWT with 15-min access, 7-day refresh tokens
- Enabled token rotation and blacklisting
- Created logout endpoint with token invalidation
- Added comprehensive test suite (17 tests)
- Documented backend implementation
- Frontend integration pending (awaits login UI)
