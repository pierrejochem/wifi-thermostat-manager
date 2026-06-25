import { useEffect, useState } from "react";
import { api } from "../api";
import type { HaDevice, HaDevicesResponse } from "../types";

interface Props { onClose: () => void; onImported: () => void; }

export function ImportModal({ onClose, onImported }: Props) {
  const [data, setData] = useState<HaDevicesResponse | null>(null);
  const [status, setStatus] = useState("Loading…");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.haDevices()
      .then((d) => {
        setData(d);
        if (d.devices.length) setStatus(`${d.devices.length} thermostat(s) found.`);
        else if (d.total > 0) {
          const cats = Object.entries(d.seen_categories).map(([c, n]) => `${c}×${n}`).join(", ");
          setStatus(`Found ${d.total} Tuya device(s), but none look like thermostats (categories seen: ${cats}).`);
        } else if (d.homes === 0) {
          setStatus("Connected to Tuya via Home Assistant, but the account returned no homes/devices.");
        } else setStatus("No Tuya devices found in Home Assistant.");
      })
      .catch((e) => { setStatus(""); setError((e as Error).message); });
  }, []);

  function toggle(id: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      on ? next.add(id) : next.delete(id);
      return next;
    });
  }

  function note(d: HaDevice) {
    if (d.already_added) return "already added";
    if (d.battery) return "battery · use HA Tuya";
    return null;
  }

  async function importSelected() {
    setError(null);
    try {
      const res = await api.haImport([...selected]);
      if (res.errors.length) setError(`Imported ${res.imported.length}, ${res.errors.length} failed.`);
      else onClose();
      onImported();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-head">
          <h2>Import from Home Assistant</h2>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>&times;</button>
        </div>
        <p className="ha-hint">Thermostats from your Home Assistant Tuya integration. Pick the ones to add — no Device ID or Local Key needed.</p>
        <p className="ha-status">{status}</p>
        <div className="ha-list">
          {(data?.devices ?? []).map((d) => {
            const blocked = d.already_added || d.battery;
            const tag = note(d);
            return (
              <label key={d.device_id} className={"ha-row" + (blocked ? " ha-added" : "")}>
                <input type="checkbox" value={d.device_id} disabled={blocked}
                       checked={selected.has(d.device_id)}
                       onChange={(e) => toggle(d.device_id, e.target.checked)} />
                <span className={"ha-dot " + (d.online ? "ha-online" : "ha-offline")} />
                <span className="ha-name">{d.name}</span>
                {tag && <span className="ha-tag">{tag}</span>}
              </label>
            );
          })}
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-foot">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={selected.size === 0}
                  onClick={importSelected}>Import selected</button>
        </div>
      </div>
    </div>
  );
}
