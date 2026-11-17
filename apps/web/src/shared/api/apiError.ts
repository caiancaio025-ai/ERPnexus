import { mensagemSistemaEmPortugues } from "../i18n/portugues";

export type ValidationIssue = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, status = 0, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }

  get isUnauthorized() {
    return this.status === 401;
  }

  get isForbidden() {
    return this.status === 403;
  }
}

function validationMessage(issues: ValidationIssue[]) {
  const messages = issues
    .map((issue) => issue.msg ? mensagemSistemaEmPortugues(issue.msg) : undefined)
    .filter((message): message is string => Boolean(message));
  return messages.length ? messages.join(" ") : null;
}

export function extractApiMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") return fallback;

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return mensagemSistemaEmPortugues(detail);
  if (Array.isArray(detail)) return validationMessage(detail as ValidationIssue[]) ?? fallback;

  const message = (payload as { message?: unknown }).message;
  return typeof message === "string" && message.trim() ? mensagemSistemaEmPortugues(message) : fallback;
}
