import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Plus, Search, X } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import type { WorkOrder, WorkOrderPage } from "../types";

export function GroupedQuoteCreateDialog({ companyCode, workOrderId, onClose, onCreate }: {
  companyCode?: string; workOrderId?: number; onClose: () => void; onCreate: (ids: number[]) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [selected, setSelected] = useState<WorkOrder[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [seedLoading, setSeedLoading] = useState(Boolean(workOrderId));
  const [error, setError] = useState("");
  const [seedError, setSeedError] = useState("");
  const [reload, setReload] = useState(0);
  const [total, setTotal] = useState(0);
  const first = selected[0];
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    if (!workOrderId) return;
    let active = true;
    setSeedLoading(true); setSeedError("");
    void apiClient.get<WorkOrder>(`/laboratory/work-orders/${workOrderId}`).then(order => {
      if (!active) return;
      if (order.is_inactive || order.status === "cancelled" || !order.customer_id) throw new Error("A OS precisa estar ativa e vinculada a um cadastro de cliente para entrar no orçamento conjunto.");
      setSelected(current => current.some(row => row.id === order.id) ? current : [order, ...current]);
    }).catch(cause => { if (active) setSeedError(cause instanceof Error ? cause.message : "Não foi possível carregar a OS."); })
      .finally(() => { if (active) setSeedLoading(false); });
    return () => { active = false; };
  }, [workOrderId, reload]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const params = new URLSearchParams({ page: "1", page_size: "50" });
    const company = first?.company_code || companyCode;
    if (company && company !== "all") params.set("company_code", company);
    const search = query.trim() || first?.customer_name;
    if (search) params.set("search", search);
    const timer = window.setTimeout(() => {
      void apiClient.get<WorkOrderPage>(`/laboratory/work-orders?${params}`).then(data => {
        if (active) { setOrders(data.items); setTotal(data.total); }
      }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Não foi possível consultar as OS."); })
        .finally(() => { if (active) setLoading(false); });
    }, query ? 250 : 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [companyCode, first?.company_code, first?.customer_id, first?.customer_name, query, reload]);
  function reason(order: WorkOrder): string | null {
    if (selected.some(row => row.id === order.id)) return "Já incluída";
    if (order.is_inactive || order.status === "cancelled") return "OS inativa ou cancelada";
    if (!order.customer_id) return "Vincule a OS a um cadastro de cliente";
    if (first && (order.company_code !== first.company_code || order.customer_id !== first.customer_id)) return "Escolha OS do mesmo cliente e empresa";
    if (selected.length >= 50) return "Limite de 50 OS atingido";
    return null;
  }
  return createPortal(<dialog ref={dialog} className="grouped-quote-dialog grouped-quote-create" aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose(); }}>
    <header><div><small>ORÇAMENTO CONJUNTO</small><h2 id={titleId}>Adicionar OS ao orçamento</h2><p>Busque e adicione os equipamentos que devem aparecer no mesmo documento.</p></div><button type="button" aria-label="Fechar seleção do orçamento" onClick={onClose}><X size={22} /></button></header>
    <div className="grouped-quote-content">
      {first && <div className="grouped-quote-selection"><strong>{first.customer_name} · {selected.length} OS</strong><div>{selected.map(order => <button type="button" key={order.id} onClick={() => setSelected(current => current.filter(row => row.id !== order.id))} aria-label={`Remover ${order.number} do orçamento`}>{order.number}<X size={15} /></button>)}</div></div>}
      <label className="grouped-quote-create-search"><span><Search size={16} /> Buscar OS, cliente ou série</span><input autoFocus value={query} disabled={seedLoading} onChange={event => setQuery(event.target.value)} placeholder="Digite o número da OS ou identifique o equipamento" /></label>
      {(error || seedError) && <div role="alert" className="grouped-quote-error">{seedError || error}<button type="button" onClick={() => setReload(current => current + 1)}>Tentar novamente</button></div>}
      {(loading || seedLoading) && <p role="status">Consultando ordens de serviço…</p>}
      <div className="grouped-quote-candidates">{!seedLoading && orders.map(order => { const blocked = reason(order); return <article key={order.id}>
        <div><strong>{order.number} · {order.customer_name}</strong><span>{[order.equipment_type, order.manufacturer, order.model].filter(Boolean).join(" · ") || "Equipamento"}</span><small>Série: {order.equipment_serial || "Não informada"}</small>{blocked && <small>{blocked}</small>}</div>
        <button type="button" disabled={Boolean(blocked)} aria-label={`Adicionar ${order.number} ao orçamento`} onClick={() => { if (!reason(order)) { setSelected(current => [...current, order]); setQuery(""); } }}><Plus size={16} /> Adicionar</button>
      </article>; })}</div>
      {!loading && !seedLoading && !error && !orders.length && <p>Nenhuma OS encontrada. Tente o número da OS, o cliente ou a série.</p>}
      {total > 50 && <p>Mostrando até 50 resultados. Refine a busca para encontrar a OS desejada.</p>}
    </div>
    <footer><button type="button" onClick={onClose}>Cancelar</button><span /><button type="button" disabled={seedLoading || Boolean(seedError) || selected.length < 2} onClick={() => onCreate(selected.map(order => order.id))}>Criar orçamento com {selected.length} OS</button></footer>
  </dialog>, document.body);
}
