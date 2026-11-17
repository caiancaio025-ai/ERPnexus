/* SÊNTICO Web Push service worker · sem cache de dados ou sessões do ERP. */
self.addEventListener("push", (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch { /* corpo inválido */ }
  // Notificações podem aparecer na tela bloqueada (Windows/iOS/Android).
  // Evitar nomes de clientes, dados de OS, valores e outros dados sensíveis.
  const title = "SÊNTICO ERP · Nova atualização";
  const url = typeof payload.url === "string" && payload.url.startsWith("/") && !payload.url.startsWith("//") && !payload.url.includes("\\")
    ? payload.url : "/painel?notificacoes=1";
  event.waitUntil(self.registration.showNotification(title, {
    body: "Abra o SÊNTICO para conferir os detalhes da notificação.",
    icon: "/sentico-icon-192.png",
    badge: "/sentico-icon-192.png",
    tag: typeof payload.tag === "string" ? payload.tag : "sentico",
    data: { url },
  }));
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const route = event.notification.data?.url || "/painel?notificacoes=1";
  const url = new URL(route, self.location.origin).href;
  event.waitUntil((async () => {
    const windows = await clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.navigate(url);
      return existing.focus();
    }
    return clients.openWindow(url);
  })());
});
