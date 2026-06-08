import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App";
import { I18nProvider } from "./i18n";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows login when unauthenticated", () => {
    render(
      <BrowserRouter>
        <I18nProvider>
          <App />
        </I18nProvider>
      </BrowserRouter>,
    );
    expect(screen.getByText("AlphaPilot")).toBeInTheDocument();
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });
});
