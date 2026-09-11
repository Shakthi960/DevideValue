import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SelectOrCustom, { CUSTOM } from "./SelectOrCustom";

describe("SelectOrCustom", () => {
  const baseProps = {
    value: "",
    onValueChange: vi.fn(),
    customValue: "",
    onCustomChange: vi.fn(),
    options: ["Samsung", "Apple"],
    placeholder: "Select brand",
    customPlaceholder: "Type your brand",
  };

  it("renders options from the list", () => {
    render(<SelectOrCustom {...baseProps} />);

    expect(screen.getByRole("option", { name: "Samsung" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Apple" })).toBeTruthy();
  });

  it("shows a text input once 'Others' is selected", () => {
    render(
      <SelectOrCustom
        {...baseProps}
        value={CUSTOM}
        customValue="Nothing"
      />
    );

    const input = screen.getByPlaceholderText("Type your brand");
    expect(input).toBeTruthy();

    fireEvent.change(input, { target: { value: "Nothing Phone" } });
    expect(baseProps.onCustomChange).toHaveBeenCalledWith(
      "Nothing Phone"
    );
  });

  it("does not render the custom input for a normal selection", () => {
    render(<SelectOrCustom {...baseProps} value="Samsung" />);

    expect(
      screen.queryByPlaceholderText("Type your brand")
    ).toBeNull();
  });

  it("emits the custom sentinel when 'Others' is chosen", () => {
    render(<SelectOrCustom {...baseProps} />);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: CUSTOM },
    });

    expect(baseProps.onValueChange).toHaveBeenCalledWith(CUSTOM);
  });
});
