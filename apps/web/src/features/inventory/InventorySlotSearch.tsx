import { useId, useMemo, useRef, useState } from "react";
import { Check, MapPin, Search, X } from "lucide-react";

export type SearchableSlot = {
  id: number;
  code: string;
  name: string;
  container_id: number;
  is_active: boolean;
  occupied: boolean;
};
export type SearchableContainer = {
  id: number;
  area_id: number;
  type_id: number;
  code: string;
  name: string;
  is_active: boolean;
};
export type SearchableArea = { id: number; code: string; name: string };
export type SearchableKind = { id: number; name: string };

type Props = {
  value: string;
  onChange: (id: string) => void;
  slots: SearchableSlot[];
  containers: SearchableContainer[];
  areas: SearchableArea[];
  types: SearchableKind[];
  disabled?: boolean;
};

const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");

/** Pesquisa a localização física existente; mantém o slot_id esperado pela API. */
export function InventorySlotSearch({ value, onChange, slots, containers, areas, types, disabled }: Props) {
  const listId = useId();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const selected = slots.find((slot) => String(slot.id) === value);
  const [query, setQuery] = useState(selected ? `${selected.code} · ${selected.name}` : "");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const details = useMemo(() => {
    const containerById = new Map(containers.map((container) => [container.id, container]));
    const areaById = new Map(areas.map((area) => [area.id, area]));
    const typeById = new Map(types.map((type) => [type.id, type]));
    return slots.filter((slot) => slot.is_active && containerById.get(slot.container_id)?.is_active).map((slot) => {
      const container = containerById.get(slot.container_id)!;
      const area = areaById.get(container.area_id);
      const kind = typeById.get(container.type_id);
      const location = [kind?.name, container.name, area?.name].filter(Boolean).join(" · ");
      return { slot, location, searchable: normalize([slot.code, slot.name, container.code, container.name, area?.code, area?.name, kind?.name].join(" ")) };
    });
  }, [slots, containers, areas, types]);
  const matches = useMemo(() => {
    const term = normalize(query.trim());
    const results = details.filter((entry) => !term || entry.searchable.includes(term));
    return results.sort((a, b) => a.slot.code.localeCompare(b.slot.code, "pt-BR", { numeric: true })).slice(0, 35);
  }, [details, query]);
  const choose = (id: string) => {
    const slot = slots.find((entry) => String(entry.id) === id);
    onChange(id);
    setQuery(slot ? `${slot.code} · ${slot.name}` : "");
    setOpen(false);
    setActiveIndex(0);
  };
  const visible = open && !disabled;

  return (
    <div className="inv-slot-search" ref={wrapperRef} onBlur={(event) => {
      if (!wrapperRef.current?.contains(event.relatedTarget as Node | null)) {
        setOpen(false);
        // Não deixa texto sem correspondência parecer uma seleção salva.
        if (value && query !== `${selected?.code} · ${selected?.name}`) {
          const slot = slots.find((entry) => String(entry.id) === value);
          setQuery(slot ? `${slot.code} · ${slot.name}` : "");
        }
      }
    }}>
      <label htmlFor={`${listId}-input`}>Posição física</label>
      <div className="inv-slot-search__field">
        <Search size={18} aria-hidden="true" />
        <input
          id={`${listId}-input`}
          type="search"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={`${listId}-options`}
          aria-expanded={visible}
          aria-activedescendant={visible && matches.length ? `${listId}-option-${Math.min(activeIndex, matches.length - 1)}` : undefined}
          placeholder="Buscar estante, gaveta, código, caixa..."
          autoComplete="off"
          value={query}
          disabled={disabled}
          onFocus={(event) => { event.currentTarget.select(); setOpen(true); setActiveIndex(0); }}
          onChange={(event) => { setQuery(event.target.value); onChange(""); setOpen(true); setActiveIndex(0); }}
          onKeyDown={(event) => {
            if (event.key === "Escape") { setOpen(false); return; }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault(); setOpen(true);
              setActiveIndex((index) => Math.max(0, Math.min(matches.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
            }
            if (event.key === "Enter" && visible && matches.length) {
              event.preventDefault(); choose(String(matches[Math.min(activeIndex, matches.length - 1)].slot.id));
            }
          }}
        />
        {(query || value) && <button type="button" className="inv-slot-search__clear" onClick={() => { choose(""); setOpen(true); }} aria-label="Limpar localização"><X size={16} /></button>}
      </div>
      {value && <small className="inv-slot-search__selected"><Check size={14} /> Localização selecionada: {selected?.code ?? "indisponível"}</small>}
      {visible && <div className="inv-slot-search__results" id={`${listId}-options`} role="listbox" aria-label="Localizações encontradas">
        <button type="button" className="inv-slot-search__none" role="option" aria-selected={!value} onMouseDown={(event) => event.preventDefault()} onClick={() => choose("")}>Sem localização</button>
        {matches.map(({ slot, location }, index) => <button
          key={slot.id} type="button" role="option" id={`${listId}-option-${index}`}
          aria-selected={value === String(slot.id)} className={index === activeIndex ? "is-active" : ""}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => choose(String(slot.id))}
        ><MapPin size={16} /><span><strong>{slot.code} · {slot.name}</strong><small>{location}</small></span>{slot.occupied && <em>Em uso</em>}</button>)}
        {matches.length === 0 && <p role="status">Nenhuma posição encontrada para “{query}”.</p>}
        {details.length > 35 && !query && <p>Digite um código ou nome para refinar a busca.</p>}
      </div>}
    </div>
  );
}
