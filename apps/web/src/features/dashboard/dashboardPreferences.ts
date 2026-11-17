import type { DashboardSummary } from "./types";

/** A preferência é apenas visual. A API continua definindo quais setores o usuário pode acessar. */
export const DASHBOARD_AREAS = [
  "laboratorio", "orcamentos", "compras", "financeiro", "estoque", "notificacoes", "atalhos", "geral",
] as const;

export type DashboardArea = (typeof DASHBOARD_AREAS)[number];

export const dashboardAreaLabels: Record<DashboardArea, { title: string; description: string }> = {
  laboratorio: { title: "Laboratório", description: "Entradas, serviços aprovados e equipamentos do mês" },
  orcamentos: { title: "Orçamentos", description: "OS analisadas que aguardam orçamento" },
  compras: { title: "Compras", description: "Solicitações, pedidos atrasados e entregas previstas" },
  financeiro: { title: "Financeiro", description: "Pendências, vencimentos e faturamentos" },
  estoque: { title: "Estoque", description: "Materiais a receber e separar para o laboratório" },
  notificacoes: { title: "Notificações", description: "Últimas atividades registradas no sistema" },
  atalhos: { title: "Ações rápidas", description: "Acesso às operações mais frequentes" },
  geral: { title: "Outros indicadores", description: "Indicadores gerais disponíveis para seu perfil" },
};

const alertAreaByKey: Record<string, DashboardArea> = {
  unread_notifications: "notificacoes",
  delayed_purchases: "compras", purchases_due_soon: "compras", requests_buy: "compras",
  delayed_invoices: "financeiro", finance_overdue: "financeiro", pending_finance: "financeiro",
  active_work_orders: "laboratorio", lab_entries: "laboratorio", lab_approved: "laboratorio", monthly_equipment: "laboratorio",
  quotes_pending: "orcamentos",
};

export function alertDashboardArea(key: string): DashboardArea {
  return alertAreaByKey[key] ?? "geral";
}

/** Nunca cria opções de setores ausentes do resumo já autorizado pelo servidor. */
export function availableDashboardAreas(summary: DashboardSummary): DashboardArea[] {
  const available = new Set<DashboardArea>(["notificacoes"]);
  for (const queue of summary.work_queues) available.add(queue.section);
  for (const alert of summary.alerts) available.add(alertDashboardArea(alert.key));
  if (summary.audience === "gestao" || summary.audience === "compras") available.add("compras");
  if (summary.audience === "gestao" || summary.audience === "lab") available.add("laboratorio");
  if (summary.quick_actions.length > 0) available.add("atalhos");
  return DASHBOARD_AREAS.filter((area) => available.has(area));
}

export function dashboardPreferenceKey(userId: number): string {
  return `sentico.dashboard.areas.v1.user.${userId}`;
}

/** Entradas antigas ou inválidas são ignoradas; novas áreas começam visíveis por padrão. */
export function readHiddenDashboardAreas(raw: string | null): DashboardArea[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !('hidden' in parsed)) return [];
    const hidden = (parsed as { hidden?: unknown }).hidden;
    if (!Array.isArray(hidden)) return [];
    return DASHBOARD_AREAS.filter((area) => hidden.includes(area));
  } catch {
    return [];
  }
}

export function serializeHiddenDashboardAreas(hidden: readonly DashboardArea[]): string {
  return JSON.stringify({ version: 1, hidden: DASHBOARD_AREAS.filter((area) => hidden.includes(area)) });
}
