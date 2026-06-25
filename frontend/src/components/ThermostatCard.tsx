import { useEffect, useRef, useState } from "react";
import { ThermalBar } from "./ThermalBar";
import type { Thermostat } from "../types";

function fmt(n: number) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
function cardState(d: Thermostat) {
  const s = d.state;
  if (!s.available) return "unavailable";
  if (s.hvac_action === "heating") return "heating";
  if (s.hvac_mode === "off") return "off";
  return "idle";
}
const STATE_LABEL: Record<string, string> = {
  heating: "Heating", idle: "Idle", off: "Off", unavailable: "Unavailable",
};

interface Props {
  device: Thermostat;
  onSetTemp: (id: string, t: number) => void;
  onSetMode: (id: string, m: string) => void;
  onEdit: (id: string) => void;
}

export function ThermostatCard({ device, onSetTemp, onSetMode, onEdit }: Props) {
  const [pending, setPending] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);

  const s = device.state;

  // Hold the optimistic target until the backend reports it (or give up after a
  // while), so it doesn't flicker back to the old value while the cloud catches up.
  useEffect(() => {
    if (pending == null) return;
    if (s.target_temperature === pending) { setPending(null); return; }
    const t = setTimeout(() => setPending(null), 8000);
    return () => clearTimeout(t);
  }, [pending, s.target_temperature]);

  const cur = s.current_temperature;
  const tgt = pending ?? s.target_temperature;
  const state = cardState(device);
  const stateClass = state === "heating" ? "s-heat" : state === "idle" ? "s-idle" : "";

  function nudge(direction: number) {
    const step = device.temp_step || 0.5;
    const base = pending ?? s.target_temperature ?? device.min_temp;
    let next = Math.round((base + direction * step) / step) * step;
    next = Math.max(device.min_temp, Math.min(device.max_temp, next));
    setPending(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      onSetTemp(device.id, next);   // pending stays until the backend confirms it
    }, 600);
  }

  return (
    <article className="tile" data-state={state} data-id={device.id}>
      <div className="tile-head">
        <h3 className="tile-name">{device.name}</h3>
        <button className="icon-btn tile-menu" aria-label="Edit thermostat"
                onClick={() => onEdit(device.id)}>&#8230;</button>
      </div>
      <div className={"tile-state " + stateClass}>{STATE_LABEL[state]}</div>

      <div className="tile-temp">
        <span className="tile-temp-v mono">{cur == null ? "--" : fmt(cur)}</span>
        <span className="tile-temp-u">&deg;C</span>
      </div>
      <div className="tile-cap">Current</div>

      <ThermalBar current={cur} target={tgt} off={state === "off" || state === "unavailable"} />

      <div className="tile-ctl">
        <div className="setpoint">
          <button className="step-btn step-down" aria-label="Lower target" onClick={() => nudge(-1)}>&minus;</button>
          <span className="target-num mono">{tgt == null ? "--" : fmt(tgt)}&deg;</span>
          <button className="step-btn step-up" aria-label="Raise target" onClick={() => nudge(+1)}>+</button>
        </div>
        <div className="modes" role="group" aria-label="Mode">
          {device.supported_modes.map((m) => (
            <button key={m} className="mode-opt" data-mode={m}
                    aria-pressed={m === s.hvac_mode}
                    onClick={() => onSetMode(device.id, m)}>{m}</button>
          ))}
        </div>
      </div>
    </article>
  );
}
