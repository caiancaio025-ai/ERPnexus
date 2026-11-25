import { ApiError, extractApiMessage } from "./apiError";
import type { ApiRequestOptions } from "./types";
import { buildApiUrl, fetchJson, TransportError } from "./requestPolicy";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "/api";

const DEFAULT_ERROR = "Não foi possível concluir a operação.";

let redirectingToLogin = false;

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
    timeoutMs,
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
  let payload: unknown;
  try {
    ({ response, payload } = await fetchJson(buildApiUrl(url, API_BASE_URL), {
      credentials: "include",
      cache: "no-store",
      ...requestOptions,
      headers,
    }, { timeoutMs }));
  } catch (error) {
    if (error instanceof TransportError) {
      throw new ApiError(error.message, 0, error, error.requestId);
    }
    throw error;
  }

  if (!response.ok) {
    const fallback =
      response.status === 401
        ? "Sua sessão expirou. Entre novamente."
        : response.status === 403
          ? "Você não tem permissão para realizar esta operação."
          : response.status === 409
            ? "Este registro foi atualizado por outra operação. Atualize os dados antes de salvar novamente."
            : response.status === 413
              ? "O arquivo ultrapassa o tamanho permitido. Escolha um arquivo menor."
              : response.status === 429
                ? "Muitas solicitações ao mesmo tempo. Aguarde alguns instantes e tente novamente."
                : response.status >= 500
                  ? "O servidor não conseguiu concluir a operação. Tente novamente após conferir o registro."
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
      response.headers.get("x-request-id"),
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