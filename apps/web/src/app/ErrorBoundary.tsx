import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  failed: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Falha ao renderizar o NEXUS", error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="loading-screen" role="alert">
          <div>
            <h1>Não foi possível abrir o painel.</h1>
            <p>Atualize a página. Se o erro continuar, consulte o console e os logs do frontend.</p>
            <button type="button" onClick={() => window.location.reload()}>
              Tentar novamente
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
