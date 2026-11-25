export type ApiRequestOptions = RequestInit & {
  redirectOnUnauthorized?: boolean;
  timeoutMs?: number;
};
