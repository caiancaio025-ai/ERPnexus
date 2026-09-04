import { useEffect, useMemo, useState } from "react";
import { Calculator, Eye, FileDown, FilePlus2, Plus, Save, Trash2 } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import type { Quote, QuoteItem } from "../types";
import { ActionButton } from "./ActionButton";

const CONSUMER = "Art. 26 do Código de Defesa do Consumidor: Produtos e serviços duráveis têm prazo de 90 dias para reclamação de vícios ocultos, contados a partir da entrega.";
const SUPPLY = "O prazo de execução e entrega dos serviços poderá ser prorrogado quando impossibilitado ou prejudicado por atraso, indisponibilidade ou irregularidade no fornecimento de insumos ou intercorrências imputáveis a fornecedores terceiros, incluindo atraso na entrega de materiais ou componentes essenciais, suspensão de fornecimento, descontinuação de produtos, falhas logísticas, restrições de estoque e situações de caso fortuito ou força maior que afetem a cadeia de suprimentos (arts. 393 e 396 do Código Civil). A prorrogação nas hipóteses previstas não caracterizará inadimplemento, tampouco ensejará penalidades ou sanções contratuais.";
const ESTIMATE = "O orçamento apresentado antes do início dos serviços técnicos possui natureza prévia e estimativa, não definitiva. Durante manutenções e reparos podem ser identificados defeitos ocultos, novos vícios, necessidade de peças adicionais ou serviços complementares somente verificáveis no decorrer da execução. Havendo necessidade de revisão de valor, a contratada comunicará o cliente por orçamento complementar detalhado e aguardará aprovação por meio eletrônico idôneo. Em caso de recusa ou ausência de resposta, os serviços adicionais não serão executados, permanecendo devidos, proporcionalmente, os serviços já realizados, peças adquiridas e custos operacionais incorridos. A empresa manterá registros de orçamentos, comunicações, laudos técnicos e aprovações ou recusas.";

type Form = {
  service_code: string; technical_report: string; services_description: string;
  delivery_days: number; billing_days: number; billing_terms: string; warranty_months: number; warranty_terms: string; payment_terms: string;
  validity_days: number; return_condition: string; consumer_clause: string; supply_clause: string;
  estimate_clause: string; discount_type: "none" | "amount" | "percent"; discount_value: string;
  items: QuoteItem[];
};

type Props = {
  workOrderId: number; workOrderNumber: string; customerName: string; defect: string; quotedValue: string;
  equipmentType: string; manufacturer: string; model: string; serialNumber: string; power: string; voltage: string;
  readOnly?: boolean;
};

const empty = (defect: string, value: string): Form => ({
  service_code: "3312102 / 14.01", technical_report: defect, services_description: "",
  delivery_days: 20, billing_days: 21, billing_terms: "21 dias", warranty_months: 3, warranty_terms: "3 meses",
  payment_terms: "TRANSFERÊNCIA, BOLETO E PIX.", validity_days: 0,
  return_condition: "ORÇAMENTO NÃO APROVADO EM 30 DIAS: O EQUIPAMENTO SERÁ DEVOLVIDO.",
  consumer_clause: CONSUMER, supply_clause: SUPPLY, estimate_clause: ESTIMATE,
  discount_type: "none", discount_value: "0",
  items: [{ description: "SERVIÇO DE MANUTENÇÃO E REPARO", quantity: "1", unit_value: value || "0" }],
});

