import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { FileDown, FilePlus2, FileText, Plus, RefreshCw, Save, Search, Trash2, X } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import { ApiError } from "../../../shared/api/apiError";
import { moneyInput } from "../../../shared/forms/moneyInput";
import { ActionButton } from "./ActionButton";
import { quoteNumber } from "./quoteSaveGuard";
import { quoteDiscountCents, quoteLineCents } from "./groupedQuoteMoney";
import { groupedQuoteContentMatches } from "./groupedQuoteSave";
import { GroupedQuoteCreateDialog } from "./GroupedQuoteCreateDialog";
import type { GroupedQuote, GroupedQuoteItem } from "../types";
import "./groupedQuotes.css";

const money = (value: unknown) => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const equipmentName = (row: GroupedQuote["work_orders"][number]) => [row.equipment_type, row.manufacturer, row.model].filter(Boolean).join(" · ") || "Equipamento";
const cloneQuote = (quote: GroupedQuote): GroupedQuote => ({ ...quote, items: quote.items.map(item => ({ ...item, quantity: String(item.quantity), unit_value: String(item.unit_value ?? "0") })) });

type PanelProps = { workOrderId?: number; companyCode?: string; onChanged?: () => Promise<void>; readOnly?: boolean };

export function GroupedQuotesPanel({ workOrderId, companyCode, onChanged, readOnly = false }: PanelProps) {
  const [quotes, setQuotes] = useState<GroupedQuote[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [newOrderIds, setNewOrderIds] = useState<number[] | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const params = new URLSearchParams({ limit: "200" });
    if (workOrderId) params.set("work_order_id", String(workOrderId));
    if (companyCode && companyCode !== "all") params.set("company_code", companyCode);
    if (search.trim()) params.set("search", search.trim());
    const timer = window.setTimeout(() => {
      void apiClient.get<GroupedQuote[]>(`/laboratory/grouped-quotes?${params}`).then(rows => { if (active) setQuotes(rows); })
        .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Não foi possível consultar os orçamentos conjuntos."); })
        .finally(() => { if (active) setLoading(false); });
    }, search ? 250 : 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [workOrderId, companyCode, search, reload]);
  const groups = [...new Map([...quotes].sort((a, b) => a.revision - b.revision).map(quote => [quote.group_id, quote])).values()].sort((a, b) => b.id - a.id);
  return <section className="grouped-quotes-panel">
    <header><div><small>PROPOSTAS COM VÁRIAS OS</small><h2>Orçamentos conjuntos</h2><p>{workOrderId ? "Documentos conjuntos que incluem esta OS." : "Crie um documento e adicione nele as OS do mesmo cliente e empresa."}</p></div><div className="grouped-quotes-actions">{!readOnly && <button type="button" onClick={() => setCreating(true)}><Plus size={16} /> Novo orçamento conjunto</button>}<button type="button" disabled={loading} onClick={() => setReload(value => value + 1)}><RefreshCw size={16} /> Atualizar</button></div></header>
    {!workOrderId && <label className="grouped-quotes-search"><Search size={17} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Buscar código, cliente ou OS..." aria-label="Pesquisar orçamentos conjuntos" /></label>}
    {error && <p role="alert" className="grouped-quote-error">{error}</p>}
    {loading && <p role="status">Consultando orçamentos conjuntos…</p>}
    <div className="grouped-quotes-list">{groups.map(quote => <button type="button" key={quote.group_id} onClick={() => setSelected(quote.id)}>
      <FileText size={22} /><span><strong>{quote.code} · {quote.customer_name}</strong><small>{quote.work_orders.map(row => row.number).join(" · ")}</small><small>Revisão {quote.revision} · {quote.status === "emitted" ? "Emitido" : "Rascunho"}</small></span><b>{money(quote.total)}</b>
    </button>)}</div>
    {!loading && !error && !groups.length && <p className="grouped-quotes-empty">Nenhum orçamento conjunto encontrado.</p>}
    {quotes.length >= 200 && <small>Mostrando até 200 revisões. Use a pesquisa para localizar um documento específico.</small>}
    {selected != null && <GroupedQuoteDialog quoteId={selected} readOnly={readOnly} onClose={() => { setSelected(null); setReload(value => value + 1); }} onChanged={async () => { setReload(value => value + 1); await onChanged?.(); }} />}
    {creating && <GroupedQuoteCreateDialog companyCode={companyCode} workOrderId={workOrderId} onClose={() => setCreating(false)} onCreate={ids => { setCreating(false); setNewOrderIds(ids); }} />}
    {newOrderIds && <GroupedQuoteDialog workOrderIds={newOrderIds} onClose={() => { setNewOrderIds(null); setReload(value => value + 1); }} onChanged={async () => { setReload(value => value + 1); await onChanged?.(); }} />}
  </section>;
}

type EditorProps = { quoteId?: number; workOrderIds?: number[]; onClose: () => void; onChanged?: () => Promise<void>; readOnly?: boolean };
type Busy = "load" | "save" | "preview" | "emit" | "delete" | null;

export function GroupedQuoteDialog({ quoteId, workOrderIds, onClose, onChanged, readOnly = false }: EditorProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [form, setForm] = useState<GroupedQuote | null>(null);
  const [revisions, setRevisions] = useState<GroupedQuote[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<Busy>("load");
  const busyRef = useRef<Busy>("load");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const alive = useRef(true);
  const loadSequence = useRef(0);
  const knownId = useRef<number | undefined>(quoteId);
  const creationKey = useRef(crypto.randomUUID());
  const initialOrders = useRef(workOrderIds ?? []);
  const locked = readOnly || form?.status === "emitted" || Boolean(form?.emitted_at);
  function setWorking(value: Busy) { busyRef.current = value; setBusy(value); }
  const edit = (value: Partial<GroupedQuote>) => { setForm(current => current ? { ...current, ...value } : current); setDirty(true); setError(""); setNotice(""); };

  async function refreshHistory(groupId: number) {
    const rows = await apiClient.get<GroupedQuote[]>(`/laboratory/grouped-quotes?group_id=${groupId}&limit=200`);
    if (alive.current) setRevisions(rows);
  }
  async function load(id?: number) {
    const sequence = ++loadSequence.current;
    setWorking("load"); setError("");
    try {
      const target = id ?? knownId.current;
      const quote = target != null ? await apiClient.get<GroupedQuote>(`/laboratory/grouped-quotes/${target}`)
        : await apiClient.post<GroupedQuote>("/laboratory/grouped-quotes", { work_order_ids: initialOrders.current }, { headers: { "Idempotency-Key": creationKey.current } });
      if (!alive.current || sequence !== loadSequence.current) return;
      knownId.current = quote.id;
      setForm(cloneQuote(quote)); setDirty(false);
      await refreshHistory(quote.group_id).catch(() => { if (alive.current) setNotice("Documento carregado. Atualize o histórico se precisar consultar outras revisões."); });
    } catch (cause) { if (alive.current && sequence === loadSequence.current) setError(cause instanceof Error ? cause.message : "Não foi possível abrir o orçamento conjunto."); }
    finally { if (alive.current && sequence === loadSequence.current) setWorking(null); }
  }
  useEffect(() => {
    alive.current = true;
    dialog.current?.showModal();
    void load();
    return () => { alive.current = false; loadSequence.current++; };
  }, []);

  function requestClose() {
    if (busyRef.current) return;
    if (dirty && !window.confirm("Descartar as alterações ainda não salvas deste orçamento conjunto?")) return;
    onClose();
  }
  async function persisted(): Promise<GroupedQuote> {
    if (!form) throw new Error("O orçamento ainda não foi carregado.");
    if (locked || !dirty) return form;
    const items = form.items.map(item => ({ work_order_id: item.work_order_id, description: item.description.trim(), quantity: quoteNumber(item.quantity), unit_value: moneyInput(item.unit_value ?? "0") }));
    if (!items.length || items.some(item => !item.description || !Number.isFinite(item.quantity) || item.quantity <= 0 || !Number.isFinite(item.unit_value) || item.unit_value < 0)) throw new Error("Confira a descrição, quantidade e valor dos itens de cada OS.");
    if (items.some(item => Math.abs(item.quantity * 1000 - Math.round(item.quantity * 1000)) > .000001 || Math.abs(item.unit_value * 100 - Math.round(item.unit_value * 100)) > .000001)) throw new Error("Quantidade aceita até três casas decimais e valores até duas casas decimais.");
    if (form.work_order_ids.some(id => !items.some(item => item.work_order_id === id))) throw new Error("Cada OS precisa ter pelo menos um item no orçamento.");
    const discountValue = moneyInput(form.discount_value ?? "0");
    if (!Number.isFinite(discountValue) || discountValue < 0 || Math.abs(discountValue * 100 - Math.round(discountValue * 100)) > .000001 || (form.discount_type === "percent" && discountValue > 100)) throw new Error("Confira o desconto do orçamento; use até duas casas decimais.");
    const subtotalCents = items.reduce((sum, item) => sum + quoteLineCents(item.quantity, item.unit_value), 0);
    if (quoteDiscountCents(subtotalCents, form.discount_type, discountValue) > subtotalCents) throw new Error("O desconto não pode exceder o subtotal do orçamento.");
    const payload = {
      version: form.version, work_order_ids: form.work_order_ids, title: form.title,
      service_code: form.service_code, technical_report: form.technical_report, services_description: form.services_description,
      delivery_days: form.delivery_days, billing_days: form.billing_days, billing_terms: form.billing_terms,
      warranty_months: form.warranty_months, warranty_terms: form.warranty_terms, payment_terms: form.payment_terms,
      validity_days: form.validity_days, return_condition: form.return_condition, consumer_clause: form.consumer_clause,
      supply_clause: form.supply_clause, estimate_clause: form.estimate_clause, discount_type: form.discount_type,
      discount_value: discountValue, items,
    };
    let quote: GroupedQuote;
    try {
      quote = await apiClient.put<GroupedQuote>(`/laboratory/grouped-quotes/${form.id}`, payload);
    } catch (cause) {
      if (!(cause instanceof ApiError) || (cause.status !== 0 && cause.status !== 409 && cause.status < 500)) throw cause;
      // A lost acknowledgement may follow a committed PUT. Read and compare;
      // never replay a write or replace a different draft automatically.
      let current: GroupedQuote;
      try { current = await apiClient.get<GroupedQuote>(`/laboratory/grouped-quotes/${form.id}`); }
      catch { throw cause; }
      if (current.id !== form.id || !groupedQuoteContentMatches(payload, current)) throw cause;
      quote = current;
    }
    setForm(cloneQuote(quote)); setDirty(false); knownId.current = quote.id;
    void onChanged?.().catch(() => undefined);
    void refreshHistory(quote.group_id).catch(() => undefined);
    return quote;
  }
  async function save() {
    if (busyRef.current) return;
    setWorking("save"); setError(""); setNotice("");
    try { const quote = await persisted(); setNotice(`${quote.code} · revisão ${quote.revision} salva. Total ${money(quote.total)}.`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível salvar. Os dados digitados foram preservados."); }
    finally { setWorking(null); }
  }
  async function pdf(preview: boolean) {
    if (busyRef.current || !form) return;
    const tab = preview ? window.open("", "_blank") : null;
    if (tab) { tab.document.title = "Preparando orçamento conjunto"; tab.document.body.textContent = "Preparando PDF…"; }
    setWorking(preview ? "preview" : "emit"); setError(""); setNotice("");
    const controller = new AbortController(); const timeout = window.setTimeout(() => controller.abort(), 120000);
    try {
      const quote = await persisted();
      const emitted = quote.status === "emitted" || Boolean(quote.emitted_at);
      const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "/api";
      const response = await fetch(`${base}/laboratory/grouped-quotes/${quote.id}/${preview || emitted ? `pdf?preview=${preview ? "true" : "false"}` : "emit"}`, {
        method: preview || emitted ? "GET" : "POST", credentials: "include", cache: "no-store", signal: controller.signal,
        headers: { Accept: "application/pdf", ...(preview || emitted ? {} : { "Content-Type": "application/json" }) },
        ...(preview || emitted ? {} : { body: JSON.stringify({ version: quote.version }) }),
      });
      if (!response.ok) {
        if (response.status === 401) window.dispatchEvent(new Event("nexus:session-expired"));
        const data = await response.json().catch(() => null) as { detail?: unknown } | null;
        throw new Error(typeof data?.detail === "string" ? data.detail : "Não foi possível gerar o PDF. Reabra a revisão para conferir seu estado antes de tentar novamente.");
      }
      const blob = await response.blob();
      if (!blob.type.includes("pdf") || blob.size < 100) throw new Error("A resposta não contém um PDF válido.");
      const url = URL.createObjectURL(blob);
      if (preview && tab && !tab.closed) tab.location.replace(url);
      else { const link = document.createElement("a"); link.href = url; link.download = `orcamento-${quote.code}-r${String(quote.revision).padStart(2, "0")}.pdf`; document.body.append(link); link.click(); link.remove(); }
      window.setTimeout(() => URL.revokeObjectURL(url), 120000);
      if (!preview && !emitted) {
        // Preserve an acknowledged emission even if the follow-up read fails.
        setForm(current => current ? { ...current, status: "emitted", emitted_at: current.emitted_at || new Date().toISOString() } : current);
        void onChanged?.().catch(() => undefined);
        try { const updated = await apiClient.get<GroupedQuote>(`/laboratory/grouped-quotes/${quote.id}`); setForm(cloneQuote(updated)); await refreshHistory(updated.group_id); }
        catch { setNotice("PDF emitido. Atualize a revisão para conferir o histórico; o documento está protegido contra edição."); return; }
      }
      setNotice(preview ? "Prévia gerada com os dados salvos." : "PDF conjunto emitido e pronto para download.");
    } catch (cause) { tab?.close(); setError(cause instanceof Error ? cause.message : "Falha ao gerar o documento. O rascunho foi preservado."); }
    finally { window.clearTimeout(timeout); setWorking(null); }
  }
  async function newRevision() {
    if (!form || busyRef.current) return;
    setWorking("save"); setError("");
    try { const quote = await apiClient.post<GroupedQuote>(`/laboratory/grouped-quotes/${form.id}/revisions`); setForm(cloneQuote(quote)); setDirty(false); knownId.current = quote.id; await refreshHistory(quote.group_id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível criar a revisão."); }
    finally { setWorking(null); }
  }
  async function remove() {
    if (!form || busyRef.current || locked || !window.confirm(`Excluir o rascunho ${form.code}, revisão ${form.revision}?`)) return;
    setWorking("delete"); setError("");
    try { await apiClient.delete(`/laboratory/grouped-quotes/${form.id}?version=${form.version}`); void onChanged?.().catch(() => undefined); onClose(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível excluir o rascunho."); }
    finally { setWorking(null); }
  }
  function updateItem(index: number, next: Partial<GroupedQuoteItem>) { if (form) edit({ items: form.items.map((item, i) => i === index ? { ...item, ...next } : item) }); }
  const lineCents = (item: GroupedQuoteItem) => quoteLineCents(quoteNumber(item.quantity), moneyInput(item.unit_value ?? "0"));
  const subtotalCents = form?.items.reduce((sum, item) => sum + lineCents(item), 0) ?? 0;
  const subtotal = subtotalCents / 100;
  const discount = form ? quoteDiscountCents(subtotalCents, form.discount_type, moneyInput(form.discount_value ?? "0")) / 100 : 0;
  const disabled = Boolean(busy) || locked;
  return createPortal(<dialog ref={dialog} className="grouped-quote-dialog" aria-labelledby={titleId} onCancel={event => { event.preventDefault(); requestClose(); }}>
    <header><div><small>ORÇAMENTO CONJUNTO</small><h2 id={titleId}>{form ? `${form.code} · ${form.customer_name}` : "Preparando orçamento conjunto"}</h2>{form && <p>{form.work_orders.length} OS · revisão {form.revision} · {form.status === "emitted" ? "Emitido" : "Rascunho"}</p>}</div><button type="button" disabled={Boolean(busy)} aria-label="Fechar orçamento conjunto" onClick={requestClose}><X size={22} /></button></header>
    <div className="grouped-quote-content">
      {error && <div className="grouped-quote-error" role="alert">{error}<button type="button" disabled={Boolean(busy)} onClick={() => { if (!dirty || window.confirm("Recarregar a revisão e descartar as alterações não salvas?")) void load(); }}>Recarregar orçamento</button></div>}
      {notice && <p className="grouped-quote-notice" role="status">{notice}</p>}
      {busy === "load" && <p role="status">Carregando o documento e suas OS…</p>}
      {form && <>
        <div className="grouped-quote-revisions"><label>Revisão<select value={form.id} disabled={Boolean(busy)} onChange={event => { if (!dirty || window.confirm("Descartar as alterações não salvas e abrir outra revisão?")) void load(Number(event.target.value)); }}><option value={form.id}>{form.code} · revisão {form.revision} · {form.status === "emitted" ? "Emitido" : "Rascunho"}</option>{revisions.filter(quote => quote.id !== form.id).map(quote => <option key={quote.id} value={quote.id}>{quote.code} · revisão {quote.revision} · {quote.status === "emitted" ? "Emitido" : "Rascunho"}</option>)}</select></label>{locked && !readOnly && <ActionButton type="button" variant="secondary" disabled={Boolean(busy)} icon={<FilePlus2 size={17} />} onClick={() => void newRevision()}>Nova revisão</ActionButton>}</div>
        {locked && <p className="grouped-quote-lock">{readOnly ? "Visualização do documento." : "Esta revisão foi emitida. Use Nova revisão para alterar a proposta."}</p>}
        <fieldset disabled={disabled} className="grouped-quote-fields">
          <label>Título do documento<input maxLength={200} value={form.title} onChange={event => edit({ title: event.target.value })} /></label>
          <section className="grouped-quote-section"><h3>OS e equipamentos incluídos</h3><p>O documento identifica cada equipamento e mostra os valores de cada OS.</p>
            {form.work_orders.map(order => <article className="grouped-quote-order" key={order.id}>
              <header><div><strong>{order.number}</strong><span>{equipmentName(order)}</span><small>Série: {order.equipment_serial || "Não informada"} · NF de entrada: {order.entry_invoice || "Não informada"}</small></div><b>{money(form.items.filter(item => item.work_order_id === order.id).reduce((sum, item) => sum + lineCents(item), 0) / 100)}</b></header>
              {order.reported_defect && <p><strong>Defeito informado:</strong> {order.reported_defect}</p>}
              {form.items.map((item, index) => item.work_order_id === order.id ? <div className="grouped-quote-item" key={index}>
                <label>Descrição — {order.number}<input value={item.description} onChange={event => updateItem(index, { description: event.target.value })} /></label>
                <label>Quantidade<input inputMode="decimal" value={item.quantity} onChange={event => updateItem(index, { quantity: event.target.value })} /></label>
                <label>Valor unitário (R$)<input inputMode="decimal" value={item.unit_value ?? "0"} onChange={event => updateItem(index, { unit_value: event.target.value })} /></label>
                <button type="button" disabled={disabled || form.items.filter(row => row.work_order_id === order.id).length <= 1} aria-label={`Remover item ${index + 1} de ${order.number}`} onClick={() => edit({ items: form.items.filter((_, i) => i !== index) })}><Trash2 size={17} /></button>
              </div> : null)}
              <button type="button" className="grouped-quote-add" onClick={() => edit({ items: [...form.items, { work_order_id: order.id, description: "", quantity: "1", unit_value: "0" }] })}><Plus size={16} /> Adicionar item — {order.number}</button>
              {!dirty && <small className="grouped-quote-order-total">Desconto: {money(order.discount_amount)} · Total da OS: <strong>{money(order.total)}</strong></small>}
            </article>)}
          </section>
          <section className="grouped-quote-section"><h3>Diagnóstico e serviço comuns</h3><label>Diagnóstico técnico / laudo<textarea rows={4} value={form.technical_report} onChange={event => edit({ technical_report: event.target.value })} /></label><label>Serviço a realizar<textarea rows={4} value={form.services_description ?? ""} onChange={event => edit({ services_description: event.target.value })} /></label></section>
          <div className="grouped-quote-grid"><label>Desconto<select value={form.discount_type} onChange={event => edit({ discount_type: event.target.value as GroupedQuote["discount_type"] })}><option value="none">Sem desconto</option><option value="amount">Valor em R$</option><option value="percent">Percentual %</option></select></label><label>Valor do desconto<input disabled={disabled || form.discount_type === "none"} inputMode="decimal" value={form.discount_value ?? "0"} onChange={event => edit({ discount_value: event.target.value })} /></label></div>
          <div className="grouped-quote-total"><span>Subtotal: {money(subtotal)}</span><strong>Total do orçamento: {money(Math.max(0, subtotal - (Number.isFinite(discount) ? discount : 0)))}</strong><small>O desconto é distribuído entre as OS, sem duplicar o valor do documento.</small></div>
          <section className="grouped-quote-section"><h3>Condições comerciais comuns</h3><div className="grouped-quote-grid">
            <label>Código de serviço<input value={form.service_code} onChange={event => edit({ service_code: event.target.value })} /></label>
            <label>Prazo de execução (dias)<input type="number" min="0" value={form.delivery_days} onChange={event => edit({ delivery_days: Number(event.target.value) })} /></label>
            <label>Prazo para faturamento<input value={form.billing_terms ?? ""} onChange={event => edit({ billing_terms: event.target.value })} /></label>
            <label>Garantia<input value={form.warranty_terms ?? ""} onChange={event => edit({ warranty_terms: event.target.value })} /></label>
            <label>Validade (dias)<input type="number" min="1" value={form.validity_days} onChange={event => edit({ validity_days: Number(event.target.value) })} /></label>
            <label>Pagamento<input value={form.payment_terms} onChange={event => edit({ payment_terms: event.target.value })} /></label>
          </div><label>Condição de devolução<textarea rows={2} value={form.return_condition} onChange={event => edit({ return_condition: event.target.value })} /></label></section>
          <details className="grouped-quote-clauses"><summary>Cláusulas da proposta</summary><label>Artigo / garantia legal<textarea rows={3} value={form.consumer_clause} onChange={event => edit({ consumer_clause: event.target.value })} /></label><label>Cláusula de prazo, insumos e fornecedores<textarea rows={4} value={form.supply_clause} onChange={event => edit({ supply_clause: event.target.value })} /></label><label>Cláusula de orçamento prévio e estimativo<textarea rows={4} value={form.estimate_clause} onChange={event => edit({ estimate_clause: event.target.value })} /></label></details>
        </fieldset>
        {dirty && <p className="grouped-quote-dirty" role="status">Há alterações ainda não salvas.</p>}
      </>}
    </div>
    <footer><button type="button" disabled={Boolean(busy)} onClick={requestClose}>Fechar</button>{form && <>{!locked && <button type="button" className="grouped-quote-delete" disabled={Boolean(busy)} onClick={() => void remove()}>Excluir rascunho</button>}<span />{!readOnly && <ActionButton type="button" variant="secondary" disabled={Boolean(busy)} onClick={() => void pdf(true)}>Visualizar PDF</ActionButton>}{!locked && <ActionButton type="button" loading={busy === "save"} disabled={Boolean(busy)} icon={<Save size={16} />} onClick={() => void save()}>Salvar rascunho</ActionButton>}<ActionButton type="button" loading={busy === "emit"} disabled={Boolean(busy) || (readOnly && form.status !== "emitted")} icon={<FileDown size={16} />} onClick={() => void pdf(false)}>{form.status === "emitted" ? "Baixar PDF emitido" : "Salvar e emitir PDF"}</ActionButton></>}</footer>
  </dialog>, document.body);
}
