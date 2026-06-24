export type HvacMode = "off" | "heat" | "auto";

export interface DeviceState {
  available: boolean;
  current_temperature: number | null;
  target_temperature: number | null;
  hvac_mode: HvacMode;
  hvac_action: "off" | "idle" | "heating";
}

export interface Thermostat {
  id: string;
  name: string;
  type: string;
  min_temp: number;
  max_temp: number;
  temp_step: number;
  supported_modes: HvacMode[];
  state: DeviceState;
}

export interface FieldSchema {
  key: string;
  label: string;
  type: "text" | "number" | "select";
  required?: boolean;
  default?: string | number;
  options?: string[];
  placeholder?: string;
}

export interface TypeSchemas {
  schemas: Record<string, { label: string; fields: FieldSchema[] }>;
  common_fields: FieldSchema[];
  supported: string[];
}

export interface HaDevice {
  device_id: string;
  name: string;
  online: boolean;
  already_added: boolean;
  battery: boolean;
  category: string | null;
  local_key?: string;
  address?: string;
}

export interface HaDevicesResponse {
  devices: HaDevice[];
  seen_categories: Record<string, number>;
  total: number;
  homes?: number;
}
