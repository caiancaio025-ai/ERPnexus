import { useState } from "react";
import {
  Boxes, Building2, ChevronLeft, ChevronRight, FlaskConical, Handshake,
  LayoutDashboard, LogOut, Menu, ShoppingCart, UsersRound, WalletCards, X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import type { AuthUser } from "../../features/auth/AuthCard";
import { SenticoMark } from "./SenticoMark";
import "./sentico-sidebar.css";

export type SenticoSidebarItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  active?: boolean;
  onClick: () => void;
};

type Props = {
  user: AuthUser;
  onLogout: () => void;
  sectionLabel?: string;
  sectionItems?: SenticoSidebarItem[];
};

const STORAGE_KEY = "sentico:sidebar:collapsed";

const moduleLinks = [
  { label: "Painel", icon: LayoutDashboard, path: "/painel" },
  { label: "Financeiro", icon: WalletCards, path: "/financeiro" },
  { label: "Laboratório", icon: FlaskConical, path: "/laboratorio" },
  { label: "Clientes", icon: Building2, path: "/clientes" },
  { label: "Colaboradores", icon: UsersRound, path: "/colaboradores" },
  { label: "Estoque", icon: Boxes, path: "/estoque" },
  { label: "Compras", icon: ShoppingCart, path: "/compras" },
  { label: "Comercial", icon: Handshake, path: "/comercial" },
];

function storedCollapseState() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function userInitials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "S";
}

/** Um único menu, com a mesma posição, dimensões, ícones e recolhimento em todos os módulos. */
export function SenticoSidebar({ user, onLogout, sectionLabel, sectionItems = [] }: Props) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(storedCollapseState);
  const [mobileOpen, setMobileOpen] = useState(false);

  function toggleCollapse() {
    setCollapsed((current) => {
      const next = !current;
      try { window.localStorage.setItem(STORAGE_KEY, String(next)); } catch { /* Navegação funciona sem armazenamento. */ }
      return next;
    });
  }

  function visit(path: string) {
    setMobileOpen(false);
    navigate(path);
  }

  function runAction(action: () => void) {
    setMobileOpen(false);
    action();
  }

  return (
    <>
      <button
        type="button"
        className="sentico-mobile-menu"
        aria-label={mobileOpen ? "Fechar menu lateral" : "Abrir menu lateral"}
        aria-expanded={mobileOpen}
        aria-controls="sentico-menu-global"
        onClick={() => setMobileOpen((current) => !current)}
      >
        {mobileOpen ? <X size={22} /> : <Menu size={22} />}
      </button>
      {mobileOpen && <button className="sentico-sidebar-backdrop" type="button" aria-label="Fechar menu" onClick={() => setMobileOpen(false)} />}
      <aside
        id="sentico-menu-global"
        className={`sentico-sidebar ${collapsed ? "sentico-sidebar--collapsed" : ""} ${mobileOpen ? "sentico-sidebar--mobile-open" : ""}`}
        aria-label="Menu lateral SÊNTICO"
      >
        <header className="sentico-sidebar__header">
          <button type="button" className="sentico-sidebar__logo" onClick={() => visit("/painel")} aria-label="Ir para o painel SÊNTICO" title="SÊNTICO ERP">
            <SenticoMark compact={collapsed && !mobileOpen} />
          </button>
          <button type="button" className="sentico-sidebar__collapse" onClick={toggleCollapse} title={collapsed ? "Expandir menu" : "Recolher menu"} aria-label={collapsed ? "Expandir menu lateral" : "Recolher menu lateral"}>
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </header>

        <div className="sentico-sidebar__scroll">
          <p className="sentico-sidebar__section-heading">Módulos</p>
          <nav className="sentico-sidebar__nav" aria-label="Navegação principal">
            {moduleLinks
              .filter(({ path }) => path !== "/financeiro" || ["gestao", "super_admin"].includes(user.role))
              .map(({ label, path, icon: Icon }) => (
                <button
                  key={path}
                  type="button"
                  className={`sentico-sidebar__item ${pathname === path || pathname.startsWith(`${path}/`) ? "is-active" : ""}`}
                  aria-current={pathname === path || pathname.startsWith(`${path}/`) ? "page" : undefined}
                  title={label}
                  onClick={() => visit(path)}
                >
                  <Icon size={19} strokeWidth={1.9} aria-hidden="true" />
                  <span>{label}</span>
                </button>
              ))}
          </nav>

          {sectionItems.length > 0 && (
            <>
              <p className="sentico-sidebar__section-heading sentico-sidebar__section-heading--module">{sectionLabel ?? "Neste módulo"}</p>
              <nav className="sentico-sidebar__nav" aria-label={`Seções de ${sectionLabel ?? "módulo"}`}>
                {sectionItems.map(({ id, label, icon: Icon, active, onClick }) => (
                  <button
                    key={id}
                    type="button"
                    className={`sentico-sidebar__item sentico-sidebar__item--sub ${active ? "is-active" : ""}`}
                    aria-current={active ? "location" : undefined}
                    title={label}
                    onClick={() => runAction(onClick)}
                  >
                    <Icon size={18} strokeWidth={1.85} aria-hidden="true" />
                    <span>{label}</span>
                  </button>
                ))}
              </nav>
            </>
          )}
        </div>

        <footer className="sentico-sidebar__footer">
          <div className="sentico-sidebar__profile" title={`${user.name} · ${user.role}`}>
            <span className="sentico-sidebar__avatar">{userInitials(user.name)}</span>
            <div className="sentico-sidebar__profile-text"><strong>{user.name}</strong><small>{user.role}</small></div>
          </div>
          <button className="sentico-sidebar__item sentico-sidebar__logout" type="button" onClick={() => runAction(onLogout)} title="Sair do sistema" aria-label="Sair do sistema">
            <LogOut size={19} aria-hidden="true" /><span>Sair do sistema</span>
          </button>
        </footer>
      </aside>
    </>
  );
}
