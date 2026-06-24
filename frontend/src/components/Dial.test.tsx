import { render } from "@testing-library/react";
import { Dial } from "./Dial";

it("renders the track always and the fill when a target is set", () => {
  const { container } = render(<Dial current={20} target={22} min={5} max={35} />);
  expect(container.querySelector(".dial-track")).toBeInTheDocument();
  const fill = container.querySelector(".dial-fill") as SVGPathElement;
  expect(fill.getAttribute("d")).not.toBe("");
});

it("hides the marker when current is null", () => {
  const { container } = render(<Dial current={null} target={22} min={5} max={35} />);
  const marker = container.querySelector(".dial-marker") as SVGCircleElement;
  expect(marker).toHaveStyle({ display: "none" });
});
