import { useEffect, useState } from "react";
import { api } from "../api";
import type { FieldSchema, TypeSchemas } from "../types";

interface Props {
  schemas: TypeSchemas;
  editId: string | null;          // null = add mode
  onClose: () => void;
  onSaved: () => void;
}

export function AddEditModal({ schemas, editId, onClose, onSaved }: Props) {
  const types = Object.keys(schemas.schemas);
  const [type, setType] = useState(types[0] ?? "");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (editId) {
      api.getThermostatConfig(editId).then((d) => {
        const cfg = d.config as Record<string, unknown>;
        setType(String(cfg.type ?? types[0]));
        const v: Record<string, string> = {};
        Object.entries(cfg).forEach(([k, val]) => (v[k] = val == null ? "" : String(val)));
        setValues(v);
      });
    }
  }, [editId]); // eslint-disable-line react-hooks/exhaustive-deps

  const fields: FieldSchema[] = [
    ...(schemas.schemas[type]?.fields ?? []),
    ...schemas.common_fields,
  ];

  function set(key: string, val: string) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  async function save() {
    setError(null);
    const def: Record<string, unknown> = { type };
    fields.forEach((f) => {
      const raw = (values[f.key] ?? (f.default != null ? String(f.default) : "")).trim();
      if (raw === "") return;
      def[f.key] = f.type === "number" ? Number(raw) : raw;
    });
    try {
      if (editId) await api.updateThermostat(editId, def);
      else await api.addThermostat(def);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!editId) return;
    if (!confirm("Remove this thermostat? It will also disappear from Home Assistant.")) return;
    try {
      await api.deleteThermostat(editId);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-head">
          <h2>{editId ? "Edit thermostat" : "Add thermostat"}</h2>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>&times;</button>
        </div>
        <div className="field">
          <label htmlFor="type-select">Device type</label>
          <select id="type-select" value={type} disabled={!!editId}
                  onChange={(e) => setType(e.target.value)}>
            {types.map((t) => <option key={t} value={t}>{schemas.schemas[t].label}</option>)}
          </select>
        </div>
        <form className="form-fields" onSubmit={(e) => e.preventDefault()}>
          {fields.map((f) => (
            <div className="field" key={f.key}>
              <label htmlFor={`f_${f.key}`}>{f.label}{f.required ? " *" : ""}</label>
              {f.type === "select" ? (
                <select id={`f_${f.key}`} value={values[f.key] ?? String(f.default ?? "")}
                        onChange={(e) => set(f.key, e.target.value)}>
                  {f.options!.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input id={`f_${f.key}`} type={f.type === "number" ? "number" : "text"}
                       step={f.type === "number" ? "any" : undefined}
                       placeholder={f.placeholder}
                       value={values[f.key] ?? (f.default != null ? String(f.default) : "")}
                       onChange={(e) => set(f.key, e.target.value)} />
              )}
            </div>
          ))}
        </form>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-foot">
          {editId && <button className="btn btn-ghost danger" onClick={remove}>Remove</button>}
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save</button>
        </div>
      </div>
    </div>
  );
}
