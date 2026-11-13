import { useMemo, useState } from "react";
import { MapPinned, Search } from "lucide-react";

type Area = {id:number;name:string;code:string;is_active:boolean};
type Kind = {id:number;name:string;code:string};
type Container = {id:number;area_id:number;type_id:number;name:string;code:string;is_active:boolean};
type Slot = {id:number;container_id:number;code:string;name:string;occupied:boolean;items:Array<{name:string;quantity:number}>;is_active:boolean};

export function InventoryPhysicalMap({map,onLocate}:{map:{areas:Area[];types:Kind[];containers:Container[];slots:Slot[]};onLocate:(code:string)=>void}) {
  const [kind,setKind]=useState<"estante"|"gaveta"|"caixa"|"galeria"|"outros">("estante");
  const kindLabel = (value: string) => ({ estante: "Estantes", gaveta: "Gavetas", caixa: "Caixas", galeria: "Galeias", outros: "Outros" }[value] ?? value);
  const [query,setQuery]=useState("");
  const [page,setPage]=useState(0);
  const kindFor=(c:Container)=>map.types.find(t=>t.id===c.type_id)?.code;
  const records=useMemo(()=>map.containers.filter(c=>c.is_active && (kind==="outros" ? !["estante","gaveta","caixa","galeria","galeia"].includes(kindFor(c)??"") : (kind==="galeria"?["galeria","galeia"].includes(kindFor(c)??""):kindFor(c)===kind)) && (!query.trim()||[c.name,c.code].some(text=>text.toLocaleLowerCase("pt-BR").includes(query.trim().toLocaleLowerCase("pt-BR")))))
   .sort((a,b)=>Number(a.code.match(/^GAVETA-(\d+)$/)?.[1]??0)&&Number(b.code.match(/^GAVETA-(\d+)$/)?.[1]??0)
       ? Number(a.code.match(/(\d+)$/)?.[1])-Number(b.code.match(/(\d+)$/)?.[1])
       : a.name.localeCompare(b.name,"pt-BR",{numeric:true})),[map.containers,map.types,kind,query]);
  const pageCount=Math.max(1,Math.ceil(records.length/40));
  const currentPage=Math.min(page,pageCount-1);
  const visible=records.slice(currentPage*40,(currentPage+1)*40);
  return <section className="inv-map inv-map-v7">
    <header className="inv-map-intro"><div><h2><MapPinned size={20}/> Mapa físico</h2><p>Escolha um tipo de endereço. Clique na posição para localizar os itens armazenados nela.</p></div><span>{records.length} locais</span></header>
    <div className="inv-map-controls"><div className="inv-map-kinds" role="group" aria-label="Tipo de localização">
      {([ "estante", "gaveta", "caixa", "galeria", "outros" ] as const).map((id)=><button key={id} type="button" className={kind===id?"active":""} aria-pressed={kind===id} onClick={()=>{setKind(id);setQuery("");setPage(0);}}>{kindLabel(id)}</button>)}
    </div><label><Search size={16}/><input value={query} placeholder={kind==="gaveta"?"Número da gaveta, ex.: 445":"Buscar endereço"} onChange={e=>{setQuery(e.target.value);setPage(0);}}/></label></div>
    {kind==="estante"&&<p className="inv-map-hint">Cada estante possui cinco posições em coluna, do topo para baixo: A1 até A5, B1 até B5 e assim por diante.</p>}
    <div className={kind==="gaveta"?"inv-map-drawer-grid":"inv-map-shelf-grid"}>
      {visible.map(c=>{const slots=map.slots.filter(s=>s.container_id===c.id&&s.is_active);const units=slots.reduce((sum,s)=>sum+s.items.reduce((n,item)=>n+item.quantity,0),0);
        return <article className={kind==="gaveta"?"inv-map-drawer":"inv-map-shelf"} key={c.id}>
          <header><strong>{c.name}</strong><small>{c.code}</small></header>
          <div className={`inv-map-positions ${kind==="estante"?"vertical":""}`}>{slots.map(slot=><button key={slot.id} type="button" className={slot.occupied?"occupied":"free"} onClick={()=>onLocate(slot.code)} title={slot.items.map(i=>i.name).join(", ")||"Posição vazia"}><b>{kind==="gaveta"?"Ver itens":slot.code}</b><span>{slot.occupied?`${slot.items.reduce((sum,item)=>sum+item.quantity,0)} unidade(s)`:"Livre"}</span></button>)}</div>
          {kind!=="gaveta"&&<small>{units} unidade(s) armazenada(s)</small>}
        </article>})}
    </div>
    {!visible.length&&<div className="inv-empty">Nenhum endereço encontrado. Cadastre-o na aba Endereços.</div>}
    {pageCount>1&&<div className="inv-page-nav"><button disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}>Anterior</button><span>Página {currentPage+1} de {pageCount}</span><button disabled={currentPage>=pageCount-1} onClick={()=>setPage(currentPage+1)}>Próxima</button></div>}
  </section>;
}
