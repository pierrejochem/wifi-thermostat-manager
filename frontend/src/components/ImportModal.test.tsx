import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ImportModal } from "./ImportModal";
import { api } from "../api";
import type { HaDevice } from "../types";

function dev(over: Partial<HaDevice>): HaDevice {
  return { device_id: "x", name: "X", online: true, already_added: false,
           battery: false, category: "wk", ...over };
}

it("disables battery and already-added rows", async () => {
  vi.spyOn(api, "haDevices").mockResolvedValue({
    devices: [
      dev({ device_id: "a", name: "Mains" }),
      dev({ device_id: "b", name: "TRV", battery: true }),
      dev({ device_id: "c", name: "Old", already_added: true }),
    ],
    seen_categories: { wk: 3 }, total: 3, homes: 1,
  });
  render(<ImportModal onClose={() => {}} onImported={() => {}} />);
  const boxes = await screen.findAllByRole("checkbox");
  // order matches devices: Mains enabled, TRV disabled, Old disabled
  expect(boxes[0]).toBeEnabled();
  expect(boxes[1]).toBeDisabled();
  expect(boxes[2]).toBeDisabled();
  await waitFor(() => expect(screen.getByText("battery · use HA Tuya")).toBeInTheDocument());
});
