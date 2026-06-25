import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { ImportModal } from "./ImportModal";
import { api } from "../api";
import type { HaDevice } from "../types";

function dev(over: Partial<HaDevice>): HaDevice {
  return { device_id: "x", name: "X", online: true, already_added: false,
           battery: false, category: "wk", ...over };
}

function mockDevices() {
  vi.spyOn(api, "haDevices").mockResolvedValue({
    devices: [
      dev({ device_id: "a", name: "Mains" }),
      dev({ device_id: "b", name: "TRV", battery: true }),
      dev({ device_id: "c", name: "Old", already_added: true }),
    ],
    seen_categories: { wk: 3 }, total: 3, homes: 1,
  });
}

it("allows selecting battery devices; only already-added rows are locked", async () => {
  mockDevices();
  render(<ImportModal onClose={() => {}} onImported={() => {}} />);
  // Battery device is now selectable; already-added is disabled.
  expect(await screen.findByLabelText("TRV")).toBeEnabled();
  expect(screen.getByLabelText("Mains")).toBeEnabled();
  expect(screen.getByLabelText("Old")).toBeDisabled();
  // Battery badge still shown for information.
  await waitFor(() => expect(screen.getByText("battery")).toBeInTheDocument());
});

it("select-all checks every importable device (not already-added)", async () => {
  mockDevices();
  render(<ImportModal onClose={() => {}} onImported={() => {}} />);
  const selectAll = await screen.findByLabelText("Select all");
  fireEvent.click(selectAll);
  expect((screen.getByLabelText("Mains") as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("TRV") as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("Old") as HTMLInputElement).checked).toBe(false);
  // Toggling again clears them.
  fireEvent.click(selectAll);
  expect((screen.getByLabelText("Mains") as HTMLInputElement).checked).toBe(false);
});

it("imports the selected devices via the API", async () => {
  mockDevices();
  const haImport = vi.spyOn(api, "haImport").mockResolvedValue({ imported: [], skipped: [], errors: [] });
  render(<ImportModal onClose={() => {}} onImported={() => {}} />);
  fireEvent.click(await screen.findByLabelText("TRV"));
  fireEvent.click(screen.getByRole("button", { name: /import selected/i }));
  await waitFor(() => expect(haImport).toHaveBeenCalledWith(["b"]));
});
