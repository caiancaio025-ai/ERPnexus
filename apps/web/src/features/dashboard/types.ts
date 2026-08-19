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
  schema_version: "2";
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
  is_read: boolean;
  created_at: string;
};

export type NotificationSummary = {
  unread_count: number;
  items: NotificationItem[];
};
