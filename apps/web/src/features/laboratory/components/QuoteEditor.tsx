import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from "react";
import { Calculator, ChevronDown, Eye, FileDown, FilePlus2, Image, Plus, Save, Trash2, UploadCloud } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import { ApiError } from "../../../shared/api/apiError";
import type { Quote, QuoteItem, QuotePhoto } from "../types";
import { ActionButton } from "./ActionButton";
import { expectedQuoteTotal, quoteMoneyNumber, quoteNumber, verifyQuoteSaved, type QuoteSaveSnapshot } from "./quoteSaveGuard";

const CONSUMER = "Art. 26 do Código de Defesa do Consumidor: Produtos e serviços duráveis têm prazo de 90 dias para reclamação de vícios ocultos, contados a partir da entrega.";
const SUPPLY = "O prazo de execução e entrega dos serviços poderá ser prorrogado quando impossibilitado ou prejudicado por atraso, indisponibilidade ou irregularidade no fornecimento de insumos ou intercorrências imputáveis a fornecedores terceiros, incluindo atraso na entrega de materiais ou componentes essenciais, suspensão de fornecimento, descontinuação de produtos, falhas logísticas, restrições de estoque e situações de caso fortuito ou força maior que afetem a cadeia de suprimentos (arts. 393 e 396 do Código Civil). A prorrogação nas hipóteses previstas não caracterizará inadimplemento, tampouco ensejará penalidades ou sanções contratuais.";
const MAX_QUOTE_PHOTOS = 10;
const MAX_PHOTO_BYTES = 15 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const ESTIMATE = "O orçamento apresentado antes do início dos serviços técnicos possui natureza prévia e estimativa, não definitiva. Durante manutenções e reparos podem ser identificados defeitos ocultos, novos vícios, necessidade de peças adicionais ou serviços complementares somente verificáveis no decorrer da execução. Havendo necessidade de revisão de valor, a contratada comunicará o cliente por orçamento complementar detalhado e aguardará aprovação por meio eletrônico idôneo. Em caso de recusa ou ausência de resposta, os serviços adicionais não serão executados, permanecendo devidos, proporcionalmente, os serviços já realizados, peças adquiridas e custos operacionais incorridos. A empresa manterá registros de orçamentos, comunicações, laudos técnicos e aprovações ou recusas.";

type Form = {
  service_code: string; technical_report: string; services_description: string;
  delivery_days: number; billing_days: number; billing_terms: string; warranty_months: number; warranty_terms: string; payment_terms: string;
  validity_days: number; return_condition: string; consumer_clause: string; supply_clause: string;
  estimate_clause: string; discount_type: "none" | "amount" | "percent"; discount_value: string;
  items: QuoteItem[];
  photos: QuotePhoto[];
};

export type QuoteEditorHandle = { save: () => Promise<void> };

type Props = {
  saveRef?: Ref<QuoteEditorHandle>;
  workOrderId: number; workOrderNumber: string; customerName: string; defect: string; quotedValue: string;
  equipmentType: string; manufacturer: string; model: string; serialNumber: string; power: string; voltage: string;
  readOnly?: boolean;
};

const empty = (defect: string, value: string): Form => ({
  service_code: "3312102 / 14.01", technical_report: defect, services_description: "",
  delivery_days: 20, billing_days: 21, billing_terms: "21 dias", warranty_months: 3, warranty_terms: "3 meses",
  payment_terms: "TRANSFERÊNCIA, BOLETO E PIX.", validity_days: 30,
  return_condition: "ORÇAMENTO NÃO APROVADO EM 30 DIAS: O EQUIPAMENTO SERÁ DEVOLVIDO.",
  consumer_clause: CONSUMER, supply_clause: SUPPLY, estimate_clause: ESTIMATE,
  discount_type: "none", discount_value: "0",
  items: [{ description: "SERVIÇO DE MANUTENÇÃO E REPARO", quantity: "1", unit_value: value || "0" }],
  photos: [],
});

