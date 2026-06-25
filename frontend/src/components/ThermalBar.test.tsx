import { render } from "@testing-library/react";
import { ThermalBar, rampColor } from "./ThermalBar";

it("renders the track always, and the current marker when current is set", () => {
  const { container } = render(<ThermalBar current={21} target={22} off={false} />);
  expect(container.querySelector(".therm-track")).toBeInTheDocument();
  expect(container.querySelector(".therm-cur")).toBeInTheDocument();
  expect(container.querySelector(".therm-tgt")).toBeInTheDocument();
});

it("hides the current marker when current is null", () => {
  const { container } = render(<ThermalBar current={null} target={22} off={false} />);
  expect(container.querySelector(".therm-cur")).not.toBeInTheDocument();
});

it("desaturates the track when off", () => {
  const { container } = render(<ThermalBar current={20} target={20} off={true} />);
  expect(container.querySelector(".therm.off")).toBeInTheDocument();
});

it("ramps cold to hot", () => {
  expect(rampColor(5)).toBe("#38bdf8");    // cold
  expect(rampColor(95)).toBe("#fb6a3c");   // hot
});
