import { Navigate, Route, Routes } from "react-router-dom";

import type { AuthUser } from "../../features/auth/AuthCard";
import { AuthCard } from "../../features/auth/AuthCard";
import { Dashboard } from "../../features/dashboard/Dashboard";
import { CustomerMaster } from "../../features/customers/CustomerMaster";
import { CommercialDashboard } from "../../features/commercial/CommercialDashboard";
import { FinanceDashboard } from "../../features/finance/FinanceDashboard";
import { PurchasingDashboard } from "../../features/purchasing/PurchasingDashboard";
import { LaboratoryDashboard } from "../../features/laboratory/LaboratoryDashboard";
import { EmployeeDashboard } from "../../features/employees/EmployeeDashboard";
import { ModulePlaceholder } from "../ModulePlaceholder";
import { NotFound } from "../NotFound";
import { ProtectedRoute } from "./ProtectedRoute";
import { PublicRoute } from "./PublicRoute";

type AppRouterProps = {
  user: AuthUser | null;
  onLogin: (user: AuthUser) => void;
  onLogout: () => void;
};

function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  return (
    <main className="page-shell">
      <section className="brand-copy" aria-labelledby="page-title">
        <p className="eyebrow">NEXUS ENTERPRISE</p>
        <h1 id="page-title">Operação conectada, segura e rastreável.</h1>
        <p>ERP para financeiro, laboratório, estoque, compras e comercial.</p>
      </section>
      <AuthCard onLogin={onLogin} />
    </main>
  );
}

export function AppRouter({ user, onLogin, onLogout }: AppRouterProps) {
  const authenticated = Boolean(user);

  return (
    <Routes>
      <Route element={<PublicRoute authenticated={authenticated} />}>
        <Route path="/login" element={<LoginPage onLogin={onLogin} />} />
      </Route>

      <Route element={<ProtectedRoute authenticated={authenticated} />}>
        <Route path="/painel" element={<Dashboard user={user!} onLogout={onLogout} />} />
        <Route path="/clientes/*" element={<CustomerMaster user={user!} onLogout={onLogout} />} />
        <Route path="/financeiro/*" element={<FinanceDashboard user={user!} onLogout={onLogout} />} />
        <Route path="/compras/*" element={<PurchasingDashboard user={user!} onLogout={onLogout} />} />
        <Route path="/laboratorio/*" element={<LaboratoryDashboard user={user!} onLogout={onLogout} />} />
        <Route path="/colaboradores/*" element={<EmployeeDashboard user={user!} onLogout={onLogout} />} />
        <Route path="/estoque/*" element={<ModulePlaceholder />} />
        <Route path="/comercial/*" element={<CommercialDashboard user={user!} onLogout={onLogout} />} />
        <Route path="*" element={<NotFound />} />
      </Route>

      <Route path="/" element={<Navigate to={authenticated ? "/painel" : "/login"} replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
