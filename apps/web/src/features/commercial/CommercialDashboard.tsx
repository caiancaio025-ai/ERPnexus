import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, FileText, LogOut, PackagePlus, Printer, Search, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/apiClient";
import type { AuthUser } from "../auth/AuthCard";
import type { CommercialEquipment, CommercialPurpose, CompanyCode } from "./types";
import "./commercial.css";

type Props = { user: AuthUser; onLogout: () => void };
type Tab = "cadastros" | "ativos" | "orcamento" | "preventiva" | "relatorios";

type FormState = {
  company_code: CompanyCode;
  purpose: CommercialPurpose;
  equipment_type: string;
  manufacturer: string;
  model: string;
  power: string;
  voltage: string;
  notes: string;
};

const emptyForm = (): FormState => ({
  company_code: "universo_eletronica",
  purpose: "rental_sale",
  equipment_type: "",
  manufacturer: "",
  model: "",
  power: "",
  voltage: "",
  notes: "",
});

const tabLabels: Array<[Tab, string]> = [
  ["cadastros", "Cadastros"],
  ["ativos", "Estoque & Ativos"],
  ["orcamento", "Orçamento Aluguel/Venda"],
  ["preventiva", "Orçamento Preventiva"],
  ["relatorios", "Relatórios e O.S."],
];

export function CommercialDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("cadastros");
  const [equipment, setEquipment] = useState<CommercialEquipment[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const endpoint = useMemo(() => `/api/commercial/equipment${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`, [search]);

  async function load() {
    setError("");
    try {
      setEquipment(await apiClient.request<CommercialEquipment[]>(endpoint));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar o Comercial.");
    }
  }

  useEffect(() => { void load(); }, [endpoint]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true); setError(""); setMessage("");
    try {
      const created = await apiClient.post<CommercialEquipment>("/commercial/equipment", {
        ...form,
        manufacturer: form.manufacturer || null,
        model: form.model || null,
        power: form.power || null,
        voltage: form.voltage || null,
        notes: form.notes || null,
      });
      setMessage(`Equipamento cadastrado com a série comercial ${created.serial_code}.`);
      setForm(emptyForm());
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível cadastrar o equipamento.");
    } finally { setSaving(false); }
  }

  async function deactivate(id: number) {
    if (!window.confirm("Inativar este equipamento comercial?")) return;
    await apiClient.delete(`/commercial/equipment/${id}`);
    await load();
  }

  function openLabel(item: CommercialEquipment) {
    window.open(`/api/commercial/equipment/${item.id}/label.pdf`, "_blank", "noopener,noreferrer");
  }

  return <div className="com-layout">
    <aside className="com-sidebar">
      <div className="com-brand">NEXUS · Comercial</div>
      <nav className="com-nav">{tabLabels.map(([value,label]) => <button key={value} className={tab===value?"active":""} onClick={()=>setTab(value)}>{label}</button>)}</nav>
      <div className="com-spacer"/>
      <button className="com-btn" onClick={()=>navigate("/painel")}><ArrowLeft size={16}/> Menu principal</button>
      <button className="com-btn" onClick={onLogout}><LogOut size={16}/> Sair</button>
    </aside>

    <main className="com-main">
      <header className="com-header"><div><p>NEXUS ENTERPRISE</p><h1>Patrimônio e operação comercial</h1><p>Usuário: {user.name} · séries próprias, aluguel, venda e preventiva.</p></div></header>
      <div className="com-tabs">{tabLabels.map(([value,label]) => <button key={value} className={tab===value?"active":""} onClick={()=>setTab(value)}>{label}</button>)}</div>
      {message && <div className="com-notice">{message}</div>}
      {error && <div className="com-notice">{error}</div>}

      {(tab === "cadastros" || tab === "ativos") && <div className="com-grid">
        <section className="com-card">
          <h2><PackagePlus size={19}/> Novo equipamento</h2>
          <form className="com-form" onSubmit={create}>
            <label>Finalidade<select value={form.purpose} onChange={(e)=>setForm({...form,purpose:e.target.value as CommercialPurpose})}><option value="rental_sale">Aluguel / Venda</option><option value="preventive">Preventiva</option></select></label>
            <label>Equipamento<input required value={form.equipment_type} onChange={(e)=>setForm({...form,equipment_type:e.target.value})}/></label>
            <div className="com-form-row"><label>Fabricante<input value={form.manufacturer} onChange={(e)=>setForm({...form,manufacturer:e.target.value})}/></label><label>Modelo<input value={form.model} onChange={(e)=>setForm({...form,model:e.target.value})}/></label></div>
            <div className="com-form-row"><label>Potência/Corrente<input value={form.power} onChange={(e)=>setForm({...form,power:e.target.value})}/></label><label>Tensão<input value={form.voltage} onChange={(e)=>setForm({...form,voltage:e.target.value})}/></label></div>
            <label>Observações<textarea rows={3} value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})}/></label>
            <footer><button className="com-btn primary" disabled={saving}>{saving?"Salvando...":"Cadastrar equipamento"}</button></footer>
          </form>
        </section>

        <section className="com-card">
          <h2>Registros salvos</h2>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}><Search size={17}/><input className="com-search" placeholder="Buscar série, equipamento, fabricante ou modelo" value={search} onChange={(e)=>setSearch(e.target.value)}/></div>
          <div className="com-table-wrap"><table className="com-table"><thead><tr><th>Série</th><th>Equipamento</th><th>Finalidade</th><th>Especificação</th><th>Ações</th></tr></thead><tbody>{equipment.map((item)=><tr key={item.id}><td className="com-serial">{item.serial_code}</td><td><strong>{item.equipment_type}</strong><br/><small>{[item.manufacturer,item.model].filter(Boolean).join(" · ") || "—"}</small></td><td><span className={`com-tag ${item.purpose}`}>{item.purpose === "preventive" ? "Preventiva" : "Aluguel / Venda"}</span></td><td>{[item.power,item.voltage].filter(Boolean).join(" · ") || "—"}</td><td><div className="com-row-actions">{item.purpose === "preventive" && <button className="com-btn" title="Emitir etiqueta" onClick={()=>openLabel(item)}><Printer size={16}/></button>}<button className="com-btn danger" title="Inativar" onClick={()=>void deactivate(item.id)}><Trash2 size={16}/></button></div></td></tr>)}</tbody></table></div>
        </section>
      </div>}

      {tab === "orcamento" && <section className="com-card com-placeholder"><FileText size={28}/><h2>Orçamento de aluguel e venda</h2><p>A base de equipamentos e séries já está ativa. O fluxo de proposta comercial será ligado a estes registros no próximo incremento.</p></section>}
      {tab === "preventiva" && <section className="com-card com-placeholder"><Printer size={28}/><h2>Preventiva</h2><p>Cadastre o equipamento com finalidade Preventiva e emita a etiqueta diretamente na listagem. O orçamento de preventiva será a próxima camada deste módulo.</p></section>}
      {tab === "relatorios" && <section className="com-card com-placeholder"><FileText size={28}/><h2>Relatórios e O.S.</h2><p>Estrutura preparada para consolidar aluguel, venda e preventiva sem duplicar dados do Laboratório.</p></section>}
    </main>
  </div>;
}
