import { ApiError, extractApiMessage } from "./apiError";
import type { ApiRequestOptions } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "/api";

const DEFAULT_ERROR = "Não foi possível concluir a operação.";

let redirectingToLogin = false;

function isAbsoluteUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

function buildRequestUrl(url: string): string {
  if (isAbsoluteUrl(url)) {
    return url;
  }

  const normalizedPath = url.startsWith("/") ? url : `/${url}`;

  if (
    normalizedPath === API_BASE_URL ||
    normalizedPath.startsWith(`${API_BASE_URL}/`)
  ) {
    return normalizedPath;
  }

  return `${API_BASE_URL}${normalizedPath}`;
}

function isJsonResponse(response: Response): boolean {
  return (
    response.headers
      .get("content-type")
      ?.includes("application/json") ?? false
  );
}

async function readPayload(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  if (isJsonResponse(response)) {
    return response.json().catch(() => undefined);
  }

  const text = await response.text().catch(() => "");

  return text || undefined;
}

function handleUnauthorized(): void {
  if (
    redirectingToLogin ||
    window.location.pathname === "/login"
  ) {
    return;
  }

  redirectingToLogin = true;

  window.dispatchEvent(
    new CustomEvent("nexus:session-expired"),
  );
}

async function request<T>(
  url: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    redirectOnUnauthorized = true,
    headers: providedHeaders,
    ...requestOptions
  } = options;

  const headers = new Headers(providedHeaders);
  const isFormData =
    requestOptions.body instanceof FormData;

  if (
    requestOptions.body &&
    !isFormData &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let response: Response;

  try {
    response = await fetch(buildRequestUrl(url), {
      credentials: "include",
      cache: "no-store",
      ...requestOptions,
      headers,
    });
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === "AbortError"
    ) {
      throw error;
    }

    throw new ApiError(
      "Não foi possível conectar ao servidor. Verifique se a API está em execução.",
      0,
      error,
    );
  }

  const payload = await readPayload(response);

  if (!response.ok) {
    const fallback =
      response.status === 401
        ? "Sua sessão expirou. Entre novamente."
        : response.status === 403
          ? "Você não tem permissão para realizar esta operação."
          : DEFAULT_ERROR;

    if (
      response.status === 401 &&
      redirectOnUnauthorized
    ) {
      handleUnauthorized();
    }

    throw new ApiError(
      extractApiMessage(payload, fallback),
      response.status,
      payload,
    );
  }

  redirectingToLogin = false;

  return payload as T;
}

export const apiClient = {
  request,

  get<T>(
    url: string,
    options?: ApiRequestOptions,
  ) {
    return request<T>(url, {
      ...options,
      method: "GET",
    });
  },

  post<T>(
    url: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ) {
    return request<T>(url, {
      ...options,
      method: "POST",
      body:
        body instanceof FormData
          ? body
          : body === undefined
            ? undefined
            : JSON.stringify(body),
    });
  },

  put<T>(
    url: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ) {
    return request<T>(url, {
      ...options,
      method: "PUT",
      body:
        body instanceof FormData
          ? body
          : body === undefined
            ? undefined
            : JSON.stringify(body),
    });
  },

  patch<T>(
    url: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ) {
    return request<T>(url, {
      ...options,
      method: "PATCH",
      body:
        body instanceof FormData
          ? body
          : body === undefined
            ? undefined
            : JSON.stringify(body),
    });
  },

  delete<T>(
    url: string,
    options?: ApiRequestOptions,
  ) {
    return request<T>(url, {
      ...options,
      method: "DELETE",
    });
  },
};