'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const fetchAuth = (url: string, options: RequestInit = {}) =>
  fetch(url, { credentials: 'include', ...options });

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

  // Form state
  const [editId, setEditId] = useState<number | null>(null); // null = ny mall
  const [name, setName] = useState('');
  const [purpose, setPurpose] = useState('');
  const [business, setBusiness] = useState(true);
  const [vehicle, setVehicle] = useState('');
  const [driver, setDriver] = useState('');
  const [startAddr, setStartAddr] = useState('');
  const [endAddr, setEndAddr] = useState('');

  const resetForm = () => {
    setEditId(null);
    setName('');
    setPurpose('');
    setBusiness(true);
    setVehicle('');
    setDriver('');
    setStartAddr('');
    setEndAddr('');
  };

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const r = await fetchAuth(`${API}/templates?_ts=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`GET /templates ${r.status}`);
      const data = (await r.json()) as Template[];
      setTemplates(data);
      setStatus(`OK – ${data.length} mallar`);
    } catch (e: any) {
      setStatus(`Fel vid laddning: ${e?.message || e}`);
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
    const r = await fetchAuth(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte spara: ${txt}`);
      return;
    }
    await loadTemplates();
    resetForm();
  };

  const deleteTemplate = async (id: number) => {
    if (!confirm('Ta bort mallen?')) return;
    const r = await fetchAuth(`${API}/templates/${id}`, { method: 'DELETE' });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte ta bort: ${txt}`);
      return;
    }
    if (editId === id) resetForm();
    await loadTemplates();
  };

  return (
    <div>
      <h1>Mallar</h1>

      {/* Formulär */}
      <div style={{ display:'grid', gap:8, gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))' }}>
        <label>
          Namn
          <input value={name} onChange={e=>setName(e.target.value)} />
        </label>
        <label>
          Syfte
          <input value={purpose} onChange={e=>setPurpose(e.target.value)} />
        </label>
        <label style={{ display:'flex', alignItems:'center', gap:8 }}>
          Tjänst
          <input type="checkbox" checked={business} onChange={e=>setBusiness(e.target.checked)} />
        </label>
        <label>
          Regnr
          <input value={vehicle} onChange={e=>setVehicle(e.target.value)} />
        </label>
        <label>
          Förare
          <input value={driver} onChange={e=>setDriver(e.target.value)} />
        </label>
        <label>
          Startadress
          <input value={startAddr} onChange={e=>setStartAddr(e.target.value)} />
        </label>
        <label>
          Slutadress
          <input value={endAddr} onChange={e=>setEndAddr(e.target.value)} />
        </label>
      </div>
      <div style={{ display:'flex', gap:8, marginTop:8 }}>
        <button onClick={saveTemplate}>{editId ? 'Spara ändringar' : 'Skapa mall'}</button>
        <button onClick={resetForm} type="button">Rensa</button>
        {editId && (
          <button onClick={()=> editId && deleteTemplate(editId)} type="button" style={{ color:'#b00020' }}>
            Ta bort
          </button>
        )}
      </div>

      {/* Lista */}
      <h2 style={{ marginTop:24 }}>Befintliga mallar</h2>
      {loading ? (
        <div>Laddar…</div>
      ) : templates.length === 0 ? (
        <div>Inga mallar ännu.</div>
      ) : (
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead>
            <tr>
              <th align="left">Namn</th>
              <th align="left">Typ</th>
              <th align="left">Syfte</th>
              <th align="left">Regnr</th>
              <th align="left">Förare</th>
              <th align="left">Startadress</th>
              <th align="left">Slutadress</th>
              <th align="left">Åtgärd</th>
            </tr>
          </thead>
          <tbody>
            {templates.map(t => (
              <tr key={t.id} style={{ borderTop:'1px solid #eee' }}>
                <td>{t.name}</td>
                <td>{t.business ? 'Tjänst' : 'Privat'}</td>
                <td>{t.default_purpose || ''}</td>
                <td>{t.default_vehicle_reg || ''}</td>
                <td>{t.default_driver_name || ''}</td>
                <td>{t.default_start_address || ''}</td>
                <td>{t.default_end_address || ''}</td>
                <td style={{ display:'flex', gap:8 }}>
                  <button onClick={()=> loadIntoForm(t)}>Redigera</button>
                  <button onClick={()=> deleteTemplate(t.id)} style={{ color:'#b00020' }}>Ta bort</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
        API: <code>{API}</code> — {status}
      </div>
    </div>
  );
}
