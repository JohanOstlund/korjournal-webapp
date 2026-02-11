'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

async function fetchAuth(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(input, { credentials: 'include', ...init, headers });
}

type Template = {
  id: number;
  name: string;
  default_purpose?: string | null;
  business: boolean;
  default_vehicle_reg?: string | null;
  default_driver_name?: string | null;
  default_start_address?: string | null;
  default_end_address?: string | null;
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const [editId, setEditId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [purpose, setPurpose] = useState('');
  const [business, setBusiness] = useState(true);
  const [vehicle, setVehicle] = useState('');
  const [driver, setDriver] = useState('');
  const [startAddr, setStartAddr] = useState('');
  const [endAddr, setEndAddr] = useState('');

  const resetForm = () => {
    setEditId(null); setName(''); setPurpose(''); setBusiness(true);
    setVehicle(''); setDriver(''); setStartAddr(''); setEndAddr('');
  };

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const r = await fetchAuth(`${API}/templates?_ts=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`GET /templates ${r.status}`);
      const data = (await r.json()) as Template[];
      setTemplates(data);
      setStatus(`${data.length} mallar`);
    } catch (e: any) {
      setStatus(`Fel: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTemplates(); }, []);

  const loadIntoForm = (t: Template) => {
    setEditId(t.id);
    setName(t.name || '');
    setPurpose(t.default_purpose || '');
    setBusiness(!!t.business);
    setVehicle(t.default_vehicle_reg || '');
    setDriver(t.default_driver_name || '');
    setStartAddr(t.default_start_address || '');
    setEndAddr(t.default_end_address || '');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const saveTemplate = async () => {
    if (!name.trim()) { alert('Namn krävs.'); return; }
    const payload = {
      name: name.trim(),
      business,
      default_purpose: purpose || null,
      default_vehicle_reg: vehicle || null,
      default_driver_name: driver || null,
      default_start_address: startAddr || null,
      default_end_address: endAddr || null,
    };
    const url = editId ? `${API}/templates/${editId}` : `${API}/templates`;
    const method = editId ? 'PUT' : 'POST';
    const r = await fetchAuth(url, { method, body: JSON.stringify(payload) });
    if (!r.ok) { const txt = await r.text(); alert(`Kunde inte spara: ${txt}`); return; }
    await loadTemplates();
    resetForm();
  };

  const deleteTemplate = async (id: number) => {
    if (!confirm('Ta bort mallen?')) return;
    const r = await fetchAuth(`${API}/templates/${id}`, { method: 'DELETE' });
    if (!r.ok) { const txt = await r.text(); alert(`Kunde inte ta bort: ${txt}`); return; }
    if (editId === id) resetForm();
    await loadTemplates();
  };

  return (
    <div>
      <h1>Mallar</h1>

      {/* Form */}
      <div className="card">
        <div className="card-header">{editId ? 'Redigera mall' : 'Skapa ny mall'}</div>
        <div className="form-grid">
          <div className="field">
            <span className="field-label">Namn</span>
            <input type="text" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Syfte</span>
            <input type="text" value={purpose} onChange={e => setPurpose(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Typ</span>
            <div className="field-row" style={{ minHeight: 44 }}>
              <input type="checkbox" checked={business} onChange={e => setBusiness(e.target.checked)} id="chk-tpl-biz" />
              <label htmlFor="chk-tpl-biz" style={{ fontSize: 15, cursor: 'pointer' }}>Tjänsteresa</label>
            </div>
          </div>
          <div className="field">
            <span className="field-label">Regnr</span>
            <input type="text" value={vehicle} onChange={e => setVehicle(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Förare</span>
            <input type="text" value={driver} onChange={e => setDriver(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Startadress</span>
            <input type="text" value={startAddr} onChange={e => setStartAddr(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Slutadress</span>
            <input type="text" value={endAddr} onChange={e => setEndAddr(e.target.value)} />
          </div>
        </div>
        <div className="btn-group mt-16">
          <button className="btn btn-primary" onClick={saveTemplate}>
            {editId ? 'Spara ändringar' : 'Skapa mall'}
          </button>
          <button className="btn btn-ghost" onClick={resetForm}>Rensa</button>
          {editId && (
            <button className="btn btn-danger" onClick={() => editId && deleteTemplate(editId)}>Ta bort</button>
          )}
        </div>
      </div>

      {/* List */}
      <div className="section">
        <h2>Befintliga mallar <span className="text-light text-sm">({templates.length})</span></h2>
        {loading ? (
          <p className="text-muted">Laddar…</p>
        ) : templates.length === 0 ? (
          <p className="text-muted">Inga mallar ännu.</p>
        ) : (
          <>
            {/* Desktop table */}
            <div className="responsive-table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Namn</th>
                    <th>Typ</th>
                    <th>Syfte</th>
                    <th>Regnr</th>
                    <th>Förare</th>
                    <th>Startadress</th>
                    <th>Slutadress</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map(t => (
                    <tr key={t.id}>
                      <td><strong>{t.name}</strong></td>
                      <td><span className={`badge ${t.business ? 'badge-business' : 'badge-private'}`}>{t.business ? 'Tjänst' : 'Privat'}</span></td>
                      <td>{t.default_purpose || ''}</td>
                      <td>{t.default_vehicle_reg || ''}</td>
                      <td>{t.default_driver_name || ''}</td>
                      <td>{t.default_start_address || ''}</td>
                      <td>{t.default_end_address || ''}</td>
                      <td>
                        <div className="btn-group">
                          <button className="btn btn-ghost btn-sm" onClick={() => loadIntoForm(t)}>Redigera</button>
                          <button className="btn btn-danger btn-sm" onClick={() => deleteTemplate(t.id)}>Ta bort</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="responsive-cards">
              {templates.map(t => (
                <div key={t.id} className="card">
                  <div className="flex-between">
                    <strong>{t.name}</strong>
                    <span className={`badge ${t.business ? 'badge-business' : 'badge-private'}`}>{t.business ? 'Tjänst' : 'Privat'}</span>
                  </div>
                  {t.default_purpose && <div className="text-sm mt-8">{t.default_purpose}</div>}
                  <div className="text-xs text-light mt-8">
                    {[t.default_vehicle_reg, t.default_driver_name].filter(Boolean).join(' · ')}
                    {(t.default_start_address || t.default_end_address) && (
                      <> · {t.default_start_address || '?'} → {t.default_end_address || '?'}</>
                    )}
                  </div>
                  <div className="btn-group mt-12">
                    <button className="btn btn-ghost btn-sm" onClick={() => loadIntoForm(t)}>Redigera</button>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteTemplate(t.id)}>Ta bort</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="status-bar">
        <code>{API}</code> — {status}
      </div>
    </div>
  );
}
