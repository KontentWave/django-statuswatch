// frontend/src/lib/api.ts
import axios from "axios";
import { API_BASE, apiUrl } from "./env";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000, // 30 second timeout
  headers: {
    "Content-Type": "application/json",
  },
});

// Debug logging
api.interceptors.request.use((cfg) => {
  console.log("🚀 API Request:", {
    method: cfg.method?.toUpperCase(),
    url: cfg.url,
    baseURL: cfg.baseURL,
    fullURL: `${cfg.baseURL}${cfg.url}`,
    data: cfg.data,
  });

  const token = localStorage.getItem("jwt");
  if (token) {
    cfg.headers = cfg.headers ?? {};
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});

// Debug response/error logging
api.interceptors.response.use(
  (response) => {
    console.log("✅ API Response:", {
      status: response.status,
      url: response.config.url,
      data: response.data,
    });
    return response;
  },
  (error) => {
    console.error("❌ API Error:", {
      message: error.message,
      code: error.code,
      url: error.config?.url,
      status: error.response?.status,
      data: error.response?.data,
    });
    return Promise.reject(error);
  }
);

export async function login(username: string, password: string) {
  const r = await fetch(apiUrl("/auth/token/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || "Login failed");
  return d.access as string;
}

export async function stripePublicKey() {
  const r = await fetch(apiUrl("/pay/config/"));
  const d = await r.json();
  return d.publicKey as string;
}

export async function createCheckout(access: string, amount: number) {
  const r = await fetch(apiUrl("/pay/create-checkout-session/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${access}`,
    },
    body: JSON.stringify({ amount, currency: "usd", name: "Demo" }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || "Checkout failed");
  return d.url as string;
}
