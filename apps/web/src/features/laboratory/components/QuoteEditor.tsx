import { useEffect, useMemo, useState } from "react";
import { Calculator, Eye, FileDown, FilePlus2, Printer, Plus, Save, Trash2 } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import type { Quote, QuoteItem } from "../types";
import { ActionButton } from "./ActionButton";

const CONSUMER = "Art. 26 do Código de Defesa do Consumidor: Produtos e serviços duráveis têm prazo de 90 dias para reclamação de vícios ocultos, contados a partir da entrega.";
const SUPPLY = "O prazo de execução e entrega dos serviços poderá ser prorrogado quando impossibilitado ou prejudicado por atraso, indisponibilidade ou irregularidade no fornecimento de insumos ou intercorrências imputáveis a fornecedores terceiros, incluindo atraso na entrega de materiais ou componentes essenciais, suspensão de fornecimento, descontinuação de produtos, falhas logísticas, restrições de estoque e situações de caso fortuito ou força maior que afetem a cadeia de suprimentos (arts. 393 e 396 do Código Civil). A prorrogação nas hipóteses previstas não caracterizará inadimplemento, tampouco ensejará penalidades ou sanções contratuais.";
const ESTIMATE = "O orçamento apresentado antes do início dos serviços técnicos possui natureza prévia e estimativa, não definitiva. Durante manutenções e reparos podem ser identificados defeitos ocultos, novos vícios, necessidade de peças adicionais ou serviços complementares somente verificáveis no decorrer da execução. Havendo necessidade de revisão de valor, a contratada comunicará o cliente por orçamento complementar detalhado e aguardará aprovação por meio eletrônico idôneo. Em caso de recusa ou ausência de resposta, os serviços adicionais não serão executados, permanecendo devidos, proporcionalmente, os serviços já realizados, peças adquiridas e custos operacionais incorridos. A empresa manterá registros de orçamentos, comunicações, laudos técnicos e aprovações ou recusas.";

type Form = {
  service_code: string; technical_report: string; services_description: string;
  delivery_days: number; billing_days: number; warranty_months: number; payment_terms: string;
  validity_days: number; return_condition: string; consumer_clause: string; supply_clause: string;
  estimate_clause: string; discount_type: "none" | "amount" | "percent"; discount_value: string;
  items: QuoteItem[];
};

const empty = (defect: string, value: string): Form => ({
  service_code: "3312102 / 14.01", technical_report: defect, services_description: "",
  delivery_days: 20, billing_days: 21, warranty_months: 3,
  payment_terms: "TRANSFERÊNCIA, BOLETO E PIX.", validity_days: 30,
  return_condition: "ORÇAMENTO NÃO APROVADO EM 30 DIAS: O EQUIPAMENTO SERÁ DEVOLVIDO.",
  consumer_clause: CONSUMER, supply_clause: SUPPLY, estimate_clause: ESTIMATE,
  discount_type: "none", discount_value: "0",
  items: [{ description: "SERVIÇO DE MANUTENÇÃO E REPARO", quantity: "1", unit_value: value || "0" }],
});

