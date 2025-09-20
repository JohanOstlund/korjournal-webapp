'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

type Trip = {
  id: number;
  vehicle_reg: string;
  started_at: string;
  ended_at: string;
  distance_km?: number;
  purpose?: string;
  business: boolean;
};

type Template = {
  id: number;
  name: string;
  default_purpose?: string;
  business: boolean;
  default_distance_km?: number;
  start_place?: string;
  end_place?: string;
};

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [vehicle, setVehicle] = useState('ABC123');
  const [form, setForm] = useState({
    vehicle_reg: 'ABC123',
    started_at: '',
    ended_at: '',
    purpose: 'Kundbesök',
    business: true,
    distance_km: '',
  });
  const [editId, setEditId] = useState<number | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<number | 'new' | ''>('');

  const loadTrips = async () => {
    const url = vehicle ? `${API}/trips?vehicle=${encodeURIComponent(vehicle)}` : `${API}/trips`;
    const r = await fetch(url);
    setTrips(await r.json());
  };

  const loadTemplates = async () => {
    const r = await fetch(`${API}/templates`);
    setTemplates(await r.json());
  };

  useEffect(() => { loadTrips(); }, [vehicle]);
  useEffect(() => { loadTemplates(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Om en template är vald och inget edit-id: använd /templates/{id}/apply
    if (!editId && selectedTemplate && selectedTemplate !== 'new') {
      const payload = {
        vehicle_reg: form.vehicle_reg,
        started_at: new Date(form.started_at).toISOString(),
        ended_at: new Date(form.ended_at).toISOString(),
        purpose: form.purpose || undefined,
        business: form.business,
        distance_km: form.distance_km ? parseFloat(form.distance_km) : undefined,
      };
      const res = await fetch(`${API}/templates/${selectedTemplate}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const t = await res.text();
        alert(`Fel: ${res.status} ${t}`);
        return;
      }
      setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
      setSelectedTemplate('');
      await loadTrips();
      return;
    }

    // Annars vanlig trip POST/PUT
    const payload: any = {
      vehicle_reg: form.vehicle_reg,
      started_at: new Date(form.started_at).toISOString(),
      ended_at: new Date(form.ended_at).toISOString(),
      purpose: form.purpose,
      business: form.business,
    };
    if (form.distance_km) payload.distance_km = parseFloat(form.distance_km);

    const method = editId ? 'PUT' : 'POST';
    const endpoint = editId ? `${API}/trips/${editId}` : `${API}/trips`;

    const res = await fetch(endpoint, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) {
      const t = await res.text();
      alert(`Fel: ${res.status} ${t}`);
      return;
    }
    setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
    setEditId(null);
    await loadTrips();
  };

  const edit = (t: Trip) => {
    setEditId(t.id);
    setSelectedTemplate('');
    setForm({
      vehicle_reg: t.vehicle_reg,
      started_at: t.started_at.slice(0,16),
      ended_at: t.ended_at.slice(0,16),
      purpose: t.purpose || '',
      business: t.business,
      distance_km: t.distance_km?.toString() || '',
    });
  };

  const remove = async (id: number) => {
    if (!confirm('Radera resa?')) return;
    await fetch(`${API}/trips/${id}`, { method: 'DELETE' });
    await loadTrips();
  };

  const exportCsv = () => window.open(`${API}/exports/journal.csv?vehicle=${vehicle}`, '_blank');
  const exportPdf = () => window.open(`${API}/exports/journal.pdf?vehicle=${vehicle}`, '_blank');

  const onPickTemplate = (val: string) => {
    if (!val) { setSelectedTemplate(''); return; }
    if (val === 'new') {
      setSelectedTemplate('new');
      return;
    }
    const id = parseInt(val, 10);
    setSelectedTemplate(id);
    const t = templates.find(x => x.id === id);
    if (t) {
      setForm(f => ({
        ...f,
        purpose: t.default_purpose || f.purpose,
        business: t.business,
        distance_km: t.default_distance_km?.toString() || f.distance_km,
      }));
    }
  };

  const createTemplate = async () => {
    const name = prompt('Namn på mall (ex: "Pendling Järfälla → Norrtälje")?');
    if (!name) return;
    const body = {
      name,
      default_purpose: form.purpose || 'Pendling',
      business: form.business,
      default_distance_km: form.distance_km ? parseFloat(form.distance_km) : undefined,
      start_place: undefined,
      end_place: undefined,
    };
    const r = await fetch(`${API}/templates`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    if (!r.ok) {
      alert(await r.text());
      return;
    }
    await loadTemplates();
    setSelectedTemplate('');
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}>
        <label>
          Fordon
          <input value={vehicle} onChange={e=>{ setVehicle(e.target.value); setForm(f=>({...f, vehicle_reg: e.target.value})); }} />
        </label>
        <button onClick={exportCsv}>Exportera CSV</button>
        <button onClick={exportPdf}>Exportera PDF</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <label>
          Mall
          <select value={String(selectedTemplate)} onChange={e=>onPickTemplate(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="">– Välj mall –</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            <option value="new">+ Skapa mall av nuvarande fält</option>
          </select>
        </label>
        {selectedTemplate === 'new' && (
          <button onClick={createTemplate} style={{ marginLeft: 8 }}>Spara som ny mall</button>
        )}
      </div>

      <form onSubmit={submit} style={{ display: 'grid', gap: 8, marginTop: 16 }}>
        <label>
          Regnr
          <input value={form.vehicle_reg} onChange={e=>setForm({ ...form, vehicle_reg: e.target.value })} />
        </label>
        <label>
          Start
          <input type="datetime-local" value={form.started_at} onChange={e=>setForm({ ...form, started_at: e.target.value })} />
        </label>
        <label>
          Slut
          <input type="datetime-local" value={form.ended_at} onChange={e=>setForm({ ...form, ended_at: e.target.value })} />
        </label>
        <label>
          Syfte
          <input value={form.purpose} onChange={e=>setForm({ ...form, purpose: e.target.value })} />
        </label>
        <label>
          Km (valfritt)
          <input value={form.distance_km} onChange={e=>setForm({ ...form, distance_km: e.target.value })} />
        </label>
        <label>
          Tjänst
          <input type="checkbox" checked={form.business} onChange={e=>setForm({ ...form, business: e.target.checked })} />
        </label>
        <button type="submit">{editId ? 'Uppdatera resa' : 'Spara resa'}</button>
        {editId && <button type="button" onClick={()=>{ setEditId(null); setForm({...form, started_at:'', ended_at:'', distance_km:''}); }}>Avbryt</button>}
      </form>

      <h2 style={{ marginTop: 24, fontSize: 18 }}>Resor</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">Start</th>
            <th align="left">Slut</th>
            <th align="left">Km</th>
            <th align="left">Syfte</th>
            <th align="left">Typ</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {trips.map(t => (
            <tr key={t.id}>
              <td>{new Date(t.started_at).toLocaleString()}</td>
              <td>{new Date(t.ended_at).toLocaleString()}</td>
              <td>{t.distance_km ?? '-'}</td>
              <td>{t.purpose || ''}</td>
              <td>{t.business ? 'Tjänst' : 'Privat'}</td>
              <td style={{ whiteSpace: 'nowrap' }}>
                <button onClick={()=>edit(t)}>Ändra</button>
                <button onClick={()=>remove(t.id)} style={{ marginLeft: 8 }}>Ta bort</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
