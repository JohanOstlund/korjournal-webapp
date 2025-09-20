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
  const [form, setForm] = useState({
    vehicle_reg: 'ABC123',
    started_at: '',
    ended_at: '',
    purpose: 'Kundbesök',
    business: true,
    distance_km: '',
  });

  const load = async () => {
    const r = await fetch(`${API}/trips`);
    setTrips(await r.json());
  };

  useEffect(() => { load(); }, []);

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
    await fetch(`${API}/trips`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
    await load();
  };

  const exportCsv = () => window.open(`${API}/exports/journal.csv`, '_blank');
  const exportPdf = () => window.open(`${API}/exports/journal.pdf`, '_blank');

  return (
    <div>
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
        <button type="submit">Spara resa</button>
      </form>

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button onClick={exportCsv}>Exportera CSV</button>
        <button onClick={exportPdf}>Exportera PDF</button>
      </div>

      <h2 style={{ marginTop: 24, fontSize: 18 }}>Senaste resor</h2>
      <ul>
        {trips.map(t => (
          <li key={t.id}>
            {new Date(t.started_at).toLocaleString()} → {new Date(t.ended_at).toLocaleString()} · {t.vehicle_reg} · {t.purpose || ''} · {t.distance_km ?? '-'} km · {t.business ? 'Tjänst' : 'Privat'}
          </li>
        ))}
      </ul>
    </div>
  );
}
