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

function handleRedirectToLogin() {
  if (typeof window !== "undefined") {
    window.location.href = "/auth/login";
  }
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
        // Validation errors
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
    if (body instanceof FormData) {
      // Do NOT set Content-Type, boundary is automatically added by browser
    } else {
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
        } else {
          handleRedirectToLogin();
          throw {
            status: 401,
            code: "UNAUTHORIZED",
            message: "Session expired. Please log in again.",
          } as ApiError;
        }
      } else {
        handleRedirectToLogin();
        throw await normalizeError(response);
      }
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
