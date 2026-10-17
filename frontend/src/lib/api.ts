import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, any>;
  constructor(message: string, status = 0, code = "network_error", details: Record<string, any> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const http = axios.create({ baseURL: API_BASE_URL, withCredentials: true, timeout: 60_000 });
const bare = axios.create({ baseURL: API_BASE_URL, withCredentials: true, timeout: 30_000 });

// ----------------------------------------------------------------- tokens
let accessToken: string | null = null;
let refreshing: Promise<RefreshResult | null> | null = null;
let onSessionLost: (() => void) | null = null;

export type RefreshResult = { access_token: string; user: import("./types").User };

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};
export const getAccessToken = () => accessToken;
export const setSessionLostHandler = (fn: (() => void) | null) => {
  onSessionLost = fn;
};

/** One refresh at a time; concurrent 401s share it. */
export function refreshSession(): Promise<RefreshResult | null> {
  if (!refreshing) {
    refreshing = bare
      .post<RefreshResult>("/auth/refresh")
      .then((r) => {
        accessToken = r.data.access_token;
        return r.data;
      })
      .catch((error: AxiosError) => {
        if (error.response && [401, 403].includes(error.response.status)) {
          accessToken = null;
          return null;
        }
        throw toApiError(error);
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) config.headers.set("Authorization", `Bearer ${accessToken}`);
  return config;
});

const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout", "/auth/verify-email", "/auth/reset-password", "/auth/forgot-password"];

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;
    if (!original || status !== 401 || original._retried || NO_REFRESH.some((p) => original.url?.startsWith(p))) {
      throw error;
    }
    original._retried = true;
    let refreshed: RefreshResult | null = null;
    try {
      refreshed = await refreshSession();
    } catch {
      throw error; // network trouble: keep the session, surface the error
    }
    if (!refreshed) {
      onSessionLost?.();
      throw error;
    }
    original.headers.set("Authorization", `Bearer ${refreshed.access_token}`);
    return http.request(original);
  },
);

// ----------------------------------------------------------------- errors
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return new ApiError(
        error.code === "ECONNABORTED" ? "The request took too long. Check your connection and try again." : "Can't reach Streixpei right now. Check your connection.",
        0,
        "network_error",
      );
    }
    const data = error.response.data as any;
    const body = data?.error;
    const message = body?.message ?? (typeof data?.detail === "string" ? data.detail : null) ?? "Something went wrong. Please try again.";
    return new ApiError(message, error.response.status, body?.code ?? "http_error", body?.details ?? {});
  }
  return new ApiError(error instanceof Error ? error.message : "Something went wrong.");
}

async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await http.request<T>(config);
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export const api = {
  get: <T>(url: string, params?: Record<string, unknown>) => request<T>({ method: "get", url, params }),
  post: <T>(url: string, data?: unknown) => request<T>({ method: "post", url, data }),
  patch: <T>(url: string, data?: unknown) => request<T>({ method: "patch", url, data }),
  delete: <T>(url: string) => request<T>({ method: "delete", url }),
  upload: <T>(url: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>({ method: "post", url, data: form });
  },
  /** Downloads an authenticated file (CSV/XLSX export). */
  download: async (url: string, fallbackName: string, params?: Record<string, unknown>) => {
    try {
      const response = await http.get<Blob>(url, { params, responseType: "blob" });
      const disposition = String(response.headers["content-disposition"] ?? "");
      const match = /filename="?([^";]+)"?/i.exec(disposition);
      const href = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = href;
      a.download = match?.[1] ?? fallbackName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(href), 2000);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const parsed = JSON.parse(text);
          throw new ApiError(parsed?.error?.message ?? "Download failed.", error.response.status);
        } catch (inner) {
          if (inner instanceof ApiError) throw inner;
        }
      }
      throw toApiError(error);
    }
  },
};

/** Public calls that must never carry the manager's token (staff onboarding). */
export const publicApi = {
  get: async <T>(url: string) => {
    try {
      return (await bare.get<T>(url)).data;
    } catch (e) {
      throw toApiError(e);
    }
  },
  post: async <T>(url: string, data?: unknown) => {
    try {
      return (await bare.post<T>(url, data)).data;
    } catch (e) {
      throw toApiError(e);
    }
  },
};
