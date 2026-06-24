import type {
  HaDevicesResponse, Thermostat, TypeSchemas,
} from "./types";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `Request failed (${res.status})`);
  }
  return data as T;
}

function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  return req<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export const api = {
  getTypes: () => req<TypeSchemas>("api/types"),
  listThermostats: () =>
    req<{ thermostats: Thermostat[]; mqtt_connected: boolean }>("api/thermostats"),
  getThermostatConfig: (id: string) =>
    req<{ config: Record<string, unknown> }>(`api/thermostats/${id}/config`),
  addThermostat: (def: Record<string, unknown>) =>
    send<{ thermostat: Thermostat }>("api/thermostats", "POST", def),
  updateThermostat: (id: string, def: Record<string, unknown>) =>
    send<{ thermostat: Thermostat }>(`api/thermostats/${id}`, "PUT", def),
  deleteThermostat: (id: string) =>
    send<{ deleted: string }>(`api/thermostats/${id}`, "DELETE"),
  setTemperature: (id: string, temperature: number) =>
    send<{ ok: boolean }>(`api/thermostats/${id}/temperature`, "POST", { temperature }),
  setMode: (id: string, mode: string) =>
    send<{ ok: boolean }>(`api/thermostats/${id}/mode`, "POST", { mode }),
  haDevices: () => req<HaDevicesResponse>("api/ha/devices"),
  haImport: (device_ids: string[]) =>
    send<{ imported: unknown[]; skipped: string[]; errors: unknown[] }>(
      "api/ha/import", "POST", { device_ids }
    ),
};
