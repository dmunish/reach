import "./style.css";
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

// Initialize the React app
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("app");
  if (container) {
    const root = createRoot(container);
    root.render(React.createElement(App));
  }
});
