// The signature element: a cold->hot temperature spectrum with a current marker
// (colored to its temperature) and a target tick. Places a room on the thermal
// scale at a glance. The visual range is a fixed comfort band, not the device's
// full min/max, so small differences read clearly.
const MIN = 14, MAX = 28;
const STOPS: [number, string][] = [
  [0, "#2563eb"], [20, "#38bdf8"], [40, "#22d3ee"],
  [60, "#a3e635"], [80, "#fbbf24"], [100, "#fb6a3c"],
];

function pct(v: number) {
  return Math.max(0, Math.min(100, ((v - MIN) / (MAX - MIN)) * 100));
}
export function rampColor(p: number) {
  for (let i = 1; i < STOPS.length; i++) {
    if (p <= STOPS[i][0]) return STOPS[i][1];
  }
  return STOPS[STOPS.length - 1][1];
}

interface Props { current: number | null; target: number | null; off: boolean; }

export function ThermalBar({ current, target, off }: Props) {
  const cp = current == null ? null : pct(current);
  const tp = target == null ? null : pct(target);
  const mk = off || cp == null ? "var(--faint)" : rampColor(cp);
  return (
    <div className={"therm" + (off ? " off" : "")}>
      <div className="therm-track" />
      {tp != null && <div className="therm-tgt" style={{ left: `calc(${tp}% - 1.5px)` }} />}
      {cp != null && (
        <div className="therm-cur" data-testid="therm-cur"
             style={{ left: `${cp}%`, ["--mk" as string]: mk }} />
      )}
      {tp != null && target != null && (
        <div className="therm-lab" style={{ left: `${tp}%` }}>{Math.round(target)}&deg;</div>
      )}
    </div>
  );
}
