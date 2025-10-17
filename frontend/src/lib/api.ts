import axios from 'axios';
import { API_BASE } from './config';

export const api = axios.create({ baseURL: API_BASE });

export const API_BASE =
  import.meta.env.VITE_API_BASE || "https://acme.statuswatch.local";

export async function login(username: string, password: string) {
  const r = await fetch(`${API_BASE}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || "Login failed");
  return d.access as string;
}

export async function stripePublicKey() {
  const r = await fetch(`${API_BASE}/api/pay/config/`);
  return (await r.json()).publicKey as string;
}

export async function createCheckout(access: string, amount: number) {
  const r = await fetch(`${API_BASE}/api/pay/create-checkout-session/`, {
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

// Attach JWT from localStorage if present
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('jwt');
  if (token) {
    cfg.headers = cfg.headers ?? {};
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});