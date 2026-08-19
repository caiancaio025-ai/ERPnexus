import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, PackageCheck, Search, ShoppingCart, Truck, XCircle } from "lucide-react";
import { apiClient } from "../../shared/api/apiClient";
import type { MaterialRequest, MaterialRequestStatus } from "./types";

const labels: Record<MaterialRequestStatus, string> = {
  awaiting_approval: "Aguardando aprovação", approved: "Aprovado", rejected: "Reprovado",
  purchasing: "Em compra", purchased: "Comprado", in_transit: "Em trânsito",
  received: "Recebido", delivered_to_lab: "Entregue ao lab", cancelled: "Cancelado",
};
const money = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);

const nextActions: Partial<Record<MaterialRequestStatus, { status: MaterialRequestStatus; label: string }[]>> = {
  awaiting_approval: [{ status: "approved", label: "Aprovar" }, { status: "rejected", label: "Reprovar" }],
  approved: [{ status: "purchasing", label: "Iniciar compra" }],
  purchasing: [{ status: "purchased", label: "Marcar comprado" }],
  purchased: [{ status: "in_transit", label: "Em trânsito" }, { status: "received", label: "Recebido" }],
  in_transit: [{ status: "received", label: "Recebido" }],
  received: [{ status: "delivered_to_lab", label: "Entregar ao lab" }],
};

export function MaterialRequestsPanel() {
  const [items, setItems] = useState<MaterialRequest[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<MaterialRequestStatus | "all">("all");
  const [editing, setEditing] = useState<MaterialRequest | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (status !== "all") params.set("status", status);
    if (search.trim()) params.set("search", search.trim());
    try { setItems(await apiClient.get<MaterialRequest[]>(`/purchasing/material-requests?${params}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao carregar solicitações."); }
  }
  useEffect(() => { void load(); }, [status]);
  const stats = useMemo(() => ({
    approval: items.filter((i) => i.status === "awaiting_approval").length,
    buying: items.filter((i) => ["approved", "purchasing"].includes(i.status)).length,
    waiting: items.filter((i) => ["purchased", "in_transit"].includes(i.status)).length,
  }), [items]);

  return <>
    <section className="material-request-kpis">
      <article><CheckCircle2 /><span>Aguardando aprovação</span><strong>{stats.approval}</strong></article>
      <article><ShoppingCart /><span>Para comprar</span><strong>{stats.buying}</strong></article>
      <article><Truck /><span>Aguardando chegada</span><strong>{stats.waiting}</strong></article>
    </section>
    <section className="purchase-panel">
      <div className="panel-title orders-title"><div><small>LABORATÓRIO → COMPRAS</small><h2>Solicitações de material</h2></div><div className="order-filters"><label><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void load()} placeholder="OS, item, fornecedor..." /></label><select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}><option value="all">Todos os status</option>{Object.entries(labels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
      {error && <div className="purchase-alert error">{error}</div>}
      <div className="material-request-list">
        {items.map((item) => <article key={item.id} onClick={() => setEditing(item)}>
          <div><small>{item.code} · {item.work_order_number}</small><strong>{item.item_name} <em>× {item.quantity}</em></strong><span>{item.customer_name} · {item.equipment_serial || "Sem série"}</span></div>
          <div><span className={`material-request-status ${item.status}`}>{labels[item.status]}</span><small>{item.requester_name}</small></div>
        </article>)}
        {!items.length && <div className="empty-state">Nenhuma solicitação encontrada.</div>}
      </div>
    </section>
    {editing && <MaterialRequestEditor item={editing} onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await load(); }} />}
  </>;
}

function MaterialRequestEditor({ item, onClose, onSaved }: { item: MaterialRequest; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ supplier_name: item.supplier_name || "", purchase_reference: item.purchase_reference || "", purchase_link: item.purchase_link || "", tracking_code: item.tracking_code || "", unit_cost: item.unit_cost ? String(item.unit_cost) : "", expected_delivery_date: item.expected_delivery_date || "", note: "" });
  const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const parsedUnitCost = Number(form.unit_cost.replace(",", ".")) || 0;
  const totalCost = parsedUnitCost * item.quantity;
  async function update(nextStatus: MaterialRequestStatus) {
    setSaving(true); setError("");
    try {
      await apiClient.patch(`/purchasing/material-requests/${item.id}`, { status: nextStatus, supplier_name: form.supplier_name || null, purchase_reference: form.purchase_reference || null, purchase_link: form.purchase_link || null, tracking_code: form.tracking_code || null, unit_cost: form.unit_cost ? Number(form.unit_cost.replace(",", ".")) : null, expected_delivery_date: form.expected_delivery_date || null, note: form.note || null });
      await onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível atualizar."); }
    finally { setSaving(false); }
  }
  return <div className="material-request-modal"><section><header><div><small>{item.code}</small><h2>{item.item_name}</h2><span>{item.work_order_number} · {item.customer_name}</span></div><button onClick={onClose}><XCircle /></button></header>
    <div className="material-request-context"><span><strong>Equipamento</strong>{item.equipment_serial || "Sem série"}</span><span><strong>Quantidade</strong>{item.quantity}</span><span><strong>Status</strong>{labels[item.status]}</span><span><strong>Solicitante</strong>{item.requester_name}</span></div>
    {item.technical_note && <div className="material-note"><strong>Observação técnica</strong><p>{item.technical_note}</p></div>}
    {item.suggested_link && <a className="material-suggested-link" href={item.suggested_link} target="_blank" rel="noreferrer"><ExternalLink size={15} />Abrir link sugerido pelo técnico</a>}
    <div className="material-purchase-total"><span>Valor desta compra</span><strong>{money(totalCost)}</strong><small>{item.quantity} × {money(parsedUnitCost)}</small></div><div className="material-editor-grid"><label>Fornecedor<input value={form.supplier_name} onChange={(e) => setForm({ ...form, supplier_name: e.target.value })} /></label><label>Referência / pedido<input value={form.purchase_reference} onChange={(e) => setForm({ ...form, purchase_reference: e.target.value })} /></label><label>Valor unitário<input value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} placeholder="0,00" /></label><label>Previsão de chegada<input type="date" value={form.expected_delivery_date} onChange={(e) => setForm({ ...form, expected_delivery_date: e.target.value })} /></label><label className="wide">Link da compra<input value={form.purchase_link} onChange={(e) => setForm({ ...form, purchase_link: e.target.value })} /></label><label>Rastreio<input value={form.tracking_code} onChange={(e) => setForm({ ...form, tracking_code: e.target.value })} /></label><label className="wide">Observação da movimentação<textarea rows={3} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label></div>
    {error && <div className="purchase-alert error">{error}</div>}
    <footer>{nextActions[item.status]?.map((action) => <button key={action.status} disabled={saving} className={action.status === "rejected" ? "danger" : "primary-action"} onClick={() => void update(action.status)}>{action.status === "received" || action.status === "delivered_to_lab" ? <PackageCheck size={16} /> : action.status === "rejected" ? <XCircle size={16} /> : <CheckCircle2 size={16} />}{action.status === "purchased" && totalCost > 0 ? `${action.label} · ${money(totalCost)}` : action.label}</button>)}<button onClick={onClose}>Fechar</button></footer>
  </section></div>;
}
