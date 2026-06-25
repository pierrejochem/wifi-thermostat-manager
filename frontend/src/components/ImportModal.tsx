import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { HaDevicesResponse } from "../types";

interface Props { onClose: () => void; onImported: () => void; }

export function ImportModal({ onClose, onImported }: Props) {
  const [data, setData] = useState<HaDevicesResponse | null>(null);
  const [status, setStatus] = useState("Loading…");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.haDevices()
      .then((d) => {
        setData(d);
        if (d.devices.length) setStatus(`${d.devices.length} device(s) found.`);
        else if (d.total > 0) {
          const cats = Object.entries(d.seen_categories).map(([c, n]) => `${c}×${n}`).join(", ");
          setStatus(`Found ${d.total} Tuya device(s), but none look like thermostats (categories seen: ${cats}).`);
        } else if (d.homes === 0) {
          setStatus("Connected to Tuya via Home Assistant, but the account returned no homes/devices.");
        } else setStatus("No Tuya devices found in Home Assistant.");
      })
      .catch((e) => { setStatus(""); setError((e as Error).message); });
  }, []);

  const devices = data?.devices ?? [];
  // Battery devices are importable again; only already-added rows are locked.
  const importable = useMemo(() => devices.filter((d) => !d.already_added), [devices]);
  const allChecked = importable.length > 0 && importable.every((d) => selected.has(d.device_id));
  const someChecked = importable.some((d) => selected.has(d.device_id));

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someChecked && !allChecked;
  }, [someChecked, allChecked]);

  function toggle(id: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(() => (allChecked ? new Set() : new Set(importable.map((d) => d.device_id))));
  }

  async function importSelected() {
    setError(null);
    setBusy(true);
    try {
      const res = await api.haImport([...selected]);
      if (res.errors.length) setError(`Imported ${res.imported.length}, ${res.errors.length} failed.`);
      else onClose();
      onImported();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal modal-wide">
        <div className="modal-head">
          <h2>Import from Home Assistant</h2>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>&times;</button>
        </div>
        <p className="ha-hint">Thermostats from your Home Assistant Tuya integration — no Device ID or Local Key needed.</p>
        <p className="ha-status">{status}</p>

        {devices.length > 0 && (
          <div className="ha-table-wrap">
            <table className="ha-table">
              <thead>
                <tr>
                  <th className="ha-col-check">
                    <input ref={selectAllRef} type="checkbox" aria-label="Select all"
                           checked={allChecked} disabled={importable.length === 0}
                           onChange={toggleAll} />
                  </th>
                  <th>Device</th>
                  <th className="ha-col-status">Status</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => {
                  const locked = d.already_added;
                  return (
                    <tr key={d.device_id} className={selected.has(d.device_id) ? "is-selected" : ""}>
                      <td className="ha-col-check">
                        <input type="checkbox" aria-label={d.name} disabled={locked}
                               checked={selected.has(d.device_id)}
                               onChange={(e) => toggle(d.device_id, e.target.checked)} />
                      </td>
                      <td>
                        <span className="ha-name">{d.name}</span>
                        {d.already_added && <span className="ha-tag">added</span>}
                        {d.battery && <span className="ha-tag ha-tag-battery">battery</span>}
                      </td>
                      <td className="ha-col-status">
                        <span className={"ha-dot " + (d.online ? "ha-online" : "ha-offline")} />
                        <span className="ha-status-label">{d.online ? "Online" : "Offline"}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {error && <p className="form-error">{error}</p>}
        <div className="modal-foot">
          <span className="ha-selcount">{selected.size > 0 ? `${selected.size} selected` : ""}</span>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={selected.size === 0 || busy}
                  onClick={importSelected}>{busy ? "Importing…" : "Import selected"}</button>
        </div>
      </div>
    </div>
  );
}
