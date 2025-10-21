// frontend/src/lib/api.ts
import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type AxiosResponse,
} from "axios";
import { API_BASE, apiUrl } from "./env";
import {
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  storeAuthTokens,
  type AuthTokens,
} from "./auth";

interface AuthAxiosRequestConfig extends AxiosRequestConfig {
  _retry?: boolean;
  skipAuthRefresh?: boolean;
  skipAuthToken?: boolean;
}

type TokenPair = {
  access?: string;
  refresh?: string | null;
};

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000, // 30 second timeout
  headers: {
    "Content-Type": "application/json",
  },
});

// Debug logging
api.interceptors.request.use((cfg) => {
  const config = cfg as AuthAxiosRequestConfig;

  console.log("🚀 API Request:", {
    method: config.method?.toUpperCase(),
    url: config.url,
    baseURL: config.baseURL,
    fullURL: `${config.baseURL ?? API_BASE}${config.url ?? ""}`,
    data: config.data,
  });

  if (!config.skipAuthToken) {
    const token = getAccessToken();
    if (token) {
      if (!config.headers) {
        config.headers = {};
      }

      const headers = config.headers as Record<string, string> & {
        set?: (key: string, value: string) => void;
      };

      if (typeof headers.set === "function") {
        headers.set("Authorization", `Bearer ${token}`);
      } else {
        headers.Authorization = `Bearer ${token}`;
      }
    }
  }

  return cfg;
});

// Debug response/error logging
api.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log("✅ API Response:", {
      status: response.status,
      url: response.config.url,
      data: response.data,
    });
    return response;
  },
  async (error: AxiosError) => {
    console.error("❌ API Error:", {
      message: error.message,
      code: error.code,
      url: error.config?.url,
      status: error.response?.status,
      data: error.response?.data,
    });

    const originalRequest = error.config as AuthAxiosRequestConfig | undefined;
    const status = error.response?.status;

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.skipAuthRefresh
    ) {
      originalRequest._retry = true;

      try {
        const tokens = await ensureFreshTokens();
        if (!tokens) {
          throw error;
        }

        if (!originalRequest.headers) {
          originalRequest.headers = {};
        }

        const headers = originalRequest.headers as Record<string, string> & {
          set?: (key: string, value: string) => void;
        };

        if (typeof headers.set === "function") {
          headers.set("Authorization", `Bearer ${tokens.access}`);
        } else {
          headers.Authorization = `Bearer ${tokens.access}`;
        }

        return api(originalRequest);
      } catch (refreshError) {
        clearAuthTokens();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

let refreshPromise: Promise<AuthTokens | null> | null = null;

async function ensureFreshTokens(): Promise<AuthTokens | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  if (!refreshPromise) {
    refreshPromise = requestTokenRefresh(refreshToken)
      .then((pair) => {
        if (!pair?.access) {
          throw new Error("Missing access token during refresh.");
        }

        const nextTokens: AuthTokens = {
          access: pair.access,
          refresh: pair.refresh ?? refreshToken,
        };

        storeAuthTokens(nextTokens);
        return nextTokens;
      })
      .catch((err) => {
        clearAuthTokens();
        throw err;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

function requestTokenRefresh(token: string): Promise<TokenPair> {
  return axios
    .post<TokenPair>(
      apiUrl("/auth/token/refresh/"),
      { refresh: token },
      {
        headers: { "Content-Type": "application/json" },
      }
    )
    .then((response) => response.data);
}

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

export interface CurrentUserResponse {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  date_joined: string;
  groups: string[];
}

export async function fetchCurrentUser(): Promise<CurrentUserResponse> {
  const { data } = await api.get<CurrentUserResponse>("/auth/me/");
  return data;
}

export async function submitLogout(refreshToken: string) {
  await api.post("/auth/logout/", { refresh: refreshToken });
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
