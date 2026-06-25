interface Props {
  mqttConnected: boolean;
  onAdd: () => void;
  onImport: () => void;
}

export function TopBar({ mqttConnected, onAdd, onImport }: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <div className="brand-text">
          <h1>Thermostats</h1>
          <p className="subtitle">Every room, one panel</p>
        </div>
      </div>
      <div className="topbar-actions">
        <span className={"pill " + (mqttConnected ? "pill-ok" : "pill-bad")}
              title="Home Assistant link status">
          <span className="dot" />
          <span>{mqttConnected ? "Linked to Home Assistant" : "MQTT offline"}</span>
        </span>
        <button className="btn btn-ghost" onClick={onImport}>Import from Home Assistant</button>
        <button className="btn btn-primary" onClick={onAdd}>Add thermostat</button>
      </div>
    </header>
  );
}
