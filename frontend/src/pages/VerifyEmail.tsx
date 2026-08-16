import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import type { AxiosError } from "axios";

import { api } from "@/lib/api";
import type { AllowedRedirectPath } from "@/lib/redirects";
import { DEFAULT_REDIRECT, sanitizeRedirectPath } from "@/lib/redirects";

const DEFAULT_VERIFY_MESSAGE =
  "Email verified successfully! You can now log in.";
const VERIFIED_TOKEN_CACHE_PREFIX = "statuswatch:verified-token:";
const verificationPromises = new Map<string, Promise<VerifyResponse>>();

const extractErrorMessage = (value: unknown): string | null => {
  if (typeof value === "string") {
    return value;
  }

  if (
    value &&
    typeof value === "object" &&
    "message" in value &&
    typeof (value as { message?: unknown }).message === "string"
  ) {
    return (value as { message: string }).message;
  }

  return null;
};

type VerifyResponse = {
  detail?: string;
  email?: string;
};

type VerifyErrorResponse = {
  error?: string;
  expired?: boolean;
  email?: string;
};

type ResendResponse = {
  detail?: string;
  error?: string;
};

type CachedVerification = {
  detail: string;
  email?: string | null;
};

const readCachedVerification = (
  token: string | null,
): CachedVerification | null => {
  if (!token || typeof window === "undefined") {
    return null;
  }

  try {
    const cacheKey = `${VERIFIED_TOKEN_CACHE_PREFIX}${token}`;
    const raw = window.sessionStorage.getItem(cacheKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as CachedVerification;
    if (!parsed || typeof parsed.detail !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

const writeCachedVerification = (
  token: string,
  payload: CachedVerification,
): void => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const cacheKey = `${VERIFIED_TOKEN_CACHE_PREFIX}${token}`;
    window.sessionStorage.setItem(cacheKey, JSON.stringify(payload));
  } catch {
    /* ignore storage failures */
  }
};

export default function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [message, setMessage] = useState<string>(
    "Verifying your email. Please wait...",
  );
  const [resendEmail, setResendEmail] = useState<string | null>(null);
  const [resendFeedback, setResendFeedback] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);
  const processedTokenRef = useRef<string | null>(null);

  const { token, nextPath } = useMemo(() => {
    const search = location.searchStr ?? location.search ?? "";
    const normalized = search.startsWith("?") ? search : `?${search}`;
    const params = new URLSearchParams(normalized);
    const tokenValue = params.get("token");
    const nextValue = sanitizeRedirectPath(params.get("next"));
    return { token: tokenValue, nextPath: nextValue };
  }, [location.search, location.searchStr]);

  useEffect(() => {
    if (!token) {
      processedTokenRef.current = null;
      setStatus("error");
      setMessage(
        "Verification token missing. Please open the link from your latest email.",
      );
      setResendEmail(null);
      return;
    }

    const cached = readCachedVerification(token);
    if (cached) {
      setStatus("success");
      setMessage(cached.detail);
      setResendEmail(cached.email ?? null);
      setResendFeedback(null);
      processedTokenRef.current = token;
      return;
    }

    if (processedTokenRef.current === token) {
      return;
    }

    let cancelled = false;
    setStatus("idle");
    setMessage("Verifying your email. Please wait...");
    setResendEmail(null);
    setResendFeedback(null);

    let verifyPromise = verificationPromises.get(token);
    if (!verifyPromise) {
      verifyPromise = api
        .post<VerifyResponse>("/auth/verify-email/", { token })
        .then((response) => response.data)
        .finally(() => {
          verificationPromises.delete(token);
        });
      verificationPromises.set(token, verifyPromise);
    }

    verifyPromise
      .then((data) => {
        const detail = data?.detail ?? DEFAULT_VERIFY_MESSAGE;
        const email = data?.email ?? null;
        writeCachedVerification(token, {
          detail,
          email,
        });
        if (cancelled) return;
        processedTokenRef.current = token;
        setStatus("success");
        setMessage(detail);
        if (email) {
          setResendEmail(email);
        }
      })
      .catch((error: AxiosError<VerifyErrorResponse>) => {
        if (cancelled) return;
        const structuredError = extractErrorMessage(
          error.response?.data?.error,
        );
        const detail =
          structuredError ??
          (error.response?.status === 404
            ? "Verification token invalid or already used."
            : "We couldn't verify this token. Please try again.");
        setStatus("error");
        setMessage(detail);
        if (error.response?.data?.email) {
          setResendEmail(error.response.data.email);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleContinue = useCallback(() => {
    const detail = message || DEFAULT_VERIFY_MESSAGE;
    const redirectTarget: AllowedRedirectPath = nextPath ?? DEFAULT_REDIRECT;
    void navigate({
      to: "/login",
      search: (prev) => ({
        ...(prev ?? {}),
        redirect: redirectTarget,
      }),
      state: (prev) => ({
        ...(prev ?? {}),
        message: detail,
        redirectTo: redirectTarget,
      }),
      replace: true,
    });
  }, [message, navigate, nextPath]);

  const handleResend = useCallback(async () => {
    if (!resendEmail) {
      return;
    }

    setIsResending(true);
    setResendFeedback(null);

    try {
      const { data } = await api.post<ResendResponse>(
        "/auth/resend-verification/",
        { email: resendEmail },
      );
      const detail =
        data?.detail ??
        "If an account exists for this email, we've sent a fresh verification link.";
      setResendFeedback(detail);
    } catch (error) {
      const axiosError = error as AxiosError<ResendResponse>;
      const structuredError = extractErrorMessage(
        axiosError.response?.data?.error,
      );
      const detail =
        axiosError.response?.data?.detail ??
        structuredError ??
        "Could not resend the verification email. Please try again.";
      setResendFeedback(detail);
    } finally {
      setIsResending(false);
    }
  }, [resendEmail]);

  const cardStyles = useMemo(() => {
    if (status === "success") {
      return "border-emerald-200 bg-emerald-50 text-emerald-900";
    }

    if (status === "error") {
      return "border-red-200 bg-red-50 text-red-900";
    }

    return "border-border bg-card text-foreground";
  }, [status]);

  const headingText =
    status === "success" ? "Email verified" : "Verify your email";

  return (
    <div className="mx-auto max-w-md space-y-6 p-6 text-center">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{headingText}</h1>
        <p className="text-sm text-muted-foreground">
          Follow the link we sent to finish setting up your StatusWatch account.
        </p>
      </header>

      <div className={`rounded border p-5 text-left ${cardStyles}`}>
        <p className="text-base font-medium">{message}</p>

        {status === "success" && (
          <div className="mt-4 space-y-2">
            <p className="text-sm">
              You're all set! Continue to the dashboard to sign in with your new
              account.
            </p>
            <button
              type="button"
              onClick={handleContinue}
              className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
            >
              Continue to Login
            </button>
          </div>
        )}

        {status === "error" && resendEmail && (
          <div className="mt-4 space-y-3">
            <p className="text-sm">
              Need a new link? We'll resend to{" "}
              <span className="font-semibold">{resendEmail}</span>.
            </p>
            <button
              type="button"
              onClick={handleResend}
              disabled={isResending}
              className="w-full rounded border border-current px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isResending ? "Resending…" : "Resend Link"}
            </button>
            {resendFeedback && <p className="text-sm">{resendFeedback}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
