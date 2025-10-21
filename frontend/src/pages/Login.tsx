import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { AxiosError } from "axios";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { api } from "@/lib/api";
import { customZodResolver } from "@/lib/zodResolver";
import { storeAuthTokens } from "@/lib/auth";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

type LoginApiResponse = {
  access?: string;
  refresh?: string;
  detail?: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState<string | null>(null);

  const registrationMessage = useMemo(() => {
    const state = location.state;
    if (state && typeof state === "object" && "message" in state) {
      const message = (state as { message?: unknown }).message;
      return typeof message === "string" ? message : null;
    }
    return null;
  }, [location.state]);

  const redirectTo = useMemo<"/dashboard" | null>(() => {
    const state = location.state;
    if (state && typeof state === "object" && "redirectTo" in state) {
      const destination = (state as { redirectTo?: unknown }).redirectTo;
      return destination === "/dashboard" ? "/dashboard" : null;
    }
    return null;
  }, [location.state]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: customZodResolver(loginSchema),
    mode: "onSubmit",
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);

    try {
      const { data } = await api.post<LoginApiResponse>("/auth/token/", {
        username: values.email,
        password: values.password,
      });

      const accessToken = data?.access;
      if (!accessToken) {
        throw new Error("Missing access token in response.");
      }

      storeAuthTokens({ access: accessToken, refresh: data?.refresh });

      const destination = (redirectTo ?? "/dashboard") as "/dashboard";
      await navigate({ to: destination, replace: true });
    } catch (err) {
      const error = err as AxiosError<LoginApiResponse>;
      const detail =
        error.response?.data?.detail ??
        (error instanceof Error ? error.message : null);

      setFormError(detail ?? "Invalid email or password.");
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold">Sign in to StatusWatch</h1>
        <p className="text-sm text-muted-foreground">
          Enter your workspace email to access your dashboard.
        </p>
        {registrationMessage && (
          <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-left">
            <p className="text-sm text-emerald-700">{registrationMessage}</p>
          </div>
        )}
      </header>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
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
            autoComplete="current-password"
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
          {isSubmitting ? "Signing In…" : "Sign In"}
        </button>
      </form>
    </div>
  );
}
