import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows login when unauthenticated", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );
    expect(screen.getByText("AlphaPilot")).toBeInTheDocument();
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });
});
