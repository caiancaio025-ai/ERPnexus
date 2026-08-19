import { Navigate, Outlet } from "react-router-dom";

type PublicRouteProps = {
  authenticated: boolean;
};

export function PublicRoute({ authenticated }: PublicRouteProps) {
  return authenticated ? <Navigate to="/painel" replace /> : <Outlet />;
}
