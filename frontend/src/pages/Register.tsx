import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import type { AxiosError } from "axios";

import { api } from "@/lib/api";

const registerSchema = z.object({
  organization_name: z.string().min(1, "Organization name is required."),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(8, "Password must be at least 8 characters long."),
  password_confirm: z
    .string()
    .min(8, "Confirm password must be at least 8 characters long."),
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

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      organization_name: "",
      email: "",
      password: "",
      password_confirm: "",
    },
  });

  const onSubmit = async (values: RegisterFormValues) => {
    setFormError(null);
    if (values.password !== values.password_confirm) {
      setError("password_confirm", {
        type: "validate",
        message: "Passwords must match.",
      });
      return;
    }

    try {
      const { data } = await api.post("/auth/register/", values);
      const detail = data?.detail ?? "Registration successful. Please log in.";
      await navigate({
        to: "/login",
        state: (prev) => ({ ...(prev ?? {}), message: detail }),
        replace: true,
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
        setFormError("Registration failed.");
      }
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold">Create your organization</h1>
        <p className="text-sm text-muted-foreground">
          Sign up to provision a new StatusWatch workspace.
        </p>
      </header>
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
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
            className="w-full rounded border border-border px-3 py-2"
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
            className="w-full rounded border border-border px-3 py-2"
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
            className="w-full rounded border border-border px-3 py-2"
            {...register("password")}
          />
          {errors.password && (
            <p className="text-sm text-red-600">{errors.password.message}</p>
          )}
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
            className="w-full rounded border border-border px-3 py-2"
            {...register("password_confirm")}
          />
          {errors.password_confirm && (
            <p className="text-sm text-red-600">
              {errors.password_confirm.message}
            </p>
          )}
        </div>

        {formError && <p className="text-sm text-red-600">{formError}</p>}

        <button
          type="submit"
          className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing Up…" : "Sign Up"}
        </button>
      </form>
    </div>
  );
}
