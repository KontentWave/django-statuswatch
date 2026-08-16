import { useCallback, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useNavigate } from "@tanstack/react-router";
import type { AxiosError } from "axios";

import { api } from "@/lib/api";
import { PasswordStrengthIndicator } from "@/components/PasswordStrengthIndicator";
import { customZodResolver } from "@/lib/zodResolver";

const SUCCESS_STORAGE_KEY = "statuswatch.registrationSuccess";
const DEFAULT_SUCCESS_DETAIL =
  "Registration successful! Please check your email to verify your account before logging in.";

type RegistrationSuccessPayload = {
  email: string;
  organization: string;
  detail: string;
};

function readStoredRegistrationSuccess(): RegistrationSuccessPayload | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.sessionStorage.getItem(SUCCESS_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as RegistrationSuccessPayload;
  } catch {
    window.sessionStorage.removeItem(SUCCESS_STORAGE_KEY);
    return null;
  }
}

// Password validation matching backend requirements (P1-01)
const passwordSchema = z
  .string()
  .min(12, "Password must be at least 12 characters long.")
  .max(128, "Password must not exceed 128 characters.")
  .regex(/[A-Z]/, "Password must contain at least one uppercase letter.")
  .regex(/[a-z]/, "Password must contain at least one lowercase letter.")
  .regex(/\d/, "Password must contain at least one number.")
  .regex(
    /[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/,
    "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)."
  );

const registerSchema = z
  .object({
    organization_name: z
      .string()
      .min(1, "Organization name is required.")
      .max(100, "Organization name is too long."),
    email: z
      .string()
      .min(1, "Email is required.")
      .email("Enter a valid email address."),
    password: passwordSchema,
    password_confirm: z.string().min(1, "Please confirm your password."),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: "Passwords must match.",
    path: ["password_confirm"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

type RegisterApiError = {
  detail?: string;
  errors?: Record<keyof RegisterFormValues | string, string[]>;
};

function buildFieldName(name: string): keyof RegisterFormValues | undefined {
  if (
    ["organization_name", "email", "password", "password_confirm"].includes(
      name
    )
  ) {
    return name as keyof RegisterFormValues;
  }
  return undefined;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const [formError, setFormError] = useState<string | null>(null);
  const [successPayload, setSuccessPayload] =
    useState<RegistrationSuccessPayload | null>(() =>
      readStoredRegistrationSuccess()
    );

  const persistSuccess = useCallback((payload: RegistrationSuccessPayload) => {
    setSuccessPayload(payload);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(
        SUCCESS_STORAGE_KEY,
        JSON.stringify(payload)
      );
    }
  }, []);

  const clearSuccessState = useCallback(() => {
    setSuccessPayload(null);
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(SUCCESS_STORAGE_KEY);
    }
  }, []);

  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: customZodResolver(registerSchema),
    mode: "onSubmit",
    reValidateMode: "onChange",
    defaultValues: {
      organization_name: "",
      email: "",
      password: "",
      password_confirm: "",
    },
  });

  // Watch password field for strength indicator
  const password = watch("password");

  const onSubmit = async (values: RegisterFormValues) => {
    setFormError(null);
    clearSuccessState();

    try {
      const { data } = await api.post("/auth/register/", values);
      const detail = data?.detail ?? DEFAULT_SUCCESS_DETAIL;

      persistSuccess({
        detail,
        email: values.email,
        organization: values.organization_name,
      });
    } catch (err) {
      const error = err as AxiosError<RegisterApiError>;
      const responseData = error.response?.data;
      let hasFieldErrors = false;
      if (responseData?.errors) {
        Object.entries(responseData.errors).forEach(([field, messages]) => {
          const name = buildFieldName(field);
          if (name) {
            hasFieldErrors = true;
            setError(name, {
              type: "server",
              message: messages.join(" "),
            });
          }
        });
      }
      if (responseData?.detail) {
        setFormError(responseData.detail);
      } else if (!hasFieldErrors) {
        setFormError("Registration failed. Please try again.");
      }
    }
  };

  const headerCopy = useMemo(() => {
    if (successPayload) {
      return {
        title: "Check your inbox",
        subtitle:
          "We emailed a verification link so you can finish setting up your workspace.",
      };
    }

    return {
      title: "Create your organization",
      subtitle: "Sign up to provision a new StatusWatch workspace.",
    };
  }, [successPayload]);

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold">{headerCopy.title}</h1>
        <p className="text-sm text-muted-foreground">{headerCopy.subtitle}</p>
      </header>

      {successPayload ? (
        <div
          data-testid="registration-success"
          className="space-y-4 rounded border border-emerald-200 bg-emerald-50 p-5 text-left"
        >
          <p className="text-base font-semibold text-emerald-800">
            {successPayload.detail || DEFAULT_SUCCESS_DETAIL}
          </p>
          <p className="text-sm text-emerald-800">
            Check your inbox — we sent a verification link to{" "}
            <span className="font-semibold">{successPayload.email}</span> for{" "}
            <span className="font-semibold">{successPayload.organization}</span>
            . Finish verification to access your dashboard.
          </p>

          <div className="flex flex-col gap-2 pt-2">
            <button
              type="button"
              className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
              onClick={() =>
                navigate({
                  to: "/login",
                  state: (prev) => ({
                    ...(prev ?? {}),
                    message: successPayload.detail || DEFAULT_SUCCESS_DETAIL,
                  }),
                  replace: true,
                })
              }
            >
              Continue to Login
            </button>
            <button
              type="button"
              className="w-full rounded border border-emerald-300 px-3 py-2 text-sm font-medium text-emerald-900 hover:bg-emerald-100"
              onClick={clearSuccessState}
            >
              Register another organization
            </button>
          </div>
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <div className="space-y-1">
            <label
              className="block text-sm font-medium"
              htmlFor="organization_name"
            >
              Organization Name
            </label>
            <input
              id="organization_name"
              type="text"
              autoComplete="organization"
              className={`w-full rounded border px-3 py-2 ${
                errors.organization_name
                  ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                  : "border-border"
              }`}
              {...register("organization_name")}
            />
            {errors.organization_name && (
              <p className="text-sm text-red-600">
                {errors.organization_name.message}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={`w-full rounded border px-3 py-2 ${
                errors.email
                  ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                  : "border-border"
              }`}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-red-600">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              className={`w-full rounded border px-3 py-2 ${
                errors.password
                  ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                  : "border-border"
              }`}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-red-600">{errors.password.message}</p>
            )}
            {/* Password strength indicator */}
            <PasswordStrengthIndicator password={password} />
          </div>

          <div className="space-y-1">
            <label
              className="block text-sm font-medium"
              htmlFor="password_confirm"
            >
              Confirm Password
            </label>
            <input
              id="password_confirm"
              type="password"
              autoComplete="new-password"
              className={`w-full rounded border px-3 py-2 ${
                errors.password_confirm
                  ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                  : "border-border"
              }`}
              {...register("password_confirm")}
            />
            {errors.password_confirm && (
              <p className="text-sm text-red-600">
                {errors.password_confirm.message}
              </p>
            )}
          </div>

          {formError && (
            <div className="rounded border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-600">{formError}</p>
            </div>
          )}

          <button
            type="submit"
            className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing Up…" : "Sign Up"}
          </button>
        </form>
      )}
    </div>
  );
}
