import { Plus, Printer, Save, Send, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import { apiClient } from "../../shared/api/apiClient";
import type { CommercialCompany, CommercialEquipment, CommercialQuote, CommercialQuoteItem, CompanyCode, CustomerLite, QuoteType } from "./types";

type Props = {
  quoteType: QuoteType;
  companies: CommercialCompany[];
  customers: CustomerLite[];
  equipment: CommercialEquipment[];
  selected: CommercialQuote | null;
  onClose: () => void;
  onSaved: (quote: CommercialQuote) => void;
};

function blankItem(): CommercialQuoteItem {
  return { equipment_id: null, description: "", manufacturer: null, model: null, power: null, voltage: null, serial_number: null, quantity: 1, unit: "UN", unit_price: 0, discount_pct: 0, rental_period_count: null, rental_period_unit: null };
}

function localDate(days = 0) {
  const date = new Date(); date.setDate(date.getDate() + days); return date.toISOString().slice(0, 10);
}

export function CommercialQuoteEditor({ quoteType, companies, customers, equipment, selected, onClose, onSaved }: Props) {
  const [companyCode, setCompanyCode] = useState<CompanyCode>(selected?.company_code ?? companies[0]?.company_code ?? "universo_eletronica");
  const [customerId, setCustomerId] = useState(String(selected?.customer_id ?? ""));
  const [validUntil, setValidUntil] = useState(selected?.valid_until ?? localDate(15));
  const [title, setTitle] = useState(selected?.title ?? "");
  const [introText, setIntroText] = useState(selected?.intro_text ?? "");
  const [notes, setNotes] = useState(selected?.notes ?? "");
  const [paymentTerms, setPaymentTerms] = useState(selected?.payment_terms ?? "");
  const [deliveryTerms, setDeliveryTerms] = useState(selected?.delivery_terms ?? "");
  const [warrantyTerms, setWarrantyTerms] = useState(selected?.warranty_terms ?? "");
  const [rentalTerms, setRentalTerms] = useState(selected?.rental_terms ?? "");
  const [preventiveScope, setPreventiveScope] = useState(selected?.preventive_scope ?? "");
  const [exclusions, setExclusions] = useState(selected?.exclusions ?? "");
  const [items, setItems] = useState<CommercialQuoteItem[]>(selected?.items?.length ? selected.items.map((item) => ({ ...item, unit_price: item.unit_price ?? 0 })) : [blankItem()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const locked = Boolean(selected && selected.status !== "draft");

  const total = useMemo(() => items.reduce((sum, item) => sum + item.quantity * (item.unit_price ?? 0) * (1 - item.discount_pct / 100), 0), [items]);

  function updateItem(index: number, patch: Partial<CommercialQuoteItem>) {
    setItems((current) => current.map((item, pos) => pos === index ? { ...item, ...patch } : item));
  }

  function selectEquipment(index: number, id: string) {
    const item = equipment.find((row) => row.id === Number(id));
    if (!item) { updateItem(index, { equipment_id: null }); return; }
    updateItem(index, {
      equipment_id: item.id, description: item.equipment_type, manufacturer: item.manufacturer, model: item.model,
      power: item.power, voltage: item.voltage,
      unit_price: quoteType === "sale" ? (item.sale_price ?? 0) : quoteType === "rental" ? (item.rental_monthly_price ?? item.rental_daily_price ?? 0) : 0,
    });
  }

  function payload() {
    return {
      quote_type: quoteType, company_code: companyCode, customer_id: Number(customerId), valid_until: validUntil || null, title: title || null,
      intro_text: introText || null, notes: notes || null, payment_terms: paymentTerms || null, delivery_terms: deliveryTerms || null,
      warranty_terms: warrantyTerms || null, rental_terms: rentalTerms || null, preventive_scope: preventiveScope || null, exclusions: exclusions || null,
      items: items.map(({ id, line_total, sort_order, ...item }) => item),
    };
  }

  async function save() {
    if (!customerId || items.some((item) => !item.description.trim())) { setError("Selecione o cliente e preencha a descrição de todos os itens."); return; }
    setSaving(true); setError("");
    try {
      const quote = selected
        ? await apiClient.put<CommercialQuote>(`/commercial/quotes/${selected.id}`, payload())
        : await apiClient.post<CommercialQuote>("/commercial/quotes", payload());
      onSaved(quote);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível salvar o orçamento."); }
    finally { setSaving(false); }
  }

  async function issue() {
    if (!selected) return;
    setSaving(true); setError("");
    try { onSaved(await apiClient.post<CommercialQuote>(`/commercial/quotes/${selected.id}/issue`, {})); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível emitir o orçamento."); }
    finally { setSaving(false); }
  }

  return <div className="com-modal" role="dialog" aria-modal="true">
    <section className="com-editor">
      <header className="com-editor-head">
        <div><span>{quoteType === "sale" ? "VENDA" : quoteType === "rental" ? "LOCAÇÃO" : "PREVENTIVA"}</span><h2>{selected?.quote_number ?? "Novo orçamento"}</h2><p>{locked ? `Emitido · R${String(selected?.revision ?? 1).padStart(2,"0")}` : "Rascunho editável"}</p></div>
        <button className="com-icon-btn" onClick={onClose}><X size={20}/></button>
      </header>
      {error && <div className="com-notice danger">{error}</div>}
      <div className="com-editor-body">
        <section className="com-editor-section"><h3>Cliente e proposta</h3><div className="com-form-grid three">
          <label>Empresa emitente<select disabled={locked} value={companyCode} onChange={(e)=>setCompanyCode(e.target.value as CompanyCode)}>{companies.map((c)=><option key={c.id} value={c.company_code}>{c.trade_name || c.legal_name}</option>)}</select></label>
          <label>Cliente<select disabled={locked} value={customerId} onChange={(e)=>setCustomerId(e.target.value)}><option value="">Selecione...</option>{customers.map((c)=><option key={c.id} value={c.id}>{c.trade_name || c.legal_name}</option>)}</select></label>
          <label>Validade<input disabled={locked} type="date" value={validUntil} onChange={(e)=>setValidUntil(e.target.value)}/></label>
        </div><label>Título<input disabled={locked} value={title} onChange={(e)=>setTitle(e.target.value)} placeholder="Ex.: Venda de inversor CFW11 / Locação mensal / Preventiva anual"/></label><label>Apresentação<textarea disabled={locked} rows={3} value={introText} onChange={(e)=>setIntroText(e.target.value)} placeholder="Texto introdutório da proposta..."/></label></section>

        <section className="com-editor-section"><div className="com-section-title"><div><h3>{quoteType === "preventive" ? "Equipamentos da preventiva" : "Itens do orçamento"}</h3><p>Use a grade para incluir vários equipamentos ou produtos no mesmo orçamento.</p></div>{!locked && <button className="com-btn" onClick={()=>setItems([...items,blankItem()])}><Plus size={16}/> Adicionar item</button>}</div>
          <div className="com-items-wrap"><table className="com-items"><thead><tr><th>Estoque</th><th>Descrição / especificação</th><th>Qtd.</th><th>Un.</th>{quoteType === "rental" && <th>Período</th>}<th>Valor unit.</th><th>Total</th><th></th></tr></thead><tbody>{items.map((item,index)=><tr key={index}>
            <td><select disabled={locked} value={item.equipment_id ?? ""} onChange={(e)=>selectEquipment(index,e.target.value)}><option value="">Livre</option>{equipment.map((row)=><option key={row.id} value={row.id}>{row.serial_code} · {row.equipment_type}</option>)}</select></td>
            <td><input disabled={locked} value={item.description} onChange={(e)=>updateItem(index,{description:e.target.value})}/><small>{[item.manufacturer,item.model,item.power,item.voltage].filter(Boolean).join(" · ")}</small></td>
            <td><input disabled={locked} type="number" min="0.01" step="0.01" value={item.quantity} onChange={(e)=>updateItem(index,{quantity:Number(e.target.value)})}/></td>
            <td><input disabled={locked} value={item.unit} onChange={(e)=>updateItem(index,{unit:e.target.value})}/></td>
            {quoteType === "rental" && <td><div className="com-period"><input disabled={locked} type="number" min="1" value={item.rental_period_count ?? 1} onChange={(e)=>updateItem(index,{rental_period_count:Number(e.target.value)})}/><select disabled={locked} value={item.rental_period_unit ?? "month"} onChange={(e)=>updateItem(index,{rental_period_unit:e.target.value})}><option value="day">dia(s)</option><option value="week">semana(s)</option><option value="month">mês(es)</option></select></div></td>}
            <td><input disabled={locked} type="number" min="0" step="0.01" value={item.unit_price ?? 0} onChange={(e)=>updateItem(index,{unit_price:Number(e.target.value)})}/></td>
            <td className="com-money">{(item.quantity*(item.unit_price ?? 0)*(1-item.discount_pct/100)).toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}</td>
            <td>{!locked && items.length>1 && <button className="com-icon-btn danger" onClick={()=>setItems(items.filter((_,pos)=>pos!==index))}><Trash2 size={16}/></button>}</td>
          </tr>)}</tbody></table></div><div className="com-quote-total"><span>Total da proposta</span><strong>{total.toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}</strong></div>
        </section>

        {quoteType === "preventive" && <section className="com-editor-section"><h3>Escopo técnico da preventiva</h3><textarea disabled={locked} rows={5} value={preventiveScope} onChange={(e)=>setPreventiveScope(e.target.value)} placeholder="Inspeção, limpeza técnica, reaperto, medições, ventilação, capacitores, testes funcionais..."/></section>}
        {quoteType === "rental" && <section className="com-editor-section"><h3>Condições específicas de locação</h3><textarea disabled={locked} rows={4} value={rentalTerms} onChange={(e)=>setRentalTerms(e.target.value)} placeholder="Período mínimo, entrega/retirada, manutenção, avarias, horas de uso, caução..."/></section>}
        <section className="com-editor-section"><h3>Condições comerciais</h3><div className="com-form-grid two"><label>Pagamento<textarea disabled={locked} rows={3} value={paymentTerms} onChange={(e)=>setPaymentTerms(e.target.value)}/></label><label>Entrega / execução<textarea disabled={locked} rows={3} value={deliveryTerms} onChange={(e)=>setDeliveryTerms(e.target.value)}/></label><label>Garantia<textarea disabled={locked} rows={3} value={warrantyTerms} onChange={(e)=>setWarrantyTerms(e.target.value)}/></label><label>Exclusões<textarea disabled={locked} rows={3} value={exclusions} onChange={(e)=>setExclusions(e.target.value)}/></label></div><label>Observações<textarea disabled={locked} rows={4} value={notes} onChange={(e)=>setNotes(e.target.value)}/></label></section>
      </div>
      <footer className="com-editor-footer">
        {selected && <button className="com-btn" onClick={()=>window.open(`/api/commercial/quotes/${selected.id}/pdf`,"_blank","noopener,noreferrer")}><Printer size={16}/> Visualizar PDF</button>}
        <div className="com-spacer"/>{!locked && <button disabled={saving} className="com-btn primary" onClick={()=>void save()}><Save size={16}/> {saving?"Salvando...":"Salvar rascunho"}</button>}{selected && !locked && <button disabled={saving} className="com-btn success" onClick={()=>void issue()}><Send size={16}/> Emitir orçamento</button>}
      </footer>
    </section>
  </div>;
}
