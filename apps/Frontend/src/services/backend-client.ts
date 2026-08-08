/* eslint-disable @typescript-eslint/no-explicit-any */
import { createClient } from "@/lib/supabase/client";
import { ApiError } from "@/types/api/common";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://ai-study-api.redstone-7dd5a6fe.italynorth.azurecontainerapps.io";

async function getSessionToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || null;
}

async function refreshSessionToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const supabase = createClient();
  const { data: { session }, error } = await supabase.auth.refreshSession();
  if (error || !session) {
    return null;
  }
  return session.access_token;
}

async function normalizeError(response: Response): Promise<ApiError> {
  let details: any = null;
  let message = "An error occurred while communicating with the server.";
  let code = "API_ERROR";

  try {
    const errorData = await response.json();
    if (errorData) {
      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        message = errorData.detail.map((d: any) => d.msg).join(", ");
        details = errorData.detail;
      } else if (errorData.detail?.message) {
        message = errorData.detail.message;
        code = errorData.detail.code || code;
      } else if (errorData.message) {
        message = errorData.message;
        code = errorData.code || code;
      }
    }
  } catch {
    // Fallback if not JSON
  }

  return {
    status: response.status,
    code,
    message,
    details,
  };
}

interface RequestOptions extends RequestInit {
  body?: any;
  isStream?: boolean;
}

async function request(path: string, options: RequestOptions = {}, isRetry = false): Promise<any> {
  const token = await getSessionToken();
  if (!token) {
    throw {
      status: 401,
      code: "NO_ACTIVE_SESSION",
      message: "No active session found. Please log in.",
    } as ApiError;
  }

  const url = `${API_URL}${path}`;
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);

  let body = options.body;
  if (body) {
    if (!(body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }
  }

  const fetchOptions: RequestInit = {
    ...options,
    headers,
    body,
  };

  try {
    const response = await fetch(url, fetchOptions);

    if (response.status === 401) {
      if (!isRetry) {
        const newToken = await refreshSessionToken();
        if (newToken) {
          return request(path, options, true);
        }
      }

      // Important: never hard-redirect to /auth/login from a backend API 401.
      // The Supabase browser session can still be valid while the Azure backend
      // is misconfigured. Redirecting created a login -> dashboard loop that
      // kicked users out of open notes whenever the AI panel mounted.
      const error = await normalizeError(response);
      throw {
        ...error,
        code: "BACKEND_AUTH_REJECTED",
        message:
          error.message ||
          "The AI backend rejected the current session. Your note remains open; please retry after backend configuration is fixed.",
      } as ApiError;
    }

    if (!response.ok) {
      throw await normalizeError(response);
    }

    if (options.isStream) {
      return response;
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return await response.json();
    }
    return await response.text();
  } catch (error) {
    if ((error as any).status) {
      throw error;
    }
    throw {
      status: 0,
      code: "NETWORK_ERROR",
      message: (error as Error).message || "Network request failed. Please check your connection.",
      details: error,
    } as ApiError;
  }
}

export const backendClient = {
  async get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return request(path, { ...options, method: "GET" });
  },

  async post<T>(path: string, body?: any, options: RequestOptions = {}): Promise<T> {
    return request(path, { ...options, method: "POST", body });
  },

  async put<T>(path: string, body?: any, options: RequestOptions = {}): Promise<T> {
    return request(path, { ...options, method: "PUT", body });
  },

  async delete<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return request(path, { ...options, method: "DELETE" });
  },

  async stream(path: string, body?: any, options: RequestOptions = {}): Promise<Response> {
    return request(path, { ...options, method: "POST", body, isStream: true });
  }
};
