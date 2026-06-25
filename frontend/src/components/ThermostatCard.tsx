import { useEffect, useRef, useState } from "react";
import { Dial } from "./Dial";
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
  const cur = s.current_temperature;
  const tgt = pending ?? s.target_temperature;

  function nudge(direction: number) {
    const step = device.temp_step || 0.5;
    const base = pending ?? s.target_temperature ?? device.min_temp;
    let next = Math.round((base + direction * step) / step) * step;
    next = Math.max(device.min_temp, Math.min(device.max_temp, next));
    setPending(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      onSetTemp(device.id, next);
      setPending(null);
    }, 600);
  }

  return (
    <article className="card" data-state={cardState(device)} data-id={device.id}>
      <div className="card-head">
        <h3 className="card-name">{device.name}</h3>
        <button className="icon-btn card-menu" aria-label="Edit thermostat"
                onClick={() => onEdit(device.id)}>&#8230;</button>
      </div>
      <div className="dial">
        <Dial current={cur} target={tgt} min={device.min_temp} max={device.max_temp} />
        <div className="dial-center">
          <div className="readout">
            <span className="readout-num">{cur == null ? "--" : fmt(cur)}</span>
            <span className="readout-unit">&deg;</span>
          </div>
          <div className="readout-label">current</div>
        </div>
      </div>
      <div className="setpoint">
        <button className="step-btn step-down" aria-label="Lower target" onClick={() => nudge(-1)}>&minus;</button>
        <div className="setpoint-value">
          <span className="target-num">{tgt == null ? "--" : fmt(tgt)}</span>
          <span className="target-unit">&deg;C</span>
          <span className="setpoint-label">target</span>
        </div>
        <button className="step-btn step-up" aria-label="Raise target" onClick={() => nudge(+1)}>+</button>
      </div>
      <div className="modes" role="group" aria-label="Mode">
        {device.supported_modes.map((m) => (
          <button key={m} className="mode-opt" data-mode={m}
                  aria-pressed={m === s.hvac_mode}
                  onClick={() => onSetMode(device.id, m)}>{m}</button>
        ))}
      </div>
    </article>
  );
}
