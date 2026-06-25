import { render, screen, act, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { ThermostatCard } from "./ThermostatCard";
import type { Thermostat } from "../types";

function device(over: Partial<Thermostat> = {}): Thermostat {
  return {
    id: "d1", name: "Hall", type: "tuya",
    min_temp: 5, max_temp: 35, temp_step: 0.5,
    supported_modes: ["off", "heat"],
    state: { available: true, current_temperature: 20, target_temperature: 22,
             hvac_mode: "heat", hvac_action: "heating" },
    ...over,
  };
}

it("shows the name and current temperature, and heating state", () => {
  const { container } = render(
    <ThermostatCard device={device()} onSetTemp={vi.fn()} onSetMode={vi.fn()} onEdit={vi.fn()} />
  );
  expect(screen.getByText("Hall")).toBeInTheDocument();
  expect(screen.getByText("20")).toBeInTheDocument();
  expect(container.querySelector(".card")).toHaveAttribute("data-state", "heating");
});

it("debounces the stepper and calls onSetTemp once", () => {
  vi.useFakeTimers();
  const onSetTemp = vi.fn();
  render(<ThermostatCard device={device()} onSetTemp={onSetTemp} onSetMode={vi.fn()} onEdit={vi.fn()} />);
  act(() => { fireEvent.click(screen.getByLabelText("Raise target")); });
  act(() => { fireEvent.click(screen.getByLabelText("Raise target")); });
  act(() => { vi.advanceTimersByTime(700); });
  expect(onSetTemp).toHaveBeenCalledTimes(1);
  expect(onSetTemp).toHaveBeenCalledWith("d1", 23);
  vi.useRealTimers();
});
