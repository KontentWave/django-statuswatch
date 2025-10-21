import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { RequireAuth } from "@/app/RequireAuth";

describe("RequireAuth", () => {
  it("simply renders its children (router handles auth)", () => {
    render(
      <RequireAuth>
        <div>Secret Content</div>
      </RequireAuth>
    );

    expect(screen.getByText(/secret content/i)).toBeInTheDocument();
  });
});
