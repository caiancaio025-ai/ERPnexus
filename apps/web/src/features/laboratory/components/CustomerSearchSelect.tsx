import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import type { CompanyCode, Customer } from "../types";
import { customerDisplayName, searchCustomers } from "./customerSearch";

type Props = {
  customers: Customer[];
  companyCode: CompanyCode;
  value: string;
  customerName?: string;
  onChange: (customer: Customer) => void;
  required?: boolean;
  disabled?: boolean;
};

/** Seleciona o ID do cadastro existente: digitar serve apenas para filtrar sugestões. */
export function CustomerSearchSelect({ customers, companyCode, value, customerName, onChange, required = false, disabled = false }: Props) {
  const inputId = useId();
  const resultsId = `${inputId}-resultados`;
  const inputRef = useRef<HTMLInputElement>(null);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selected = customers.find((customer) => String(customer.id) === value && customer.company_code === companyCode);
  const displayName = selected ? customerDisplayName(selected) : value ? (customerName ?? "") : "";
  const [search, setSearch] = useState(displayName);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isFiltering, setIsFiltering] = useState(false);
  const matches = useMemo(() => searchCustomers(customers, companyCode, isFiltering ? search : "", value), [customers, companyCode, isFiltering, search, value]);

  useEffect(() => {
    setSearch(displayName);
    setIsFiltering(false);
    setOpen(false);
    setActiveIndex(0);
    inputRef.current?.setCustomValidity("");
  }, [value, companyCode, displayName]);

  useEffect(() => () => { if (blurTimer.current !== null) clearTimeout(blurTimer.current); }, []);

  function cancelBlurTimer() {
    if (blurTimer.current !== null) clearTimeout(blurTimer.current);
    blurTimer.current = null;
  }

  function choose(customer: Customer) {
    cancelBlurTimer();
    onChange(customer);
    setSearch(customerDisplayName(customer));
    setIsFiltering(false);
    setOpen(false);
    setActiveIndex(0);
    inputRef.current?.setCustomValidity("");
  }

  function resetSearch() {
    setSearch(displayName);
    setIsFiltering(false);
    setOpen(false);
    setActiveIndex(0);
    inputRef.current?.setCustomValidity("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") { event.preventDefault(); resetSearch(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((previous) => event.key === "ArrowDown"
        ? Math.min(previous + 1, Math.max(0, matches.length - 1))
        : Math.max(previous - 1, 0));
      return;
    }
    if (event.key === "Enter" && open) {
      event.preventDefault(); // Nunca enviar Nova OS ao pressionar Enter na pesquisa.
      if (matches[activeIndex]) choose(matches[activeIndex]);
    }
  }

  const pendingSelection = isFiltering && search !== displayName;
  return <div className="lab-customer-picker">
    <div className="lab-customer-picker-heading">
      <label htmlFor={inputId}>Cliente{required ? " *" : ""}</label>
      <small id={`${inputId}-ajuda`} className="lab-customer-picker-help">
        {pendingSelection ? "Selecione um cliente da lista para alterar o cadastro da OS." : "Digite parte do nome e escolha uma sugestão."}
      </small>
    </div>
    <div className="lab-customer-picker-field">
      <Search size={17} aria-hidden="true" />
      <input
        ref={inputRef}
        id={inputId}
        type="search"
        required={required}
        disabled={disabled}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open && !disabled}
        aria-controls={resultsId}
        aria-activedescendant={open && matches[activeIndex] ? `${resultsId}-opcao-${matches[activeIndex].id}` : undefined}
        aria-describedby={`${inputId}-ajuda`}
        placeholder="Pesquise pelo nome, fantasia ou CNPJ"
        value={search}
        onFocus={(event) => {
          cancelBlurTimer();
          setOpen(true);
          setIsFiltering(Boolean(displayName));
          event.currentTarget.select();
        }}
        onChange={(event) => {
          const next = event.target.value;
          setSearch(next);
          setIsFiltering(true);
          setOpen(true);
          setActiveIndex(0);
          event.currentTarget.setCustomValidity(next === displayName ? "" : "Escolha um cliente da lista de sugestões.");
        }}
        onKeyDown={onKeyDown}
        onBlur={() => {
          cancelBlurTimer();
          // Permite o clique/toque na opção antes de fechar a lista.
          blurTimer.current = setTimeout(() => resetSearch(), 180);
        }}
      />
      <button type="button" className="lab-customer-picker-toggle" disabled={disabled} aria-label="Exibir clientes" onClick={() => {
        cancelBlurTimer();
        if (open) { resetSearch(); return; }
        setSearch(""); setIsFiltering(false); setActiveIndex(0); setOpen(true); inputRef.current?.focus();
      }}><ChevronDown size={16} /></button>
    </div>
    {open && !disabled && <div className="lab-customer-picker-menu" id={resultsId} role="listbox" aria-label="Clientes encontrados">
      {matches.length === 0 ? <p className="lab-customer-picker-empty">Nenhum cliente encontrado nesta empresa.</p> : matches.map((customer, index) => <button
        key={customer.id}
        id={`${resultsId}-opcao-${customer.id}`}
        type="button"
        role="option"
        aria-selected={value === String(customer.id)}
        className={`lab-customer-picker-option${index === activeIndex ? " is-active" : ""}`}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => choose(customer)}
      >
        <span className="lab-customer-picker-name">{customerDisplayName(customer)}{customer.legal_name !== customerDisplayName(customer) && <small>{customer.legal_name}</small>}</span>
        <span className="lab-customer-picker-extra">{customer.document || ""}{value === String(customer.id) && <Check size={17} aria-label="Selecionado" />}</span>
      </button>)}
    </div>}
  </div>;
}
