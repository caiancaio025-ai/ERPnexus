import { apiClient } from "../api/apiClient";

// Uma inscrição Web Push é particular do perfil do navegador + origem HTTPS.
export function isDesktopDevice(): boolean {
  return !/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

export function deviceName(): string {
  const device = isDesktopDevice() ? "Computador" : "Celular";
  const platform = /iPhone|iPad|iPod/i.test(navigator.userAgent) ? "iOS"
    : /Android/i.test(navigator.userAgent) ? "Android"
    : /Win/i.test(navigator.userAgent) ? "Windows"
    : /Mac/i.test(navigator.userAgent) ? "macOS" : "outro sistema";
  return `${device} · ${platform}`;
}

/** Encerra a inscrição APENAS deste perfil/dispositivo; nunca remove outras inscrições do usuário. */
export async function revokeDevicePush(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager?.getSubscription();
  if (!subscription) return;
  // Primeiro elimina a associação no banco; depois interrompe a inscrição no navegador.
  try {
    await apiClient.post("/notifications/push/unsubscribe", { endpoint: subscription.endpoint }, { redirectOnUnauthorized: false });
  } finally {
    // Mesmo offline, revogar a inscrição local impede que o computador continue recebendo alertas.
    await subscription.unsubscribe();
  }
}
