/** Transport policy shared by every module. Writes are never replayed automatically. */
export class TransportError extends Error {
  readonly kind: "network" | "timeout" | "invalid_response";
  readonly requestId: string | null;
  constructor(
    message: string,
    kind: "network" | "timeout" | "invalid_response",
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "TransportError";
    this.kind = kind;
    this.requestId = requestId;
  }
}

export function buildApiUrl(url: string, base = "/api"): string {
  if (/^https?:\/\//i.test(url)) return url;
  const normalizedBase = base.replace(/\/+$/, "");
  let path = url.startsWith("/") ? url : `/${url}`;
  // Callers historically use both /api/module and /module. An absolute base
  // must not turn the former into https://server/api/api/module.
  if (!/^https?:\/\//i.test(normalizedBase) && (path === normalizedBase || path.startsWith(`${normalizedBase}/`))) return path;
  if (path === "/api" || path.startsWith("/api/")) path = path.slice(4);
  return `${normalizedBase}${path}`;
}

export type TransportResult = { response: Response; payload: unknown };
export type TransportOptions = {
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
};

export async function fetchJson(
  url: string,
  options: RequestInit = {},
  policy: TransportOptions = {},
): Promise<TransportResult> {
  const method = (options.method || "GET").toUpperCase();
  const safeRead = method === "GET" || method === "HEAD";
  const retries = safeRead ? Math.max(0, Math.min(policy.retries ?? 1, 2)) : 0;
  const timeoutMs = policy.timeoutMs ?? (safeRead ? 30_000 : 120_000);
  for (let attempt = 0; ; attempt += 1) {
    options.signal?.throwIfAborted();
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort(options.signal?.reason);
    options.signal?.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    let result: TransportResult;
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      const requestId = response.headers.get("x-request-id");
      const text = response.status === 204 || method === "HEAD" ? "" : await response.text();
      let payload: unknown;
      if (text) {
        const type = response.headers.get("content-type") || "";
        if (type.includes("application/json") || type.includes("+json")) {
          try { payload = JSON.parse(text); }
          catch {
            if (response.ok) throw new TransportError("O servidor enviou uma resposta incompleta. Confira o registro antes de repetir a gravação.", "invalid_response", requestId);
          }
        } else if (response.ok) {
          throw new TransportError("O endereço da API retornou uma página inesperada. Atualize a tela e confira a configuração do servidor.", "invalid_response", requestId);
        }
      } else if (response.ok && response.status !== 204 && method !== "HEAD") {
        throw new TransportError("O servidor não confirmou os dados da operação. Confira o registro antes de repetir a gravação.", "invalid_response", requestId);
      }
      result = { response, payload };
    } catch (cause) {
      if (options.signal?.aborted) throw options.signal.reason ?? cause;
      if (cause instanceof TransportError) throw cause;
      if (attempt >= retries) {
        const message = safeRead
          ? (timedOut ? "O servidor demorou para responder. Tente atualizar a consulta." : "Não foi possível conectar ao servidor. Verifique a conexão e tente atualizar a consulta.")
          : "Não foi possível confirmar a gravação com o servidor. Seus dados permanecem na tela. Consulte o registro antes de enviar novamente para evitar duplicidade.";
        throw new TransportError(message, timedOut ? "timeout" : "network");
      }
      continue;
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", abort);
    }
    if (attempt < retries && [502, 503, 504].includes(result.response.status)) {
      await new Promise<void>((resolve) => setTimeout(resolve, policy.retryDelayMs ?? 250));
      continue;
    }
    return result;
  }
}
