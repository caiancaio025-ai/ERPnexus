export type Alert = {
  key: string;
  label: string;
  value: number;
  detail: string;
  tone: "danger" | "warning" | "info";
  target: string;
};

export type PurchaseEvent = {
  id: number;
  code: string;
  supplier: string;
  message: string;
  due_label: string;
  status: "overdue" | "due_soon";
  target: string;
};

export type QuickAction = {
  key: "new_work_order" | "new_budget" | "unnoted_movement";
  label: string;
  description: string;
  target: string;
};

export type DashboardSummary = {
  schema_version: "3";
  audience: "gestao" | "admin" | "lab" | "compras" | "estoque" | "outros";
  work_queues: WorkQueue[];
  alerts: Alert[];
  purchase_events: PurchaseEvent[];
  quick_actions: QuickAction[];
  monthly_equipment_entries: {
    month_label: string;
    count: number;
  };
};

export type NotificationItem = {
  id: number;
  category: string;
  severity: "info" | "success" | "warning" | "danger" | string;
  title: string;
  message: string;
  target?: string | null;
  entity_type?: string | null;
  entity_id?: number | null;
  work_order_id?: number | null;
  amount?: number | null;
  activity_module?: string | null;
  action?: string | null;
  actor_user_id?: number | null;
  actor_name?: string | null;
  work_order_number?: string | null;
  equipment_name?: string | null;
  details?: string | null;
  is_read: boolean;
  created_at: string;
};

export type NotificationSummary = {
  unread_count: number;
  items: NotificationItem[];
};

export type WorkItem = {
  id: number;
  title: string;
  description: string;
  meta: string | null;
  status: string;
  target: string;
  date_label: string | null;
};

export type WorkQueue = {
  key: string;
  section: "laboratorio" | "orcamentos" | "compras" | "financeiro" | "estoque";
  title: string;
  description: string;
  tone: "info" | "warning" | "danger" | "success";
  total: number;
  target: string;
  items: WorkItem[];
};
