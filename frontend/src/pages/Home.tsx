import { Link } from "@tanstack/react-router";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { STRIPE_PK } from "@/lib/config";
import { storeAuthTokens } from "@/lib/auth";

export default function Home() {
  const loginDemo = async () => {
    try {
      const { data } = await api.post("/auth/token/", {
        username: "jwt",
        password: "JwtP@ss123456",
      });
      storeAuthTokens({ access: data.access, refresh: data.refresh });
      toast.success("Logged in (jwt)");
    } catch (error: unknown) {
      const detail =
        typeof error === "object" && error !== null && "response" in error
          ? (error as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail
          : undefined;
      toast.error(detail ?? "Login failed");
    }
  };

  const ping = async () => {
    const { data } = await api.get("/ping/");
    toast.info(`ping: ${JSON.stringify(data)}`);
  };

  const pay = async () => {
    if (!STRIPE_PK) {
      toast.error("Missing VITE_STRIPE_PUBLIC_KEY");
      return;
    }
    const { data } = await api.post("/pay/create-checkout-session/", {
      amount: 500,
      currency: "usd",
      name: "Demo",
    });
    if (data?.url) {
      window.location.href = data.url;
    } else {
      toast.error("No checkout URL from backend");
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 p-6">
      <div className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-3xl font-bold">StatusWatch (dev)</h1>

        <div className="flex gap-3">
          <button
            onClick={loginDemo}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
            title="uses /api/auth/token/"
          >
            Login (jwt/JwtP@ss123456)
          </button>

          <button
            onClick={ping}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
          >
            Ping API
          </button>

          <button
            onClick={pay}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500"
          >
            Pay $5
          </button>
        </div>

        <div>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          >
            Create your organization
          </Link>
        </div>

        <p className="text-sm text-neutral-400">
          API base: <code>{import.meta.env.VITE_API_BASE}</code>
        </p>
      </div>
    </div>
  );
}
