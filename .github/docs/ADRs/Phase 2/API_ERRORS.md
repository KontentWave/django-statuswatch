# StatusWatch API Error Codes

This document describes all standardized error responses from the StatusWatch API.

## Table of Contents

- [General Error Format](#general-error-format)
- [Authentication Errors (401, 403)](#authentication-errors)
- [Validation Errors (400)](#validation-errors)
- [Conflict Errors (409)](#conflict-errors)
- [Server Errors (500)](#server-errors)

---

## General Error Format

All API errors follow a consistent structure:

```json
{
  "detail": "Human-readable error message",
  "code": "machine_readable_error_code",
  "errors": {
    "field_name": ["Field-specific error message"]
  }
}
```

**Fields:**

- `detail` (string): User-friendly error description
- `code` (string, optional): Machine-readable error identifier for client handling
- `errors` (object, optional): Field-specific validation errors

---

## Authentication Errors

### 401 Unauthorized - Invalid Credentials

**Endpoint:** `POST /api/auth/login/`

**Response:**

```json
{
  "detail": "Invalid credentials",
  "error": "Invalid credentials"
}
```

**Cause:** Incorrect email/password combination or account not verified.

**Client Action:** Display error message, allow user to retry or reset password.

---

### 401 Unauthorized - Token Expired

**Endpoint:** Any authenticated endpoint

**Response:**

```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [
    {
      "token_class": "AccessToken",
      "token_type": "access",
      "message": "Token is invalid or expired"
    }
  ]
}
```

**Cause:** Access token has expired.

**Client Action:** Attempt token refresh using refresh token. If refresh fails, redirect to login.

---

### 403 Forbidden - Wrong Tenant

**Endpoint:** Any tenant-specific endpoint

**Response:**

```json
{
  "detail": "You do not have permission to access this organization"
}
```

**Cause:** User trying to access a tenant they don't belong to.

**Client Action:** Redirect to correct tenant subdomain or show "access denied" message.

---

## Validation Errors

### 400 Bad Request - Field Validation

**Endpoint:** `POST /api/auth/register/`, form submissions

**Response:**

```json
{
  "detail": "Validation failed",
  "errors": {
    "email": ["Enter a valid email address."],
    "password": [
      "Password must be at least 12 characters long.",
      "Password must contain at least one uppercase letter."
    ],
    "organization_name": ["Organization name is required."]
  }
}
```

**Cause:** One or more fields failed validation rules.

**Client Action:** Display field-specific errors below each input field.

---

### 400 Bad Request - Password Validation

**Endpoint:** `POST /api/auth/register/`, `POST /api/auth/change-password/`

**Password Requirements:**

- Minimum 12 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one number (0-9)
- At least one special character (!@#$%^&\*()\_+-=[]{}|;:,.<>?)
- Not too similar to email/username
- Not a commonly used password

**Example Response:**

```json
{
  "detail": "Password validation failed",
  "errors": {
    "password": [
      "Password must be at least 12 characters long.",
      "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)."
    ]
  }
}
```

---

## Conflict Errors

### 409 Conflict - Duplicate Email

**Endpoint:** `POST /api/auth/register/`

**Response:**

```json
{
  "detail": "This email address is already registered.",
  "code": "duplicate_email"
}
```

**Status Code:** `409 Conflict`

**Cause:** Email address already exists in the system.

**Client Action:**

- Display error message to user
- Suggest login or password reset
- Link to "Forgot Password" flow

**Example:**

```typescript
catch (error) {
  if (error.response?.status === 409 &&
      error.response?.data?.code === 'duplicate_email') {
    setError('email', {
      message: 'This email is already registered. Try logging in instead.'
    });
  }
}
```

---

### 409 Conflict - Duplicate Organization Name ⭐ NEW

**Endpoint:** `POST /api/auth/register/`

**Response:**

```json
{
  "detail": "This organization name is already taken. Please choose another name.",
  "code": "duplicate_organization_name"
}
```

**Status Code:** `409 Conflict`

**Cause:** Organization name already exists in the system. Organization names must be globally unique.

**Client Action:**

- Display error message below organization name field
- Suggest alternative names (e.g., "Acme-2", "Acme-Corp")
- Allow user to modify and retry

**Example:**

```typescript
catch (error) {
  if (error.response?.status === 409 &&
      error.response?.data?.code === 'duplicate_organization_name') {
    setError('organization_name', {
      message: 'This organization name is already taken. Please choose another name.'
    });
  }
}
```

**Frontend Validation (Recommended):**
Implement real-time availability check:

```typescript
const checkOrgNameAvailability = debounce(async (name: string) => {
  if (!name) return;

  try {
    const { data } = await api.post("/api/check-org-name/", {
      organization_name: name,
    });

    if (!data.available) {
      setError("organization_name", {
        type: "manual",
        message: "This organization name is already taken",
      });
    } else {
      clearErrors("organization_name");
    }
  } catch (error) {
    // Handle error silently or show warning
  }
}, 500);
```

---

### 409 Conflict - Schema Conflict

**Endpoint:** `POST /api/auth/register/`

**Response:**

```json
{
  "detail": "Organization name is not available. Please choose another.",
  "code": "schema_conflict"
}
```

**Status Code:** `409 Conflict`

**Cause:** Internal schema name conflict (usually caught by organization name uniqueness).

**Client Action:** Display error, allow user to choose different name.

---

## Server Errors

### 500 Internal Server Error - Tenant Creation Failed

**Endpoint:** `POST /api/auth/register/`

**Response:**

```json
{
  "detail": "Failed to create organization. Please try again or contact support.",
  "code": "tenant_creation_failed"
}
```

**Status Code:** `500 Internal Server Error`

**Cause:** Database error, migration failure, or other internal issue during tenant provisioning.

**Client Action:**

- Display user-friendly error message
- Log error details for support
- Suggest trying again or contacting support

---

### 500 Internal Server Error - Configuration Error

**Endpoint:** Any endpoint

**Response:**

```json
{
  "detail": "Service is temporarily unavailable. Please try again later.",
  "code": "configuration_error"
}
```

**Status Code:** `500 Internal Server Error`

**Cause:** Missing environment variables, misconfigured services, or infrastructure issues.

**Client Action:**

- Display generic error message
- Suggest trying again later
- Do not expose technical details to user

---

## Payment Errors

### 402 Payment Required - Payment Failed

**Endpoint:** `POST /api/pay/create-checkout-session/`

**Response:**

```json
{
  "detail": "Payment processing failed. Please check your payment method and try again.",
  "code": "payment_failed"
}
```

**Status Code:** `402 Payment Required`

**Cause:** Stripe payment processing error, invalid payment method, or insufficient funds.

**Client Action:** Display error message, allow user to update payment method.

---

### 400 Bad Request - Invalid Payment Method

**Endpoint:** `POST /api/pay/create-checkout-session/`

**Response:**

```json
{
  "detail": "Payment method is invalid. Please use a different payment method.",
  "code": "invalid_payment_method"
}
```

**Status Code:** `400 Bad Request`

**Cause:** Payment method declined or invalid.

**Client Action:** Ask user to provide different payment method.

---

## Rate Limiting

### 429 Too Many Requests

**Endpoint:** Any endpoint

**Response:**

```json
{
  "detail": "Too many requests. Please slow down and try again later.",
  "code": "rate_limit_exceeded"
}
```

**Status Code:** `429 Too Many Requests`

**Headers:**

```
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1698765432
```

**Cause:** User or IP exceeded rate limits.

**Client Action:**

- Display "slow down" message
- Wait for `Retry-After` seconds before retrying
- Consider implementing exponential backoff

---

## Multi-Tenant Login Errors

### 200 OK - Multiple Tenants Found ⭐ NEW

**Endpoint:** `POST /api/auth/login/`

**Response:**

```json
{
  "multiple_tenants": true,
  "tenants": [
    {
      "tenant_schema": "acme",
      "tenant_name": "Acme Corporation",
      "tenant_id": 1
    },
    {
      "tenant_schema": "acmeuk",
      "tenant_name": "Acme UK",
      "tenant_id": 2
    }
  ],
  "message": "Your email exists in multiple organizations. Please select which one you want to access."
}
```

**Status Code:** `200 OK` (not an error - requires user interaction)

**Cause:** User's email exists in multiple tenant organizations (logged in from localhost or public domain).

**Client Action:**

- Hide login form
- Display tenant selector UI
- Show list of organizations with radio buttons or dropdown
- Allow user to select one
- Re-submit login with `tenant_schema` field:

```typescript
const handleTenantSelection = async (selectedSchema: string) => {
  const { data } = await api.post("/api/auth/login/", {
    username: email,
    password: password,
    tenant_schema: selectedSchema, // Include selected tenant
  });

  // Proceed with normal login flow
  storeAuthTokens(data);
  window.location.href = data.tenant_domain;
};
```

---

## Error Handling Best Practices

### Frontend Implementation

```typescript
import { AxiosError } from "axios";

interface ApiError {
  detail?: string;
  code?: string;
  errors?: Record<string, string[]>;
}

const handleApiError = (error: AxiosError<ApiError>) => {
  const status = error.response?.status;
  const data = error.response?.data;

  // Handle specific error codes
  switch (data?.code) {
    case "duplicate_email":
      return "This email is already registered. Try logging in instead.";

    case "duplicate_organization_name":
      return "This organization name is taken. Please choose another.";

    case "token_not_valid":
      // Attempt token refresh
      return attemptTokenRefresh();

    case "rate_limit_exceeded":
      return "Too many requests. Please wait a moment.";

    default:
      break;
  }

  // Handle by status code
  switch (status) {
    case 400:
      return data?.detail ?? "Invalid input. Please check your data.";

    case 401:
      return "Please log in to continue.";

    case 403:
      return "You do not have permission to access this resource.";

    case 409:
      return data?.detail ?? "This resource already exists.";

    case 429:
      return "Too many requests. Please slow down.";

    case 500:
      return "Server error. Please try again later.";

    default:
      return "An unexpected error occurred. Please try again.";
  }
};
```

### Logging Client Errors

Always log errors for debugging:

```typescript
import { logAuthEvent } from '@/lib/auth-logger';

catch (error) {
  logAuthEvent('API_ERROR', {
    endpoint: '/api/auth/register/',
    status: error.response?.status,
    code: error.response?.data?.code,
    message: error.response?.data?.detail,
  });

  handleApiError(error);
}
```

---

## Summary Table

| Status | Code                          | Endpoint          | Description              |
| ------ | ----------------------------- | ----------------- | ------------------------ |
| 400    | -                             | Any               | Validation error         |
| 401    | `token_not_valid`             | Any               | Token expired/invalid    |
| 401    | -                             | `/auth/login/`    | Invalid credentials      |
| 403    | -                             | Any               | Wrong tenant access      |
| 409    | `duplicate_email`             | `/auth/register/` | Email already registered |
| 409    | `duplicate_organization_name` | `/auth/register/` | Org name taken           |
| 409    | `schema_conflict`             | `/auth/register/` | Schema conflict          |
| 429    | `rate_limit_exceeded`         | Any               | Too many requests        |
| 500    | `tenant_creation_failed`      | `/auth/register/` | Org creation failed      |
| 500    | `configuration_error`         | Any               | Server misconfigured     |

---

**Last Updated:** October 29, 2025  
**Version:** 1.1.0 (Added duplicate organization name error)
