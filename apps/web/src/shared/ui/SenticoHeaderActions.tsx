import { LogOut, UserRound } from "lucide-react";
import type { AuthUser } from "../../features/auth/AuthCard";
import { AppearanceMenu } from "../theme/AppearanceMenu";
import "./sentico-header-actions.css";

type Props = { user: AuthUser; onLogout: () => void };

export function SenticoHeaderActions({ user, onLogout }: Props) {
  return <div className="sentico-header-actions" role="group" aria-label="Aparência e sessão do usuário">
    <AppearanceMenu />
    <span className="sentico-header-user" title={user.name}>
      <UserRound size={17} aria-hidden="true" />
      <span className="sentico-header-user__name">{user.name}</span>
    </span>
    <button type="button" className="sentico-header-logout" onClick={onLogout} aria-label="Sair do sistema">
      <LogOut size={17} aria-hidden="true" /><span>Sair</span>
    </button>
  </div>;
}
