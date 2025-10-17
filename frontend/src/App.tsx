import { useState } from "react";

const API_BASE = "https://acme.statuswatch.local/api"; // dev: call tenant backend via proxy

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>("");

  async function login() {
  try {
    setMsg("Logging in…");
    const r = await fetch(`${API_BASE}/auth/token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // IMPORTANT: no credentials: "include"
      body: JSON.stringify({ username: "jwt", password: "jwtpass123" }),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`${r.status} ${r.statusText}: ${t}`);
    }
    const data = await r.json();
    if (data.access) {
      setToken(data.access);
      setMsg("✅ Logged in");
    } else {
      setMsg("❌ No token returned");
    }
  } catch (e: any) {
    console.error(e);
    setMsg(`❌ ${e.message}`);
  }
}


  async function pay() {
    if (!token) return setMsg("❌ Login first");
    setMsg("Creating checkout session…");
    const r = await fetch(`${API_BASE}/pay/create-checkout-session/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ amount: 500, currency: "usd", name: "Demo" }),
    });
    const data = await r.json();
    if (data.url) {
      window.location.href = data.url;
    } else {
      setMsg(`❌ ${data.error || "No URL returned"}`);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">StatusWatch (dev)</h1>
      <div className="flex gap-3">
        <button
          onClick={login}
          className="px-4 py-2 rounded bg-slate-900 text-white"
        >
          Login (jwt/jwtpass123)
        </button>
        <button
          onClick={pay}
          className="px-4 py-2 rounded bg-emerald-600 text-white"
        >
          Pay $5
        </button>
      </div>
      <p className="mt-4">{msg}</p>
    </div>
  );
}
