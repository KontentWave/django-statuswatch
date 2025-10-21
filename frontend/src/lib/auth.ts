const ACCESS_TOKEN_KEY = "jwt";
const REFRESH_TOKEN_KEY = "jwt_refresh";

export interface AuthTokens {
  access: string;
  refresh?: string | null;
}

export function storeAuthTokens(tokens: AuthTokens) {
  const { access, refresh } = tokens;
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  if (refresh) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
