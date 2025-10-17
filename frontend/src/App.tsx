import { useState } from "react";
import { API_BASE } from "./lib/env";

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>("");

  async function login() {
    setMsg("Logging in…");
    try {
      const r = await fetch(`${API_BASE}/auth/token/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "jwt", password: "jwtpass123" }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Login failed");
      setToken(d.access);
      setMsg("✅ Logged in");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  }

  async function pay() {
    if (!token) return setMsg("❌ Login first");
    setMsg("Creating checkout session…");
    try {
      const r = await fetch(`${API_BASE}/pay/create-checkout-session/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ amount: 500, currency: "usd", name: "Demo" }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "Checkout failed");
      if (d.url) window.location.href = d.url;
      else setMsg("❌ No URL returned");
    } catch (e: any) {
      setMsg(`❌ ${e.message}`);
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">StatusWatch (frontend smoke test)</h1>
      <p className="mb-4 text-sm text-slate-600">
        API base: <code>{API_BASE}</code>
      </p>
      <div className="flex gap-2">
        <button onClick={login} className="px-4 py-2 rounded bg-slate-900 text-white">
          Login (jwt/jwtpass123)
        </button>
        <button onClick={pay} className="px-4 py-2 rounded bg-emerald-600 text-white">
          Pay $5
        </button>
      </div>
      <p className="mt-4">{msg}</p>
    </div>
  );
}
