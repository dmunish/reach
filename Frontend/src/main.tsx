import "./style.css";
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Initialize the React app
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("app");
  if (container) {
    const root = createRoot(container);
    root.render(
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    );
  }
});
