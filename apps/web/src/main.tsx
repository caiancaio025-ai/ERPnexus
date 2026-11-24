import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./app/App";
import "./styles.css";
import "./mobile-experience.css";
import "./shared/theme/light-theme.css";
import "./shared/theme/light-semantic-colors.css";
import "./shared/theme/dark-elevated.css";
import "./shared/theme/seasonal.css";
import "./shared/ui/sticky-tables.css";
import { iniciarTema } from "./shared/theme/theme";
import { iniciarTemporadas } from "./shared/theme/seasonal";

iniciarTema();
iniciarTemporadas();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
