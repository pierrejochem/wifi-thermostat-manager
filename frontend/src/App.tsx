import { useCallback, useEffect, useState } from "react";
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

  const closeModals = () => { setModal(null); setEditId(null); };

  return (
    <>
      <TopBar mqttConnected={mqtt}
              onAdd={() => { setEditId(null); setModal("add"); }}
              onImport={() => setModal("import")} />
      <main>
        {devices.length === 0 ? (
          <section className="empty">
            <div className="empty-dial" aria-hidden="true" />
            <h2>No thermostats yet</h2>
            <p>Add your first WiFi thermostat to start controlling it here and in Home Assistant.</p>
            <button className="btn btn-primary" onClick={() => { setEditId(null); setModal("add"); }}>Add thermostat</button>
          </section>
        ) : (
          <section className="grid" aria-live="polite">
            {devices.map((d) => (
              <ThermostatCard key={d.id} device={d}
                onSetTemp={(id, t) => api.setTemperature(id, t).catch(console.error)}
                onSetMode={(id, m) => api.setMode(id, m).then(refresh).catch(console.error)}
                onEdit={(id) => { setEditId(id); setModal("add"); }} />
            ))}
          </section>
        )}
      </main>
      {modal === "add" && schemas &&
        <AddEditModal schemas={schemas} editId={editId} onClose={closeModals} onSaved={refresh} />}
      {modal === "import" &&
        <ImportModal onClose={closeModals} onImported={refresh} />}
    </>
  );
}
