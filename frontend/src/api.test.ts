import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./api";

beforeEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

describe("api", () => {
  it("listThermostats hits the relative endpoint and returns data", async () => {
    const f = mockFetch(200, { thermostats: [], mqtt_connected: true });
    const res = await api.listThermostats();
    expect(f).toHaveBeenCalledWith("api/thermostats", undefined);
    expect(res.mqtt_connected).toBe(true);
  });

  it("addThermostat POSTs JSON", async () => {
    const f = mockFetch(201, { thermostat: { id: "x" } });
    await api.addThermostat({ type: "tuya", name: "X" });
    const [path, opts] = f.mock.calls[0];
    expect(path).toBe("api/thermostats");
    expect((opts as RequestInit).method).toBe("POST");
  });

  it("throws the server error message on non-OK", async () => {
    mockFetch(400, { error: "name and type are required" });
    await expect(api.addThermostat({})).rejects.toThrow("name and type are required");
  });
});
