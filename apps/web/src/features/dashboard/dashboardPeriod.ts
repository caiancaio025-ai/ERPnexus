/** Período do painel, salvo apenas neste navegador por usuário. Não altera o banco. */
export const PERIOD_PRESETS = ["todos", "mes", "30d", "90d", "ano", "personalizado"] as const;
export type PeriodPreset = (typeof PERIOD_PRESETS)[number];
export type DashboardPeriodPreference = { preset: PeriodPreset; start: string; end: string };
export const DEFAULT_DASHBOARD_PERIOD: DashboardPeriodPreference = { preset: "todos", start: "", end: "" };

export const periodOptions: Array<{ value: PeriodPreset; label: string }> = [
  { value: "todos", label: "Todo o histórico" },
  { value: "mes", label: "Este mês" },
  { value: "30d", label: "Últimos 30 dias" },
  { value: "90d", label: "Últimos 90 dias" },
  { value: "ano", label: "Este ano" },
  { value: "personalizado", label: "Escolher datas" },
];

export function dashboardPeriodKey(userId: number): string {
  return `sentico.dashboard.periodo.v1.user.${userId}`;
}

function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day;
}

export function dashboardPeriodError(value: DashboardPeriodPreference): string | null {
  if (!PERIOD_PRESETS.includes(value.preset)) return "Selecione um período válido.";
  if (value.preset !== "personalizado") return null;
  if (!value.start && !value.end) return "Preencha ao menos uma data para filtrar.";
  if ((value.start && !validDate(value.start)) || (value.end && !validDate(value.end))) {
    return "Informe datas válidas no formato dia/mês/ano.";
  }
  if (value.start && value.end && value.start > value.end) {
    return "A data inicial não pode ser maior que a data final.";
  }
  return null;
}

export function parseDashboardPeriod(raw: string | null): DashboardPeriodPreference {
  if (!raw) return { ...DEFAULT_DASHBOARD_PERIOD };
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return { ...DEFAULT_DASHBOARD_PERIOD };
    const entry = value as Record<string, unknown>;
    const parsed = {
      preset: entry.preset as PeriodPreset,
      start: typeof entry.start === "string" ? entry.start : "",
      end: typeof entry.end === "string" ? entry.end : "",
    };
    return dashboardPeriodError(parsed) ? { ...DEFAULT_DASHBOARD_PERIOD } : parsed;
  } catch { return { ...DEFAULT_DASHBOARD_PERIOD }; }
}

export function dashboardPeriodQuery(value: DashboardPeriodPreference): string {
  const query = new URLSearchParams({ periodo: value.preset });
  if (value.preset === "personalizado") {
    if (value.start) query.set("inicio", value.start);
    if (value.end) query.set("fim", value.end);
  }
  return `/api/dashboard/summary?${query}`;
}

export function dashboardPeriodLabel(value: DashboardPeriodPreference): string {
  if (value.preset !== "personalizado") {
    return periodOptions.find(({ value: preset }) => preset === value.preset)?.label ?? "Todo o histórico";
  }
  const format = (date: string) => date.split("-").reverse().join("/");
  if (value.start && value.end) return `${format(value.start)} a ${format(value.end)}`;
  if (value.start) return `Desde ${format(value.start)}`;
  return `Até ${format(value.end)}`;
}
