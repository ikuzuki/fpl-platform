import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StepPills } from "./StepPills";

function pillState(container: HTMLElement, label: string): "pending" | "inFlight" | "done" {
  const pill = Array.from(container.querySelectorAll("span[title]")).find(
    (el) => el.textContent?.includes(label),
  );
  if (!pill) throw new Error(`pill "${label}" not rendered`);
  if (pill.querySelector(".animate-spin")) return "inFlight";
  if (pill.querySelector("svg")) return "done";
  return "pending";
}

describe("StepPills", () => {
  it("renders nothing when there are no steps and the stream is idle", () => {
    const { container } = render(<StepPills steps={[]} active={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the current step as inFlight and earlier steps as done while streaming", () => {
    const { container } = render(
      <StepPills steps={["planner", "tool_executor"]} active={true} />,
    );
    expect(pillState(container, "Planning")).toBe("done");
    expect(pillState(container, "Gathering data")).toBe("inFlight");
    expect(pillState(container, "Reviewing")).toBe("pending");
    expect(pillState(container, "Writing report")).toBe("pending");
  });

  it("resets later pills to pending when execution loops back to an earlier step", () => {
    // Regression: the graph can route reflector → planner for another round
    // when it decides more data is needed. The previous renderer used a
    // permanent "seen" set, so Reviewing stayed ✓ while Gathering data was
    // spinning again — confusing to the user. Position-based rendering now
    // un-ticks steps that come after the most recent one.
    const { container } = render(
      <StepPills
        steps={["planner", "tool_executor", "reflector", "planner"]}
        active={true}
      />,
    );
    expect(pillState(container, "Planning")).toBe("inFlight");
    expect(pillState(container, "Gathering data")).toBe("pending");
    expect(pillState(container, "Reviewing")).toBe("pending");
    expect(pillState(container, "Writing report")).toBe("pending");
  });

  it("marks every step done once the stream ends", () => {
    const { container } = render(
      <StepPills
        steps={["planner", "tool_executor", "reflector", "recommender"]}
        active={false}
      />,
    );
    expect(pillState(container, "Planning")).toBe("done");
    expect(pillState(container, "Gathering data")).toBe("done");
    expect(pillState(container, "Reviewing")).toBe("done");
    expect(pillState(container, "Writing report")).toBe("done");
  });
});
