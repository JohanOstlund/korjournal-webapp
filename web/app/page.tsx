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

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
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

  const load = async () => {
    const url = vehicle ? `${API}/trips?vehicle=${encodeURIComponent(vehicle)}` : `${API}/trips`;
    const r = await fetch(url);
    setTrips(await r.json());
  };

  useEffect(() => { load(); }, [vehicle]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
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
    await load();
  };

  const edit = (t: Trip) => {
    setEditId(t.id);
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
    await load();
  };

  const exportCsv = () => window.open(`${API}/exports/journal.csv?vehicle=${vehicle}`, '_blank');
  const exportPdf = () => window.open(`${API}/exports/journal.pdf?vehicle=${vehicle}`, '_blank');

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