export function QuoteEditor({ workOrderId, workOrderNumber, defect, quotedValue }: { workOrderId: number; workOrderNumber: string; defect: string; quotedValue: string }) {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [form, setForm] = useState<Form>(() => empty(defect, quotedValue));
  const [busy, setBusy] = useState<"save" | "delete" | null>(null);
  const [saved, setSaved] = useState(false);

  async function load() {
    const data = await apiClient.get<Quote[]>(`/laboratory/work-orders/${workOrderId}/quotes`);
    setQuotes(data);
    if (data.length && selected === null) selectQuote(data[0]);
  }
  useEffect(() => { void load(); }, [workOrderId]);

  function selectQuote(quote: Quote) {
    setSelected(quote.id);
    setForm({
      service_code: quote.service_code, technical_report: quote.technical_report,
      services_description: quote.services_description ?? "", delivery_days: quote.delivery_days,
      billing_days: quote.billing_days, warranty_months: quote.warranty_months,
      payment_terms: quote.payment_terms, validity_days: quote.validity_days,
      return_condition: quote.return_condition, consumer_clause: quote.consumer_clause,
      supply_clause: quote.supply_clause, estimate_clause: quote.estimate_clause,
      discount_type: quote.discount_type, discount_value: quote.discount_value,
      items: quote.items.map((item) => ({ ...item, quantity: String(item.quantity), unit_value: String(item.unit_value) })),
    });
  }
  const subtotal = useMemo(() => form.items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(String(item.unit_value).replace(",", ".")) || 0), 0), [form.items]);
  const discount = form.discount_type === "percent" ? subtotal * (Number(form.discount_value) || 0) / 100 : form.discount_type === "amount" ? Number(form.discount_value) || 0 : 0;
  const total = Math.max(0, subtotal - discount);
  const payload = () => ({ ...form, items: form.items.map((item) => ({ description: item.description, quantity: Number(item.quantity), unit_value: Number(String(item.unit_value).replace(",", ".")) })) });

  async function save() {
    setBusy("save"); setSaved(false);
    try {
      const quote = selected
        ? await apiClient.put<Quote>(`/laboratory/quotes/${selected}`, payload())
        : await apiClient.post<Quote>(`/laboratory/work-orders/${workOrderId}/quotes`, payload());
      setSelected(quote.id); setSaved(true); await load(); setTimeout(() => setSaved(false), 1800);
    } finally { setBusy(null); }
  }
  async function remove() {
    if (!selected || !confirm("Excluir este rascunho de orçamento?")) return;
    setBusy("delete");
    try { await apiClient.delete(`/laboratory/quotes/${selected}`); setSelected(null); setForm(empty(defect, quotedValue)); await load(); }
    finally { setBusy(null); }
  }
  function openPdf(preview: boolean) {
    if (!selected) return;
    window.open(`/api/laboratory/quotes/${selected}/pdf?preview=${preview}`, "_blank", "noopener,noreferrer");
  }
  function label() { window.open(`/api/laboratory/work-orders/${workOrderId}/label.pdf`, "_blank", "noopener,noreferrer"); }
  function updateItem(index: number, patch: Partial<QuoteItem>) { setForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, ...patch } : item) }); }

  return <div className="lab-quote-editor">
    <div className="lab-quote-topbar">
      <div><strong>Orçamentos da {workOrderNumber}</strong><span>Rascunho, pré-visualização, PDF e revisões preservadas.</span></div>
      <div className="lab-quote-actions">
        <ActionButton variant="secondary" icon={<Printer size={17}/>} intent="print" onClick={label}>Etiqueta 40 × 40 mm</ActionButton>
        <ActionButton variant="secondary" icon={<FilePlus2 size={17}/>} intent="launch" onClick={() => { setSelected(null); setForm(empty(defect, quotedValue)); }}>Nova revisão</ActionButton>
      </div>
    </div>
    {!!quotes.length && <div className="lab-quote-revisions">{quotes.map((quote) => <button key={quote.id} className={selected === quote.id ? "active" : ""} onClick={() => selectQuote(quote)}>R{String(quote.revision).padStart(2,"0")} · {quote.status === "emitted" ? "Emitido" : "Rascunho"} · {money(Number(quote.total))}</button>)}</div>}
    <div className="lab-grid three"><Field label="Código de serviço" value={form.service_code} onChange={(v) => setForm({...form, service_code:v})}/><NumberField label="Prazo de entrega (dias)" value={form.delivery_days} onChange={(v)=>setForm({...form,delivery_days:v})}/><NumberField label="Prazo para faturamento (dias)" value={form.billing_days} onChange={(v)=>setForm({...form,billing_days:v})}/><NumberField label="Garantia (meses)" value={form.warranty_months} onChange={(v)=>setForm({...form,warranty_months:v})}/><NumberField label="Validade (dias)" value={form.validity_days} onChange={(v)=>setForm({...form,validity_days:v})}/><Field label="Pagamento" value={form.payment_terms} onChange={(v)=>setForm({...form,payment_terms:v})}/></div>
    <label>Laudo técnico detalhado<textarea rows={8} value={form.technical_report} onChange={(e)=>setForm({...form,technical_report:e.target.value})}/></label>
    <label>Serviços a serem realizados<textarea rows={6} value={form.services_description} onChange={(e)=>setForm({...form,services_description:e.target.value})}/></label>
    <div className="lab-quote-items"><header><strong>Serviços e componentes</strong><ActionButton variant="secondary" icon={<Plus size={16}/>} intent="launch" onClick={()=>setForm({...form,items:[...form.items,{description:"",quantity:"1",unit_value:"0"}]})}>Adicionar item</ActionButton></header>{form.items.map((item,index)=><div className="lab-quote-item" key={index}><input placeholder="Descrição" value={item.description} onChange={(e)=>updateItem(index,{description:e.target.value})}/><input type="number" min="0.001" step="0.001" value={item.quantity} onChange={(e)=>updateItem(index,{quantity:e.target.value})}/><input type="number" min="0" step="0.01" value={item.unit_value} onChange={(e)=>updateItem(index,{unit_value:e.target.value})}/><button className="lab-icon-danger" onClick={()=>setForm({...form,items:form.items.filter((_,i)=>i!==index)})}><Trash2 size={16}/></button></div>)}</div>
    <div className="lab-grid three"><label>Tipo de desconto<select value={form.discount_type} onChange={(e)=>setForm({...form,discount_type:e.target.value as Form["discount_type"]})}><option value="none">Sem desconto</option><option value="amount">Em reais (R$)</option><option value="percent">Em porcentagem (%)</option></select></label><Field label="Valor do desconto" value={form.discount_value} onChange={(v)=>setForm({...form,discount_value:v})}/><div className="lab-quote-total"><Calculator size={18}/><span>Subtotal {money(subtotal)}<strong>Total {money(total)}</strong></span></div></div>
    <details open className="lab-commercial-conditions"><summary>Condições comerciais e cláusulas editáveis</summary><label>Condição de devolução<textarea rows={2} value={form.return_condition} onChange={(e)=>setForm({...form,return_condition:e.target.value})}/></label><label>Artigo / garantia legal<textarea rows={3} value={form.consumer_clause} onChange={(e)=>setForm({...form,consumer_clause:e.target.value})}/></label><label>Cláusula de prazo, insumos e fornecedores<textarea rows={5} value={form.supply_clause} onChange={(e)=>setForm({...form,supply_clause:e.target.value})}/></label><label>Cláusula de orçamento prévio e estimativo<textarea rows={7} value={form.estimate_clause} onChange={(e)=>setForm({...form,estimate_clause:e.target.value})}/></label></details>
    <footer className="lab-quote-footer"><ActionButton variant="danger" loading={busy==="delete"} icon={<Trash2 size={17}/>} intent="delete" disabled={!selected} onClick={()=>void remove()}>{busy==="delete"?"Excluindo...":"Excluir rascunho"}</ActionButton><span/><ActionButton variant="secondary" icon={<Eye size={17}/>} intent="preview" disabled={!selected} onClick={()=>openPdf(true)}>Pré-visualizar PDF</ActionButton><ActionButton loading={busy==="save"} success={saved} icon={<Save size={17}/>} intent="save" onClick={()=>void save()}>{saved?"Orçamento salvo":"Salvar orçamento"}</ActionButton><ActionButton icon={<FileDown size={17}/>} intent="launch" disabled={!selected} onClick={()=>openPdf(false)}>Emitir PDF</ActionButton></footer>
  </div>;
}
function Field({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}){return <label>{label}<input value={value} onChange={(e)=>onChange(e.target.value)}/></label>}
function NumberField({label,value,onChange}:{label:string;value:number;onChange:(v:number)=>void}){return <label>{label}<input type="number" min="0" value={value} onChange={(e)=>onChange(Number(e.target.value))}/></label>}
function money(value:number){return value.toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}
