interface Props {
  roomCount: number;
  avgTemp: number | null;
  heatingCount: number;
  mqttConnected: boolean;
  onAdd: () => void;
  onImport: () => void;
}

export function TopBar({ roomCount, avgTemp, heatingCount, mqttConnected, onAdd, onImport }: Props) {
  return (
    <header className="head">
      <div className="h-left">
        <h1>Climate</h1>
        <div className="sub">
          <span className="chip">{roomCount} {roomCount === 1 ? "room" : "rooms"}</span>
          {avgTemp != null && <span className="chip mono">{avgTemp.toFixed(1)}&deg; avg</span>}
          {heatingCount > 0 && (
            <span className="chip"><span className="dot dot-heat" />{heatingCount} calling for heat</span>
          )}
          <span className="chip">
            <span className={"dot " + (mqttConnected ? "dot-ok" : "dot-bad")} />
            {mqttConnected ? "Linked to Home Assistant" : "MQTT offline"}
          </span>
        </div>
        <div className="actions">
          <button className="btn btn-ghost" onClick={onImport}>Import</button>
          <button className="btn btn-primary" onClick={onAdd}>Add room</button>
        </div>
      </div>
      <div className="legend" aria-hidden="true">
        <div className="bar" />
        <div className="scale"><span>14&deg;</span><span>18&deg;</span><span>21&deg;</span><span>24&deg;</span><span>28&deg;</span></div>
      </div>
    </header>
  );
}
