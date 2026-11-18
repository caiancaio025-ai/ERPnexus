import { useEffect, useState } from "react";
import { BellRing, BellOff, Monitor, Smartphone } from "lucide-react";
import { apiClient } from "../api/apiClient";
import "./push-notifications.css";
import { deviceName, revokeDevicePush, isDesktopDevice } from "../notifications/pushClient";

type PushConfig = { enabled: boolean; public_key: string };
type SubscriptionDto = { endpoint: string; keys: { p256dh: string; auth: string }; device_label: string };

function supported(): boolean {
  return window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function decodePublicKey(encoded: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - encoded.length % 4) % 4);
  const bytes = atob((encoded + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const result = new Uint8Array(new ArrayBuffer(bytes.length));
  for (let i = 0; i < bytes.length; i++) result[i] = bytes.charCodeAt(i);
  return result;
}

export function PushNotificationsToggle() {
  const [config, setConfig] = useState<PushConfig | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const isIphone = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  const desktop = isDesktopDevice();
  const device = desktop ? "computador" : "celular";

  useEffect(() => {
    let active = true;
    apiClient.get<PushConfig>("/notifications/push/config").then(async (result) => {
      if (!active) return;
      setConfig(result);
      if (supported()) {
        const subscription = await navigator.serviceWorker.getRegistration("/")
          .then((registration) => registration?.pushManager.getSubscription());
        if (active) setEnabled(Boolean(subscription));
      }
    }).catch(() => { if (active) setMessage("Não foi possível consultar a configuração de avisos."); });
    return () => { active = false; };
  }, []);

  async function activate() {
    if (!config?.enabled || !supported()) return;
    setWorking(true); setMessage("");
    try {
      // O pedido de permissão precisa ocorrer imediatamente após o toque.
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setMessage("Permissão não concedida. Libere notificações nas configurações do navegador.");
        return;
      }
      const registration = await navigator.serviceWorker.register("/sentico-sw.js", { scope: "/" });
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: decodePublicKey(config.public_key),
      });
      const data = subscription.toJSON();
      if (!data.endpoint || !data.keys?.p256dh || !data.keys.auth) throw new Error("Inscrição incompleta no navegador.");
      await apiClient.post("/notifications/push/subscriptions", {
        endpoint: data.endpoint, keys: { p256dh: data.keys.p256dh, auth: data.keys.auth },
        device_label: deviceName(),
      } satisfies SubscriptionDto);
      setEnabled(true);
      setMessage(`Notificações deste ${device} ativadas.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível ativar os avisos.");
    } finally { setWorking(false); }
  }

  async function deactivate() {
    setWorking(true); setMessage("");
    try {
      await revokeDevicePush();
      setEnabled(false);
      setMessage(`Notificações deste ${device} desativadas.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível desativar os avisos.");
    } finally { setWorking(false); }
  }

  return <section className="push-setup" aria-label="Avisos no dispositivo">
    <div className="push-setup__heading">{desktop ? <Monitor size={17}/> : <Smartphone size={17}/>}<strong>Notificações neste {device}</strong></div>
    {config?.enabled && supported() && !(isIphone && !standalone)
      ? <button type="button" disabled={working} onClick={() => void (enabled ? deactivate() : activate())}>
          {enabled ? <BellOff size={16}/> : <BellRing size={16}/>}
          {working ? "Configurando..." : enabled ? `Desativar neste ${device}` : `Ativar notificações neste ${device}`}
        </button>
      : <small>{isIphone && !standalone ? "No iPhone, primeiro use Compartilhar → Adicionar à Tela de Início e abra o aplicativo instalado." : !supported() ? "Abra pelo HTTPS usando Edge, Chrome ou outro navegador com suporte a Web Push. Aplicativos WebView2 podem exigir integração nativa." : config && !config.enabled ? "O administrador precisa configurar as chaves Web Push no servidor." : "Verificando disponibilidade..."}</small>
    }
    {message && <p role="status">{message}</p>}
  </section>;
}
