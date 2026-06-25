import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Thermostat, TypeSchemas } from "./types";
import { TopBar } from "./components/TopBar";
import { ThermostatCard } from "./components/ThermostatCard";
import { AddEditModal } from "./components/AddEditModal";
import { ImportModal } from "./components/ImportModal";

export default function App() {
  const [devices, setDevices] = useState<Thermostat[]>([]);
  const [mqtt, setMqtt] = useState(false);
  const [schemas, setSchemas] = useState<TypeSchemas | null>(null);
  const [modal, setModal] = useState<"add" | "import" | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  const refresh = useCallback(async () => {
    try {
      const d = await api.listThermostats();
      setDevices(d.thermostats);
      setMqtt(d.mqtt_connected);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    api.getTypes().then(setSchemas).catch(console.error);
    refresh();
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, [refresh]);

  const { avgTemp, heatingCount } = useMemo(() => {
    const temps = devices
      .map((d) => d.state.current_temperature)
      .filter((t): t is number => t != null);
    return {
      avgTemp: temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null,
      heatingCount: devices.filter((d) => d.state.hvac_action === "heating").length,
    };
  }, [devices]);

  const closeModals = () => { setModal(null); setEditId(null); };
  const openAdd = () => { setEditId(null); setModal("add"); };

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  }, []);

  // A failed command snaps the optimistic value back (refresh) and tells the user.
  const onSetTemp = (id: string, t: number) =>
    api.setTemperature(id, t).catch((e) => { showToast((e as Error).message); refresh(); });
  const onSetMode = (id: string, m: string) =>
    api.setMode(id, m).then(refresh).catch((e) => { showToast((e as Error).message); refresh(); });

  return (
    <>
      <TopBar roomCount={devices.length} avgTemp={avgTemp} heatingCount={heatingCount}
              mqttConnected={mqtt} onAdd={openAdd} onImport={() => setModal("import")} />
      <main>
        {devices.length === 0 ? (
          <section className="empty">
            <div className="bar" aria-hidden="true" />
            <h2>No rooms yet</h2>
            <p>Import your Tuya thermostats from Home Assistant, or add one manually, to start controlling them here.</p>
            <button className="btn btn-primary" onClick={openAdd}>Add room</button>
          </section>
        ) : (
          <section className="grid" aria-live="polite">
            {devices.map((d) => (
              <ThermostatCard key={d.id} device={d}
                onSetTemp={onSetTemp}
                onSetMode={onSetMode}
                onEdit={(id) => { setEditId(id); setModal("add"); }} />
            ))}
          </section>
        )}
      </main>
      {toast && <div className="toast" role="status" aria-live="polite">{toast}</div>}
      {modal === "add" && schemas &&
        <AddEditModal schemas={schemas} editId={editId} onClose={closeModals} onSaved={refresh} />}
      {modal === "import" &&
        <ImportModal onClose={closeModals} onImported={refresh} />}
    </>
  );
}
