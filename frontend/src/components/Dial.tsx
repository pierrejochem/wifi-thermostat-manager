const CX = 100, CY = 100, R = 80;
const START = 225, SWEEP = 270;

function ptOnDial(angle: number) {
  const a = (angle * Math.PI) / 180;
  return { x: CX + R * Math.sin(a), y: CY - R * Math.cos(a) };
}
function arcPath(a0: number, a1: number) {
  const p0 = ptOnDial(a0), p1 = ptOnDial(a1);
  const large = (a1 - a0) % 360 > 180 ? 1 : 0;
  return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
}
function frac(value: number | null, min: number, max: number) {
  if (value == null || max <= min) return 0;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

interface Props { current: number | null; target: number | null; min: number; max: number; }

export function Dial({ current, target, min, max }: Props) {
  const marker = current == null ? null : ptOnDial(START + SWEEP * frac(current, min, max));
  return (
    <svg viewBox="0 0 200 200" className="dial-svg">
      <path className="dial-track" d={arcPath(START, START + SWEEP)} />
      <path
        className="dial-fill"
        d={target == null ? "" : arcPath(START, START + SWEEP * frac(target, min, max))}
      />
      <circle
        className="dial-marker"
        r="5"
        cx={marker?.x.toFixed(2)}
        cy={marker?.y.toFixed(2)}
        style={{ display: marker ? "" : "none" }}
      />
    </svg>
  );
}