export function QuoteEditor(props: Props) {
  const { workOrderId, workOrderNumber, customerName, defect, quotedValue, equipmentType, manufacturer, model, serialNumber, power, voltage, readOnly = false } = props;
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [form, setForm] = useState<Form>(() => empty(defect, quotedValue));
  const [busy, setBusy] = useState<"save" | "delete" | "upload" | "emit" | "preview" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showMobileContext, setShowMobileContext] = useState(false);
  const editedSinceLoad = useRef(false);
  const activeOrderId = useRef(workOrderId);
  const selectedQuote = quotes.find((quote) => quote.id === selected) ?? null;
  const locked = readOnly || selectedQuote?.status === "emitted" || Boolean(selectedQuote?.emitted_at);
  const editingBlocked = locked || busy === "save" || busy === "emit" || busy === "preview";

  function editForm(next: Form | ((previous: Form) => Form)) {
    editedSinceLoad.current = true;
    setSaved(false);
    setDirty(true);
    setError("");
    setNotice("");
    setForm(next);
  }

  async function load(selectId?: number): Promise<Quote | null> {
    const orderId = workOrderId;
    const data = await apiClient.get<Quote[]>(`/laboratory/work-orders/${orderId}/quotes`);
    // Não aplicar uma resposta atrasada de outra OS, nem descartar edição em curso.
    if (activeOrderId.current !== orderId) return null;
    setQuotes(data);
    // Preferir um rascunho editável (inclusive o reaproveitado de uma revisão
    // anterior) impede o operador de editar a revisão emitida por engano.
    const target = selectId != null
      ? data.find((quote) => quote.id === selectId)
      : data.find((quote) => quote.status === "draft" && !quote.emitted_at) ?? data[0];
    if (target && (selectId != null || !editedSinceLoad.current)) selectQuote(target);
    return target ?? null;
  }
  useEffect(() => {
    activeOrderId.current = workOrderId;
    editedSinceLoad.current = false;
    setSelected(null); setForm(empty(defect, quotedValue)); setShowMobileContext(false);
    void load().catch((cause) => setError(cause instanceof Error ? cause.message : "Falha ao carregar os rascunhos."));
  }, [workOrderId]);

  function selectQuote(quote: Quote) {
    editedSinceLoad.current = false;
    setSelected(quote.id);
    setDirty(false);
    setError("");
    setNotice("");
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
      photos: quote.photos ?? [],
    });
  }
  const subtotal = useMemo(() => form.items.reduce((sum, item) => sum + quoteNumber(item.quantity) * quoteMoneyNumber(item.unit_value), 0), [form.items]);
  const discount = form.discount_type === "percent"
    ? subtotal * quoteMoneyNumber(form.discount_value) / 100
    : form.discount_type === "amount" ? quoteMoneyNumber(form.discount_value) : 0;
  const total = Math.max(0, subtotal - discount);
  const itemTotal = (item: QuoteItem) => quoteNumber(item.quantity) * quoteMoneyNumber(item.unit_value);
  const payload = (): QuoteSaveSnapshot => ({ ...form,
    discount_value: quoteMoneyNumber(form.discount_value),
    items: form.items.map((item) => ({
      description: item.description,
      quantity: quoteNumber(item.quantity),
      unit_value: quoteMoneyNumber(item.unit_value),
    })),
    photos: form.photos.map((photo) => ({ document_id: photo.document_id, caption: photo.caption })),
  });

  // A leitura do servidor deve ser CONFIRMADA antes de substituir os dados em
  // tela. Na V40, load() reidratava a revisão antiga mesmo quando falhava a
  // verificação, produzindo o efeito de piscar e voltar ao valor anterior.
  async function persistDraft(): Promise<Quote> {
    const snapshot = payload();
    const expectedTotalCents = expectedQuoteTotal(snapshot);
    if (!snapshot.items.length) throw new Error("Inclua pelo menos um serviço ou componente no orçamento.");
    if (snapshot.items.some((item) => !item.description.trim() || !Number.isFinite(item.quantity) || item.quantity <= 0 || !Number.isFinite(item.unit_value) || item.unit_value < 0)) {
      throw new Error("Confira a descrição, a quantidade e o valor unitário de cada item.");
    }
    if (!Number.isFinite(expectedTotalCents) || !Number.isFinite(snapshot.discount_value) || snapshot.discount_value < 0) {
      throw new Error("Há um valor inválido no orçamento. Confira os itens e o desconto.");
    }
    const invalidQuantity = snapshot.items.find((item) => Math.abs(item.quantity * 1000 - Math.round(item.quantity * 1000)) > 0.000001);
    const invalidPrice = snapshot.items.find((item) => Math.abs(item.unit_value * 100 - Math.round(item.unit_value * 100)) > 0.000001);
    if (invalidQuantity) throw new Error("A quantidade aceita até três casas decimais.");
    if (invalidPrice) throw new Error(`O valor unitário do item “${invalidPrice.description}” aceita até duas casas decimais.`);
    if (Math.abs(snapshot.discount_value * 100 - Math.round(snapshot.discount_value * 100)) > 0.000001) {
      throw new Error("Informe o desconto com no máximo duas casas decimais.");
    }
    // Bloqueia de modo explícito API antiga, evitando uma tela V42 apontando
    // para um container desatualizado com contrato de gravação incompatível.
    try {
      const capability = await apiClient.get<{contract:string}>("/laboratory/quotes/write-contract");
      if (capability.contract !== "quote-save-v42") throw new Error("Versão incompatível da API de orçamentos.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status !== 404) throw cause;
      throw new Error("A API de orçamentos está desatualizada. Recompile e reinicie também o container API do SÊNTICO V42 antes de salvar.");
    }
    // Verifica a resposta da gravação e depois uma NOVA leitura da API.
    // Qualquer divergência mantém todos os valores digitados na tela.
    const result = selected
      ? await apiClient.put<Quote>(`/laboratory/quotes/${selected}`, snapshot)
      : await apiClient.post<Quote>(`/laboratory/work-orders/${workOrderId}/quotes`, snapshot);
    const responseError = verifyQuoteSaved(snapshot, result);
    // Uma resposta do PUT pode estar desatualizada; a conferência decisiva é
    // o registro lido NOVAMENTE em uma requisição sem cache, após o commit.
    const data = await apiClient.get<Quote[]>(`/laboratory/work-orders/${workOrderId}/quotes?confirm=${Date.now()}`);
    const savedQuote = data.find((quote) => quote.id === result.id);
    if (!savedQuote) throw new Error("A API recebeu o orçamento, mas não confirmou a revisão em uma nova consulta. Seus valores continuam na tela.");
    const persistedError = verifyQuoteSaved(snapshot, savedQuote);
    if (persistedError) {
      throw new Error(`${persistedError} ${responseError ? `Resposta inicial: ${responseError}.` : ""} Os dados digitados continuam na tela. Confira a API e o banco antes de tentar emitir.`);
    }
    setQuotes(data);
    selectQuote(savedQuote); // somente após confirmação da consulta persistida
    setDirty(false);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
    return savedQuote;
  }

  async function save() {
    if (locked || busy) return;
    setBusy("save"); setSaved(false); setError(""); setNotice("");
    try {
      const result = await persistDraft();
      setNotice(`Revisão ${String(result.revision).padStart(2, "0")} salva e conferida: ${money(Number(result.total ?? 0))}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível salvar o orçamento. Suas alterações continuam nesta tela.");
    } finally { setBusy(null); }
  }

  useImperativeHandle(props.saveRef, () => ({ save }), [save]);

  async function remove() {
    if (!selected || locked || busy || !confirm("Excluir este rascunho de orçamento?")) return;
    setBusy("delete"); setError(""); setNotice("");
    try {
      await apiClient.delete(`/laboratory/quotes/${selected}`);
      setSelected(null); setForm(empty(defect, quotedValue));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível excluir o rascunho.");
    } finally { setBusy(null); }
  }

  async function openPdf(preview: boolean) {
    if (busy) return;
    // Abrir antes de iniciar a requisição assíncrona evita bloqueadores de
    // pop-up. Uma falha exibe erro no formulário e fecha a aba vazia.
    const previewWindow = preview ? window.open("", "_blank") : null;
    if (previewWindow) {
      previewWindow.document.title = "Preparando orçamento — SÊNTICO";
      previewWindow.document.body.textContent = "Preparando PDF do orçamento...";
    }
    setBusy(preview ? "preview" : "emit"); setError(""); setNotice("");
    try {
      let quoteId = selected;
      let revision = selectedQuote?.revision ?? 1;
      let alreadyEmitted = Boolean(selectedQuote?.status === "emitted" || selectedQuote?.emitted_at);
      // Clicar em Emitir/Visualizar não exige dois passos. Primeiro salvar
      // alterações, depois conferir o total, só então pedir o PDF ao servidor.
      if (!locked && (dirty || !quoteId)) {
        const current = await persistDraft();
        quoteId = current.id;
        revision = current.revision;
        alreadyEmitted = Boolean(current.status === "emitted" || current.emitted_at);
      }
      if (!quoteId) throw new Error("Não há orçamento salvo para gerar o PDF.");
      const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "/api";
      const uri = alreadyEmitted || preview
        ? `${base}/laboratory/quotes/${quoteId}/pdf?preview=${preview ? "true" : "false"}`
        : `${base}/laboratory/quotes/${quoteId}/emit`;
      const response = await fetch(uri, {
        method: alreadyEmitted || preview ? "GET" : "POST",
        credentials: "include", cache: "no-store", headers: { Accept: "application/pdf" },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null) as { detail?: unknown } | null;
        const detail = typeof data?.detail === "string" ? data.detail : `Falha HTTP ${response.status} ao gerar o PDF.`;
        if (response.status === 401) window.dispatchEvent(new Event("nexus:session-expired"));
        throw new Error(detail);
      }
      const blob = await response.blob();
      if (!blob.type.includes("pdf") || blob.size < 100) {
        throw new Error("O servidor não retornou um PDF válido. Confira a revisão antes de tentar novamente.");
      }
      const link = URL.createObjectURL(blob);
      if (preview && previewWindow && !previewWindow.closed) {
        previewWindow.location.replace(link);
      } else {
        const anchor = document.createElement("a");
        anchor.href = link;
        anchor.download = `orcamento-${workOrderNumber.replace(/[^a-zA-Z0-9-]/g, "")}-r${String(revision).padStart(2, "0")}.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      }
      window.setTimeout(() => URL.revokeObjectURL(link), 120_000);
      if (!preview && !alreadyEmitted) {
        const updated = await load(quoteId);
        if (!updated || (updated.status !== "emitted" && !updated.emitted_at)) {
          throw new Error("O PDF foi recebido, mas não foi possível confirmar o status emitido. Atualize a O.S. antes de tentar novamente.");
        }
      }
      setNotice(preview ? "Prévia gerada com os valores gravados." : "PDF emitido com os valores confirmados no servidor.");
    } catch (cause) {
      if (previewWindow && !previewWindow.closed) previewWindow.close();
      setError(cause instanceof Error ? cause.message : "Não foi possível emitir o PDF. O rascunho foi preservado.");
    } finally { setBusy(null); }
  }

  async function newRevision() {
    if (busy) return;
    if (!selectedQuote) {
      if (dirty && !window.confirm("Descartar as alterações ainda não salvas?")) return;
      setSelected(null); setForm(empty(defect, quotedValue)); setError(""); return;
    }
    if (selectedQuote.status !== "emitted" && !selectedQuote.emitted_at) return;
    setBusy("save"); setError(""); setNotice("");
    try {
      // A API reutiliza a revisão ainda em rascunho, em vez de obrigar sua exclusão.
      const quote = await apiClient.post<Quote>(`/laboratory/quotes/${selectedQuote.id}/revisions`);
      await load(quote.id);
      setNotice(`Revisão ${String(quote.revision).padStart(2, "0")} aberta. Você pode alterar o valor e salvar normalmente.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível abrir o rascunho desta OS.");
    } finally { setBusy(null); }
  }
  async function uploadReportPhotos(files: FileList | null) {
    if (!files?.length || locked || busy) return;
    const selectedFiles = Array.from(files);
    const available = MAX_QUOTE_PHOTOS - form.photos.length;
    if (selectedFiles.length > available) {
      setError(`Você pode anexar até ${MAX_QUOTE_PHOTOS} fotos por revisão. Restam ${available} vaga(s).`);
      return;
    }
    if (selectedFiles.some((file) => !ALLOWED_PHOTO_TYPES.has(file.type))) {
      setError("Formato não permitido. Selecione apenas fotos JPG, PNG ou WEBP.");
      return;
    }
    if (selectedFiles.some((file) => file.size > MAX_PHOTO_BYTES)) {
      setError("Uma das fotos excede 15 MB. Reduza o arquivo e tente novamente.");
      return;
    }
    setBusy("upload"); setSaved(false); setError("");
    const uploaded: QuotePhoto[] = [];
    let uploadError = "";
    try {
      for (const file of selectedFiles) {
        const body = new FormData(); body.append("file", file);
        const doc = await apiClient.post<{id:number; original_name:string; mime_type:string}>(
          `/laboratory/work-orders/${workOrderId}/documents?category=analise`, body
        );
        uploaded.push({id:undefined, document_id:doc.id, position:form.photos.length+uploaded.length+1, caption:null, original_name:doc.original_name, mime_type:doc.mime_type});
      }
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Falha no envio da foto.";
      uploadError = `${detail} ${uploaded.length ? `${uploaded.length} foto(s) enviada(s) foram preservadas na tela.` : "Nenhuma foto foi adicionada."}`;
    } finally {
      if (uploaded.length) {
        editForm((current) => ({...current, photos: [...current.photos, ...uploaded]}));
      }
      if (uploadError) setError(uploadError);
      setBusy(null);
    }
  }
  function updateItem(index: number, patch: Partial<QuoteItem>) { if (!editingBlocked) editForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, ...patch } : item) }); }
  const equipmentLabel = [equipmentType, manufacturer, model].filter(Boolean).join(" · ") || "Equipamento não identificado";

  return <div className={`lab-quote-editor lab-quote-workspace ${locked ? "is-locked" : ""}`}>
    <header className="lab-quote-hero">
      <div><span>ORÇAMENTO TÉCNICO</span><h3>{workOrderNumber}</h3><p>{customerName} · {equipmentLabel}</p></div>
      <div className="lab-quote-hero-meta"><span>{locked ? "EMITIDO" : "RASCUNHO"}</span><strong>{selectedQuote ? `Rev. ${String(selectedQuote.revision).padStart(2,"0")}` : "Nova revisão"}</strong></div>
    </header>

    {!!quotes.length && <div className="lab-quote-revisions">{quotes.map((quote) => <button key={quote.id} className={selected === quote.id ? "active" : ""} disabled={!!busy} onClick={() => {if (busy) return; if (dirty && !window.confirm("Há alterações não salvas. Deseja descartá-las e abrir outra revisão?")) return; selectQuote(quote);}}>R{String(quote.revision).padStart(2,"0")} · {quote.status === "emitted" ? "Emitido" : "Rascunho"}{!readOnly && ` · ${money(Number(quote.total ?? 0))}`}</button>)}</div>}

    {notice && <div className="lab-quote-save-confirmation" role="status">{notice}</div>}
    {error && <div className="lab-quote-error" role="alert">{error}</div>}

    <button type="button" className="lab-quote-context-toggle" aria-expanded={showMobileContext} onClick={() => setShowMobileContext((value) => !value)}>
      <span>Dados completos do cliente e equipamento</span>
      <ChevronDown size={17} aria-hidden="true" />
    </button>
    <section className={`lab-quote-context-grid${showMobileContext ? " is-mobile-open" : ""}`}>
      <article><small>CLIENTE</small><strong>{customerName}</strong><span>Dados vinculados automaticamente à O.S.</span></article>
      <article><small>EQUIPAMENTO</small><strong>{equipmentLabel}</strong><span>{[serialNumber && `Série ${serialNumber}`, power && `Potência ${power}`, voltage && `Tensão ${voltage}`].filter(Boolean).join(" · ") || "Sem especificações adicionais"}</span></article>
    </section>

    {readOnly && <div className="lab-quote-lock">Perfil LAB: orçamento disponível somente para consulta. Criação, alteração e emissão são bloqueadas.</div>}
    {!readOnly && locked && <div className="lab-quote-lock">Esta revisão já foi emitida e está protegida contra edição ou exclusão. Use <b>Nova revisão</b> para alterar a proposta.</div>}

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>01</span><div><strong>Diagnóstico e escopo técnico</strong><small>Informações que serão apresentadas ao cliente.</small></div></div>
      <div className="lab-quote-defect"><small>DEFEITO INFORMADO</small><p>{defect || "Não informado."}</p></div>
      <label>Diagnóstico técnico / laudo<textarea disabled={editingBlocked} rows={7} value={form.technical_report} onChange={(e)=>editForm({...form,technical_report:e.target.value})}/></label>
      <label>Serviço a realizar<textarea disabled={editingBlocked} rows={6} value={form.services_description} onChange={(e)=>editForm({...form,services_description:e.target.value})}/></label>
    </section>

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>02</span><div><strong>Serviços e componentes</strong><small>Composição comercial do orçamento.</small></div><ActionButton variant="secondary" disabled={editingBlocked} icon={<Plus size={16}/>} onClick={()=>editForm({...form,items:[...form.items,{description:"",quantity:"1",unit_value:"0"}]})}>Adicionar item</ActionButton></div>
      {readOnly ? <div className="lab-quote-items"><div className="lab-quote-item lab-quote-item-head"><span>Descrição</span><span>Qtd.</span><span>Valor unitário</span><span>Total do item</span><span/></div>{form.items.map((item,index)=><div className="lab-quote-item" key={index}><span>{item.description}</span><span>{item.quantity}</span><span>{money(Number(String(item.unit_value ?? "0").replace(",", ".")) || 0)}</span><span className="lab-quote-line-total">{money(itemTotal(item))}</span><span /></div>)}</div> : <>
        <div className="lab-quote-items"><div className="lab-quote-item lab-quote-item-head"><span>Descrição</span><span>Qtd.</span><span>Valor unitário</span><span>Total do item</span><span/></div>{form.items.map((item,index)=><div className="lab-quote-item" key={index}><input disabled={editingBlocked} placeholder="Descrição" value={item.description} onChange={(e)=>updateItem(index,{description:e.target.value})}/><input disabled={editingBlocked} type="number" min="0.001" step="0.001" value={item.quantity} onChange={(e)=>updateItem(index,{quantity:e.target.value})}/><input disabled={editingBlocked} type="text" inputMode="decimal" aria-label="Valor unitário em reais" placeholder="0,00" value={item.unit_value ?? "0"} onChange={(e)=>updateItem(index,{unit_value:e.target.value})}/><div className="lab-quote-line-total">{money(itemTotal(item))}</div><button type="button" disabled={editingBlocked} className="lab-icon-danger" onClick={()=>editForm({...form,items:form.items.filter((_,i)=>i!==index)})}><Trash2 size={16}/></button></div>)}</div>
        <div className="lab-quote-money-row"><label>Desconto<select disabled={editingBlocked} value={form.discount_type} onChange={(e)=>editForm({...form,discount_type:e.target.value as Form["discount_type"]})}><option value="none">Sem desconto</option><option value="amount">Valor em R$</option><option value="percent">Percentual %</option></select></label><Field disabled={editingBlocked || form.discount_type === "none"} label="Valor do desconto" value={form.discount_value} onChange={(v)=>editForm({...form,discount_value:v})}/><div className="lab-quote-total"><Calculator size={19}/><span>Subtotal <b>{money(subtotal)}</b><strong>{money(total)}</strong><small>TOTAL DO ORÇAMENTO</small></span></div></div>
      </>}
    </section>

    <section className="lab-quote-section">
      <div className="lab-quote-section-title"><span>03</span><div><strong>Condições comerciais</strong><small>Parâmetros resumidos na primeira página do PDF.</small></div></div>
      <div className="lab-grid three"><Field disabled={editingBlocked} label="Código de serviço" value={form.service_code} onChange={(v) => editForm({...form, service_code:v})}/><NumberField disabled={editingBlocked} label="Prazo de execução (dias)" value={form.delivery_days} onChange={(v)=>editForm({...form,delivery_days:v})}/><Field disabled={editingBlocked} label="Prazo para faturamento" value={form.billing_terms} onChange={(v)=>editForm({...form,billing_terms:v})}/><Field disabled={editingBlocked} label="Garantia" value={form.warranty_terms} onChange={(v)=>editForm({...form,warranty_terms:v})}/><NumberField disabled={editingBlocked} label="Validade (dias)" value={form.validity_days} onChange={(v)=>editForm({...form,validity_days:v})}/><Field disabled={editingBlocked} label="Pagamento" value={form.payment_terms} onChange={(v)=>editForm({...form,payment_terms:v})}/></div>
      <label>Condição de devolução<textarea disabled={editingBlocked} rows={2} value={form.return_condition} onChange={(e)=>editForm({...form,return_condition:e.target.value})}/></label>
    </section>

    <details className="lab-commercial-conditions"><summary>Cláusulas legais da proposta — mantidas no PDF</summary><label>Artigo / garantia legal<textarea disabled={editingBlocked} rows={3} value={form.consumer_clause} onChange={(e)=>editForm({...form,consumer_clause:e.target.value})}/></label><label>Cláusula de prazo, insumos e fornecedores<textarea disabled={editingBlocked} rows={5} value={form.supply_clause} onChange={(e)=>editForm({...form,supply_clause:e.target.value})}/></label><label>Cláusula de orçamento prévio e estimativo<textarea disabled={editingBlocked} rows={7} value={form.estimate_clause} onChange={(e)=>editForm({...form,estimate_clause:e.target.value})}/></label></details>

    <section className="lab-quote-section lab-quote-photo-section">
      <div className="lab-quote-section-title"><span>04</span><div><strong>Registro fotográfico do laudo · {form.photos.length}/{MAX_QUOTE_PHOTOS} fotos</strong><small>Até {MAX_QUOTE_PHOTOS} fotos por revisão. As imagens aparecem no final do PDF, depois das cláusulas.</small></div></div>
      {!locked && <label className={`lab-quote-photo-upload ${busy || form.photos.length >= MAX_QUOTE_PHOTOS ? "is-disabled" : ""}`}><UploadCloud size={17}/><span>{busy === "upload" ? "Enviando fotos..." : form.photos.length >= MAX_QUOTE_PHOTOS ? "Limite de 10 fotos atingido" : "Anexar fotos ao laudo"}</span><input type="file" multiple disabled={!!busy || form.photos.length >= MAX_QUOTE_PHOTOS} accept="image/jpeg,image/png,image/webp" onChange={(e)=>{void uploadReportPhotos(e.target.files);e.currentTarget.value="";}}/></label>}
      {!form.photos.length && <div className="lab-empty">Nenhuma foto vinculada a esta revisão.</div>}
      {!!form.photos.length && <div className="lab-quote-photo-grid">{form.photos.map((photo,index)=><article key={`${photo.document_id}-${index}`}><img src={`/api/laboratory/documents/${photo.document_id}/preview`} alt={photo.original_name}/><input disabled={editingBlocked} placeholder="Legenda opcional" value={photo.caption ?? ""} onChange={(e)=>editForm({...form,photos:form.photos.map((item,i)=>i===index?{...item,caption:e.target.value}:item)})}/>{!locked&&<button type="button" className="lab-icon-danger" disabled={editingBlocked} onClick={()=>editForm({...form,photos:form.photos.filter((_,i)=>i!==index)})}><Trash2 size={15}/> Remover do laudo</button>}</article>)}</div>}
    </section>

    {!locked && dirty && <p className="lab-quote-unsaved" role="status">Alterações pendentes. Clique em <strong>Salvar rascunho</strong> para gravar valores, legendas e fotos.</p>}
    <footer className="lab-quote-footer">{!readOnly && <><ActionButton variant="danger" loading={busy==="delete"} icon={<Trash2 size={17}/>} disabled={!selected || locked || !!busy} onClick={()=>void remove()}>{busy==="delete"?"Excluindo...":"Excluir rascunho"}</ActionButton>{(!selectedQuote || selectedQuote.status === "emitted" || Boolean(selectedQuote.emitted_at)) && <ActionButton variant="secondary" icon={<FilePlus2 size={17}/>} disabled={!!busy} onClick={()=>void newRevision()}>Nova revisão</ActionButton>}</>}<span/>{!readOnly && <ActionButton variant="secondary" icon={<Eye size={17}/>} disabled={!!busy} onClick={()=>void openPdf(true)}>Visualizar PDF</ActionButton>}{!readOnly && <><ActionButton loading={busy==="save" || busy==="emit"} success={saved} icon={<Save size={17}/>} disabled={locked || !!busy} onClick={()=>void save()}>{saved?"Orçamento salvo":"Salvar rascunho"}</ActionButton><ActionButton loading={busy==="emit"} icon={<FileDown size={17}/>} disabled={!!busy} onClick={()=>void openPdf(false)}>{locked ? "Baixar PDF emitido" : "Salvar e emitir PDF"}</ActionButton></>}</footer>
  </div>;
}
function Field({label,value,onChange,disabled=false}:{label:string;value:string;onChange:(v:string)=>void;disabled?:boolean}){return <label>{label}<input disabled={disabled} value={value} onChange={(e)=>onChange(e.target.value)}/></label>}
function NumberField({label,value,onChange,disabled=false}:{label:string;value:number;onChange:(v:number)=>void;disabled?:boolean}){return <label>{label}<input disabled={disabled} type="number" min="0" value={value} onChange={(e)=>onChange(Number(e.target.value))}/></label>}
function money(value:number){return value.toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}
