import { useEffect, useMemo, useState } from "react";
import { Building2, Layers3, Pencil, Plus, RefreshCw, Save, X } from "lucide-react";

import { apiClient } from "../../../shared/api/apiClient";
import type {
  CompanyProfile,
  LaboratoryAreaConfig,
  LaboratoryLocationConfig,
  LaboratoryRackConfig,
} from "../types";
import { ActionButton } from "./ActionButton";

type Props = {
  mode: "companies" | "locations";
  companies: CompanyProfile[];
  locationConfig: LaboratoryLocationConfig;
  canManage: boolean;
  onChanged: () => Promise<void>;
};

const blankCompany = () => ({
  company_code: "",
  legal_name: "",
  trade_name: "",
  document: "",
  state_registration: "",
  email: "",
  phone: "",
  address: "",
  city: "",
  state: "",
});

export function ConfigMasterPanel({ mode, companies, locationConfig, canManage, onChanged }: Props) {
  if (mode === "companies") {
    return <CompanyMaster companies={companies} canManage={canManage} onChanged={onChanged} />;
  }
  return <LocationMaster config={locationConfig} canManage={canManage} onChanged={onChanged} />;
}

function CompanyMaster({ companies, canManage, onChanged }: { companies: CompanyProfile[]; canManage: boolean; onChanged: () => Promise<void> }) {
  const [form, setForm] = useState(blankCompany());
  const [editing, setEditing] = useState<CompanyProfile | null>(null);
  const [busy, setBusy] = useState(false);

  function startEdit(item: CompanyProfile) {
    setEditing(item);
    setForm({
      company_code: item.company_code,
      legal_name: item.legal_name,
      trade_name: item.trade_name || "",
      document: item.document || "",
      state_registration: item.state_registration || "",
      email: item.email || "",
      phone: item.phone || "",
      address: item.address || "",
      city: item.city || "",
      state: item.state || "",
    });
  }

  function clear() {
    setEditing(null);
    setForm(blankCompany());
  }

  async function save() {
    if (!form.legal_name.trim()) return;
    setBusy(true);
    try {
      const payload = {
        legal_name: form.legal_name.trim(),
        trade_name: form.trade_name.trim() || null,
        document: form.document.trim() || null,
        state_registration: form.state_registration.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        address: form.address.trim() || null,
        city: form.city.trim() || null,
        state: form.state.trim().toUpperCase() || null,
      };
      if (editing) {
        await apiClient.put(`/laboratory/settings/companies/${editing.id}`, {
          ...payload,
          is_active: editing.is_active,
        });
      } else {
        await apiClient.post("/laboratory/settings/companies", {
          company_code: form.company_code.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, ""),
          ...payload,
        });
      }
      clear();
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function toggle(item: CompanyProfile) {
    setBusy(true);
    try {
      await apiClient.put(`/laboratory/settings/companies/${item.id}`, {
        legal_name: item.legal_name,
        trade_name: item.trade_name,
        document: item.document,
        state_registration: item.state_registration,
        email: item.email,
        phone: item.phone,
        address: item.address,
        city: item.city,
        state: item.state,
        is_active: !item.is_active,
      });
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  return <div className="lab-master-panel">
    {!canManage && <div className="lab-alert">Empresas podem ser consultadas aqui. Alterações são restritas a ADM/Gestão.</div>}
    {canManage && <div className="lab-master-form">
      <div className="lab-grid three">
        {!editing && <label>Código interno<input placeholder="nova_empresa" value={form.company_code} onChange={(e) => setForm({ ...form, company_code: e.target.value })} /></label>}
        <label>Razão social<input value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} /></label>
        <label>Nome fantasia<input value={form.trade_name} onChange={(e) => setForm({ ...form, trade_name: e.target.value })} /></label>
      </div>
      <div className="lab-grid three">
        <label>CNPJ/CPF<input value={form.document} onChange={(e) => setForm({ ...form, document: e.target.value })} /></label>
        <label>Inscrição estadual<input value={form.state_registration} onChange={(e) => setForm({ ...form, state_registration: e.target.value })} /></label>
        <label>E-mail<input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>Telefone<input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
        <label>Endereço<input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></label>
        <label>Cidade<input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></label>
        <label>UF<input maxLength={2} value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} /></label>
      </div>
      <div className="lab-master-actions">
        {editing && <ActionButton variant="secondary" icon={<X size={16}/>} onClick={clear}>Cancelar</ActionButton>}
        <ActionButton loading={busy} icon={editing ? <Save size={16}/> : <Plus size={16}/>} onClick={() => void save()}>{editing ? "Salvar empresa" : "Cadastrar empresa"}</ActionButton>
      </div>
      {!editing && <small className="lab-master-help">O código interno é permanente após o cadastro para preservar vínculos e histórico.</small>}
    </div>}

    <div className="lab-settings-list">
      {companies.map((item) => <article key={item.id} className={!item.is_active ? "inactive" : ""}>
        <div className="lab-avatar"><Building2 size={17}/></div>
        <div className="lab-settings-item-copy">
          <strong>{item.trade_name || item.legal_name}</strong>
          <span>{item.company_code} · {item.document || "Sem documento"}{!item.is_active ? " · inativa" : ""}</span>
          <small>{[item.address, item.city, item.state].filter(Boolean).join(" · ") || "Endereço não informado"}</small>
        </div>
        {canManage && <div className="lab-settings-row-actions">
          <ActionButton variant="secondary" icon={<Pencil size={16}/>} onClick={() => startEdit(item)}>Editar</ActionButton>
          <ActionButton variant={item.is_active ? "danger" : "secondary"} loading={busy} icon={<RefreshCw size={16}/>} onClick={() => void toggle(item)}>{item.is_active ? "Inativar" : "Reativar"}</ActionButton>
        </div>}
      </article>)}
    </div>
  </div>;
}

function LocationMaster({ config, canManage, onChanged }: { config: LaboratoryLocationConfig; canManage: boolean; onChanged: () => Promise<void> }) {
  const [areaForm, setAreaForm] = useState({ code: "", name: "", sort_order: "40", direct_assignment: true });
  const [rackForm, setRackForm] = useState({ area_id: "", code: "", name: "", position_prefix: "", rows: "3", columns: "2", layout_row: "1", layout_column: "1", layout_span: "1", sort_order: "10" });
  const [editingArea, setEditingArea] = useState<LaboratoryAreaConfig | null>(null);
  const [editingRack, setEditingRack] = useState<LaboratoryRackConfig | null>(null);
  const [busy, setBusy] = useState(false);

  const activeAreas = useMemo(() => config.areas.filter((item) => item.is_active), [config]);

  useEffect(() => {
    if (!rackForm.area_id && activeAreas.length) {
      setRackForm((current) => ({ ...current, area_id: String(activeAreas[0].id) }));
    }
  }, [activeAreas, rackForm.area_id]);

  async function saveArea() {
    if (!canManage) return;
    setBusy(true);
    try {
      if (editingArea) {
        await apiClient.put(`/laboratory/settings/areas/${editingArea.id}`, {
          name: areaForm.name.trim(),
          sort_order: Number(areaForm.sort_order) || 0,
          is_active: editingArea.is_active,
        });
      } else {
        await apiClient.post("/laboratory/settings/areas", {
          code: areaForm.code.trim().toUpperCase(),
          name: areaForm.name.trim(),
          sort_order: Number(areaForm.sort_order) || 0,
          direct_assignment: areaForm.direct_assignment,
        });
      }
      setEditingArea(null);
      setAreaForm({ code: "", name: "", sort_order: "40", direct_assignment: true });
      await onChanged();
    } finally { setBusy(false); }
  }

  async function saveRack() {
    if (!canManage) return;
    setBusy(true);
    try {
      if (editingRack) {
        await apiClient.put(`/laboratory/settings/racks/${editingRack.id}`, {
          name: rackForm.name.trim(),
          layout_row: Number(rackForm.layout_row) || 1,
          layout_column: Number(rackForm.layout_column) || 1,
          layout_span: Number(rackForm.layout_span) || 1,
          sort_order: Number(rackForm.sort_order) || 0,
          is_active: editingRack.is_active,
        });
      } else {
        await apiClient.post("/laboratory/settings/racks", {
          area_id: Number(rackForm.area_id),
          code: rackForm.code.trim().toUpperCase(),
          name: rackForm.name.trim(),
          position_prefix: rackForm.position_prefix.trim().toUpperCase(),
          rows: Number(rackForm.rows) || 1,
          columns: Number(rackForm.columns) || 1,
          layout_row: Number(rackForm.layout_row) || 1,
          layout_column: Number(rackForm.layout_column) || 1,
          layout_span: Number(rackForm.layout_span) || 1,
          sort_order: Number(rackForm.sort_order) || 0,
        });
      }
      setEditingRack(null);
      setRackForm((current) => ({ ...current, code: "", name: "", position_prefix: "", rows: "3", columns: "2", layout_row: "1", layout_column: "1", layout_span: "1" }));
      await onChanged();
    } finally { setBusy(false); }
  }


  async function toggleArea(area: LaboratoryAreaConfig) {
    if (!canManage) return;
    setBusy(true);
    try {
      await apiClient.put(`/laboratory/settings/areas/${area.id}`, {
        name: area.name,
        sort_order: area.sort_order,
        is_active: !area.is_active,
      });
      await onChanged();
    } finally { setBusy(false); }
  }

  async function toggleRack(rack: LaboratoryRackConfig) {
    if (!canManage) return;
    setBusy(true);
    try {
      await apiClient.put(`/laboratory/settings/racks/${rack.id}`, {
        name: rack.name,
        layout_row: rack.layout_row,
        layout_column: rack.layout_column,
        layout_span: rack.layout_span,
        sort_order: rack.sort_order,
        is_active: !rack.is_active,
      });
      await onChanged();
    } finally { setBusy(false); }
  }


  return <div className="lab-master-panel">
    {!canManage && <div className="lab-alert">A estrutura física pode ser consultada aqui. Alterações são restritas a ADM/Gestão.</div>}
    {canManage && <div className="lab-master-grid">
      <section className="lab-master-form">
        <h4><Layers3 size={17}/> {editingArea ? "Editar ala" : "Nova ala"}</h4>
        {!editingArea && <label>Código<input maxLength={8} placeholder="NOVO" value={areaForm.code} onChange={(e) => setAreaForm({ ...areaForm, code: e.target.value })}/></label>}
        <label>Nome<input placeholder="Ex.: Pintura" value={areaForm.name} onChange={(e) => setAreaForm({ ...areaForm, name: e.target.value })}/></label>
        <label>Ordem<input type="number" min="0" value={areaForm.sort_order} onChange={(e) => setAreaForm({ ...areaForm, sort_order: e.target.value })}/></label>
        {!editingArea && <label className="lab-master-check"><input type="checkbox" checked={areaForm.direct_assignment} onChange={(e) => setAreaForm({ ...areaForm, direct_assignment: e.target.checked })}/> Permitir equipamentos diretamente nesta ala</label>}
        <div className="lab-master-actions">
          {editingArea && <ActionButton variant="secondary" icon={<X size={16}/>} onClick={() => { setEditingArea(null); setAreaForm({ code:"", name:"", sort_order:"40", direct_assignment:true }); }}>Cancelar</ActionButton>}
          <ActionButton loading={busy} icon={editingArea ? <Save size={16}/> : <Plus size={16}/>} onClick={() => void saveArea()}>{editingArea ? "Salvar ala" : "Criar ala"}</ActionButton>
        </div>
      </section>

      <section className="lab-master-form">
        <h4><Layers3 size={17}/> {editingRack ? "Editar estante" : "Nova estante"}</h4>
        <label>Ala<select disabled={Boolean(editingRack)} value={rackForm.area_id} onChange={(e) => setRackForm({ ...rackForm, area_id: e.target.value })}>{activeAreas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        {!editingRack && <><label>Código<input maxLength={12} placeholder="E7" value={rackForm.code} onChange={(e) => setRackForm({ ...rackForm, code: e.target.value })}/></label><label>Prefixo das posições<input maxLength={4} placeholder="G" value={rackForm.position_prefix} onChange={(e) => setRackForm({ ...rackForm, position_prefix: e.target.value })}/></label></>}
        <label>Nome<input placeholder="Estante 7 - Entrada" value={rackForm.name} onChange={(e) => setRackForm({ ...rackForm, name: e.target.value })}/></label>
        {!editingRack && <div className="lab-grid"><label>Linhas da estante<input type="number" min="1" max="20" value={rackForm.rows} onChange={(e) => setRackForm({ ...rackForm, rows: e.target.value })}/></label><label>Colunas da estante<input type="number" min="1" max="20" value={rackForm.columns} onChange={(e) => setRackForm({ ...rackForm, columns: e.target.value })}/></label></div>}
        <div className="lab-grid three">
          <label>Linha no mapa<input type="number" min="1" max="50" value={rackForm.layout_row} onChange={(e) => setRackForm({ ...rackForm, layout_row: e.target.value })}/></label>
          <label>Coluna no mapa<input type="number" min="1" max="12" value={rackForm.layout_column} onChange={(e) => setRackForm({ ...rackForm, layout_column: e.target.value })}/></label>
          <label>Largura no mapa<input type="number" min="1" max="12" value={rackForm.layout_span} onChange={(e) => setRackForm({ ...rackForm, layout_span: e.target.value })}/></label>
        </div>
        <small className="lab-master-help">A posição visual segue o desenho real da operação. Você pode mudar linha, coluna e largura sem alterar código.</small>
        <label>Ordem<input type="number" min="0" value={rackForm.sort_order} onChange={(e) => setRackForm({ ...rackForm, sort_order: e.target.value })}/></label>
        <div className="lab-master-actions">
          {editingRack && <ActionButton variant="secondary" icon={<X size={16}/>} onClick={() => setEditingRack(null)}>Cancelar</ActionButton>}
          <ActionButton loading={busy} icon={editingRack ? <Save size={16}/> : <Plus size={16}/>} onClick={() => void saveRack()}>{editingRack ? "Salvar estante" : "Criar estante + posições"}</ActionButton>
        </div>
      </section>
    </div>}

    <div className="lab-master-location-tree">
      {config.areas.sort((a,b) => a.sort_order - b.sort_order).map((area) => {
        const racks = config.racks.filter((item) => item.area_id === area.id).sort((a,b) => a.sort_order - b.sort_order);
        const direct = config.locations.filter((item) => item.area_id === area.id && item.rack_id === null);
        return <section key={area.id} className={!area.is_active ? "inactive" : ""}>
          <header><div><strong>{area.name}</strong><span>{area.code}{area.direct_location_code ? ` · acesso direto ${area.direct_location_code}` : ""}{!area.is_active ? " · inativa" : ""}</span></div>{canManage && <div className="lab-settings-row-actions"><ActionButton variant="secondary" icon={<Pencil size={15}/>} onClick={() => { setEditingArea(area); setAreaForm({ code: area.code, name: area.name, sort_order: String(area.sort_order), direct_assignment: Boolean(area.direct_location_code) }); }}>Editar</ActionButton><ActionButton variant={area.is_active ? "danger" : "secondary"} loading={busy} icon={<RefreshCw size={15}/>} onClick={() => void toggleArea(area)}>{area.is_active ? "Inativar" : "Reativar"}</ActionButton></div>}</header>
          {direct.map((item) => <div key={item.id} className="lab-master-direct-location"><span>{item.code}</span><strong>{item.name}</strong></div>)}
          {racks.map((rack) => {
            const locations = config.locations.filter((item) => item.rack_id === rack.id).sort((a,b) => a.sort_order - b.sort_order);
            return <article key={rack.id} className={!rack.is_active ? "inactive" : ""}>
              <div><strong>{rack.name}</strong><span>{rack.code} · {rack.rows}x{rack.columns} · {locations.length} posição(ões) · mapa L{rack.layout_row}/C{rack.layout_column}{rack.layout_span > 1 ? ` · largura ${rack.layout_span}` : ""}</span></div>
              <div className="lab-master-location-chips">{locations.map((item) => <span key={item.id}>{item.code}</span>)}</div>
              {canManage && <div className="lab-settings-row-actions"><ActionButton variant="secondary" icon={<Pencil size={15}/>} onClick={() => { setEditingRack(rack); setRackForm({ area_id:String(rack.area_id), code:rack.code, name:rack.name, position_prefix:rack.position_prefix, rows:String(rack.rows), columns:String(rack.columns), layout_row:String(rack.layout_row), layout_column:String(rack.layout_column), layout_span:String(rack.layout_span), sort_order:String(rack.sort_order) }); }}>Editar</ActionButton><ActionButton variant={rack.is_active ? "danger" : "secondary"} loading={busy} icon={<RefreshCw size={15}/>} onClick={() => void toggleRack(rack)}>{rack.is_active ? "Inativar" : "Reativar"}</ActionButton></div>}
            </article>;
          })}
        </section>;
      })}
    </div>
  </div>;
}