export function QuoteEditor(props: Props) {
  const { workOrderId, workOrderNumber, customerName, defect, quotedValue, equipmentType, manufacturer, model, serialNumber, power, voltage, readOnly = false } = props;
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [form, setForm] = useState<Form>(() => empty(defect, quotedValue));
  const [busy, setBusy] = useState<"save" | "delete" | null>(null);
  const [saved, setSaved] = useState(false);
  const selectedQuote = quotes.find((quote) => quote.id === selected) ?? null;
  const locked = readOnly || selectedQuote?.status === "emitted" || Boolean(selectedQuote?.emitted_at);

  async function load(selectId?: number) {
    const data = await apiClient.get<Quote[]>(`/laboratory/work-orders/${workOrderId}/quotes`);
    setQuotes(data);
    if (selectId) {
      const target = data.find((quote) => quote.id === selectId); if (target) selectQuote(target);
    } else if (data.length && selected === null) selectQuote(data[0]);
  }
  useEffect(() => { setSelected(null); setForm(empty(defect, quotedValue)); void load(); }, [workOrderId]);

  function selectQuote(quote: Quote) {
    setSelected(quote.id);
    setForm({
      service_code: quote.service_code, technical_report: quote.technical_report,
      services_description: quote.services_description ?? "", delivery_days: quote.delivery_days,
      billing_days: quote.billing_days, billing_terms: quote.billing_terms ?? `${quote.billing_days} dias`,
      warranty_months: quote.warranty_months, warranty_terms: quote.warranty_terms ?? `${quote.warranty_months} meses`,
      payment_terms: quote.payment_terms, validity_days: quote.validity_days,
      return_condition: quote.return_condition, consumer_clause: quote.consumer_clause,
      supply_clause: quote.supply_clause, estimate_clause: quote.estimate_clause,
      discount_type: quote.discount_type, discount_value: quote.discount_value ?? "0",
      items: quote.items.map((item) => ({ ...item, quantity: String(item.quantity), unit_value: String(item.unit_value ?? "0") })),
    });
  }
  const subtotal = useMemo(() => form.items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(String(item.unit_value).replace(",", ".")) || 0), 0), [form.items]);
  const discount = form.discount_type === "percent" ? subtotal * (Number(form.discount_value) || 0) / 100 : form.discount_type === "amount" ? Number(form.discount_value) || 0 : 0;
  const total = Math.max(0, subtotal - discount);
  const payload = () => ({ ...form, items: form.items.map((item) => ({ description: item.description, quantity: Number(item.quantity), unit_value: Number(String(item.unit_value).replace(",", ".")) })) });

  async function save() {
    if (locked) return;
    setBusy("save"); setSaved(false);
    try {
      const quote = selected
        ? await apiClient.put<Quote>(`/laboratory/quotes/${selected}`, payload())
        : await apiClient.post<Quote>(`/laboratory/work-orders/${workOrderId}/quotes`, payload());
      setSelected(quote.id); setSaved(true); await load(quote.id); setTimeout(() => setSaved(false), 1800);
    } finally { setBusy(null); }
  }
  async function remove() {
    if (!selected || locked || !confirm("Excluir este rascunho de orçamento?")) return;
    setBusy("delete");
    try { await apiClient.delete(`/laboratory/quotes/${selected}`); setSelected(null); setForm(empty(defect, quotedValue)); await load(); }
    finally { setBusy(null); }
  }
  function openPdf(preview: boolean) {
    if (!selected) return;
    window.open(`/api/laboratory/quotes/${selected}/pdf?preview=${preview}`, "_blank", "noopener,noreferrer");
    if (!preview) window.setTimeout(() => void load(selected), 900);
  }
  function newRevision() { setSelected(null); setForm(selectedQuote ? { ...form, items: form.items.map((item) => ({ ...item })) } : empty(defect, quotedValue)); }
  function updateItem(index: number, patch: Partial<QuoteItem>) { if (!locked) setForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, ...patch } : item) }); }
  const equipmentLabel = [equipmentType, manufacturer, model].filter(Boolean).join(" · ") || "Equipamento não identificado";

  return <div className={`lab-quote-editor lab-quote-workspace ${locked ? "is-locked" : ""}`}>
    <header className="lab-quote-hero">
      <div><span>ORÇAMENTO TÉCNICO</span><h3>{workOrderNumber}</h3><p>{customerName} · {equipmentLabel}</p></div>
      <div className="lab-quote-hero-meta"><span>{locked ? "EMITIDO" : "RASCUNHO"}</span><strong>{selectedQuote ? `Rev. ${String(selectedQuote.revision).padStart(2,"0")}` : "Nova revisão"}</strong></div>
    </header>

    {!!quotes.length && <div className="lab-quote-revisions">{quotes.map((quote) => <button key={quote.id} className={selected === quote.id ? "active" : ""} onClick={() => selectQuote(quote)}>R{String(quote.revision).padStart(2,"0")} · {quote.status === "emitted" ? "Emitido" : "Rascunho"}{!readOnly && ` · ${money(Number(quote.total ?? 0))}`}</button>)}</div>}

    <section className="lab-quote-context-grid">
      <article><small>CLIENTE</small><strong>{customerName}</strong><span>Dados vinculados automaticamente à O.S.</span></article>
      <article><small>EQUIPAMENTO</small><strong>{equipmentLabel}</strong><span>{[serialNumber && `Série ${serialNumber}`, power && `Potência ${power}`, voltage && `Tensão ${voltage}`].filter(Boolean).join(" · ") || "Sem especificações adicionais"}</span></article>
    </section>

    {readOnly && <div className="lab-quote-lock">Perfil LAB: orçamento disponível somente para consulta. Criação, alteração e emissão são bloqueadas.</div>}
    {!readOnly && locked && <div className="lab-quote-lock">Esta revisão já foi emitida e está protegida contra edição ou exclusão. Use <b>Nova revisão</b> para alterar a proposta.</div>}

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>01</span><div><strong>Diagnóstico e escopo técnico</strong><small>Informações que serão apresentadas ao cliente.</small></div></div>
      <div className="lab-quote-defect"><small>DEFEITO INFORMADO</small><p>{defect || "Não informado."}</p></div>
      <label>Diagnóstico técnico / laudo<textarea disabled={locked} rows={7} value={form.technical_report} onChange={(e)=>setForm({...form,technical_report:e.target.value})}/></label>
      <label>Serviço a realizar<textarea disabled={locked} rows={6} value={form.services_description} onChange={(e)=>setForm({...form,services_description:e.target.value})}/></label>
    </section>

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>02</span><div><strong>Serviços e componentes</strong><small>Composição comercial do orçamento.</small></div><ActionButton variant="secondary" disabled={locked} icon={<Plus size={16}/>} onClick={()=>setForm({...form,items:[...form.items,{description:"",quantity:"1",unit_value:"0"}]})}>Adicionar item</ActionButton></div>
      {readOnly ? <div className="lab-quote-items">{form.items.map((item,index)=><div className="lab-quote-item" key={index}><span>{item.description}</span><span>{item.quantity}</span></div>)}</div> : <>
        <div className="lab-quote-items"><div className="lab-quote-item lab-quote-item-head"><span>Descrição</span><span>Qtd.</span><span>Valor unitário</span><span/></div>{form.items.map((item,index)=><div className="lab-quote-item" key={index}><input disabled={locked} placeholder="Descrição" value={item.description} onChange={(e)=>updateItem(index,{description:e.target.value})}/><input disabled={locked} type="number" min="0.001" step="0.001" value={item.quantity} onChange={(e)=>updateItem(index,{quantity:e.target.value})}/><input disabled={locked} type="number" min="0" step="0.01" value={item.unit_value ?? "0"} onChange={(e)=>updateItem(index,{unit_value:e.target.value})}/><button disabled={locked} className="lab-icon-danger" onClick={()=>setForm({...form,items:form.items.filter((_,i)=>i!==index)})}><Trash2 size={16}/></button></div>)}</div>
        <div className="lab-quote-money-row"><label>Desconto<select disabled={locked} value={form.discount_type} onChange={(e)=>setForm({...form,discount_type:e.target.value as Form["discount_type"]})}><option value="none">Sem desconto</option><option value="amount">Valor em R$</option><option value="percent">Percentual %</option></select></label><Field disabled={locked || form.discount_type === "none"} label="Valor do desconto" value={form.discount_value} onChange={(v)=>setForm({...form,discount_value:v})}/><div className="lab-quote-total"><Calculator size={19}/><span>Subtotal <b>{money(subtotal)}</b><strong>{money(total)}</strong><small>TOTAL DO ORÇAMENTO</small></span></div></div>
      </>}
    </section>

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>03</span><div><strong>Condições comerciais</strong><small>Parâmetros resumidos na primeira página do PDF.</small></div></div>
      <div className="lab-grid three"><Field disabled={locked} label="Código de serviço" value={form.service_code} onChange={(v) => setForm({...form, service_code:v})}/><NumberField disabled={locked} label="Prazo de execução (dias)" value={form.delivery_days} onChange={(v)=>setForm({...form,delivery_days:v})}/><Field disabled={locked} label="Prazo para faturamento" value={form.billing_terms} onChange={(v)=>setForm({...form,billing_terms:v})}/><Field disabled={locked} label="Garantia" value={form.warranty_terms} onChange={(v)=>setForm({...form,warranty_terms:v})}/><NumberField disabled={locked} label="Validade (dias)" value={form.validity_days} onChange={(v)=>setForm({...form,validity_days:v})}/><Field disabled={locked} label="Pagamento" value={form.payment_terms} onChange={(v)=>setForm({...form,payment_terms:v})}/></div>
      <label>Condição de devolução<textarea disabled={locked} rows={2} value={form.return_condition} onChange={(e)=>setForm({...form,return_condition:e.target.value})}/></label>
    </section>

    <details className="lab-commercial-conditions"><summary>Cláusulas legais da proposta — mantidas no PDF</summary><label>Artigo / garantia legal<textarea disabled={locked} rows={3} value={form.consumer_clause} onChange={(e)=>setForm({...form,consumer_clause:e.target.value})}/></label><label>Cláusula de prazo, insumos e fornecedores<textarea disabled={locked} rows={5} value={form.supply_clause} onChange={(e)=>setForm({...form,supply_clause:e.target.value})}/></label><label>Cláusula de orçamento prévio e estimativo<textarea disabled={locked} rows={7} value={form.estimate_clause} onChange={(e)=>setForm({...form,estimate_clause:e.target.value})}/></label></details>

    <footer className="lab-quote-footer">{!readOnly && <><ActionButton variant="danger" loading={busy==="delete"} icon={<Trash2 size={17}/>} disabled={!selected || locked} onClick={()=>void remove()}>{busy==="delete"?"Excluindo...":"Excluir rascunho"}</ActionButton>{(!selectedQuote || selectedQuote.status === "emitted" || Boolean(selectedQuote.emitted_at)) && <ActionButton variant="secondary" icon={<FilePlus2 size={17}/>} onClick={newRevision}>Nova revisão</ActionButton>}</>}<span/>{!readOnly && <ActionButton variant="secondary" icon={<Eye size={17}/>} disabled={!selected} onClick={()=>openPdf(true)}>Visualizar PDF</ActionButton>}{!readOnly && <><ActionButton loading={busy==="save"} success={saved} icon={<Save size={17}/>} disabled={locked} onClick={()=>void save()}>{saved?"Orçamento salvo":"Salvar rascunho"}</ActionButton><ActionButton icon={<FileDown size={17}/>} disabled={!selected} onClick={()=>openPdf(false)}>Emitir PDF</ActionButton></>}</footer>
  </div>;
}
function Field({label,value,onChange,disabled=false}:{label:string;value:string;onChange:(v:string)=>void;disabled?:boolean}){return <label>{label}<input disabled={disabled} value={value} onChange={(e)=>onChange(e.target.value)}/></label>}
function NumberField({label,value,onChange,disabled=false}:{label:string;value:number;onChange:(v:number)=>void;disabled?:boolean}){return <label>{label}<input disabled={disabled} type="number" min="0" value={value} onChange={(e)=>onChange(Number(e.target.value))}/></label>}
function money(value:number){return value.toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}
