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

  const [startOdo, setStartOdo] = useState<number | null>(null);
  const [endOdo, setEndOdo] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);

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

  // Helpers
  const round1 = (n: number) => Math.round(n * 10) / 10;
  const toLocalInputValue = (d: Date) => {
    const pad = (x:number)=> String(x).padStart(2,'0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  // Templates UI
  const onPickTemplate = (val: string) => {
    if (!val) { setSelectedTemplate(''); return; }
    if (val === 'new') { setSelectedTemplate('new'); return; }
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
    if (!r.ok) { alert(await r.text()); return; }
    await loadTemplates();
    setSelectedTemplate('');
  };

  // Start/Stop via HA
  const startTrip = async () => {
    try {
      setStarting(true);
      const res = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_reg: form.vehicle_reg })
      });
      if (!res.ok) { alert(`Kunde inte läsa mätarställning (start)`); return; }
      const data = await res.json();
      const now = new Date();
      setStartOdo(data.value_km);
      setEndOdo(null);
      setForm(f => ({ ...f, started_at: toLocalInputValue(now), ended_at: '', distance_km: '' }));
    } finally {
      setStarting(false);
    }
  };

  const stopTripAndSave = async () => {
    try {
      if (!form.started_at || startOdo == null) {
        alert('Ingen pågående resa. Tryck "Starta resa" först.');
        return;
      }
      setStopping(true);
      const res = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_reg: form.vehicle_reg })
      });
      if (!res.ok) { alert(`Kunde inte läsa mätarställning (slut)`); return; }
      const data = await res.json();
      const now = new Date();
      const endVal = data.value_km as number;
      setEndOdo(endVal);

      // Räkna och FYLL I fältet
      const kmRaw = endVal - (startOdo as number);
      const km = kmRaw >= 0 && isFinite(kmRaw) ? round1(kmRaw) : 0;
      setForm(f => ({ ...f, ended_at: toLocalInputValue(now), distance_km: km.toString() }));

      // Skicka till server (inkl. start/end-odo → servern har också fallback-beräkning)
      const payload: any = {
        vehicle_reg: form.vehicle_reg,
        started_at: new Date(form.started_at).toISOString(),
        ended_at: now.toISOString(),
        purpose: form.purpose,
        business: form.business,
        start_odometer_km: startOdo,
        end_odometer_km: endVal,
        distance_km: km,
      };

      if (selectedTemplate && selectedTemplate !== 'new') {
        const tplRes = await fetch(`${API}/templates/${selectedTemplate}/apply`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            vehicle_reg: payload.vehicle_reg,
            started_at: payload.started_at,
            ended_at: payload.ended_at,
            purpose: payload.purpose,
            business: payload.business,
            distance_km: payload.distance_km,
          })
        });
        if (!tplRes.ok) { alert(await tplRes.text()); return; }
      } else {
        const r2 = await fetch(`${API}/trips`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!r2.ok) { alert(await r2.text()); return; }
      }

      // Reset och uppdatera listan
      setForm(f => ({ ...f, started_at: '', ended_at: '', distance_km: '' }));
      setStartOdo(null); setEndOdo(null); setSelectedTemplate('');
      await loadTrips();
    } finally {
      setStopping(false);
    }
  };

  // Manuell CRUD (kvar för ändringar)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
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
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      if (!res.ok) { alert(await res.text()); return; }
      setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
      setSelectedTemplate('');
      await loadTrips();
      return;
    }

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
    if (!res.ok) { alert(await res.text()); return; }
    setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
    setEditId(null);
    await loadTrips();
  };

  const edit = (t: Trip) => {
    setEditId(t.id);
    setSelectedTemplate('');
    setStartOdo(null); setEndOdo(null);
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

      {/* Start/Stop-flöde kopplat till HA */}
      <div style={{ display:'flex', gap:8, marginTop:12, alignItems:'center' }}>
        <button onClick={startTrip} disabled={starting || !!startOdo}>
          {starting ? 'Hämtar mätarställning…' : (startOdo != null ? `Start satt (${startOdo} km)` : 'Starta resa (hämta odo)')}
        </button>
        <button onClick={stopTripAndSave} disabled={stopping || startOdo == null}>
          {stopping ? 'Sparar…' : 'Avsluta resa (hämta odo & spara)'}
        </button>
        {startOdo != null && endOdo != null && (
          <span style={{ marginLeft: 8 }}>
            {`Km: ${round1(endOdo - startOdo)} (start ${startOdo} → slut ${endOdo})`}
          </span>
        )}
      </div>

      {/* Manuell form finns kvar */}
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
          Km (auto vid avslut, kan justeras)
          <input value={form.distance_km} onChange={e=>setForm({ ...form, distance_km: e.target.value })} />
        </label>
        <label>
          Tjänst
          <input type="checkbox" checked={form.business} onChange={e=>setForm({ ...form, business: e.target.checked })} />
        </label>
        <button type="submit">{editId ? 'Uppdatera resa' : 'Spara resa (manuellt)'}</button>
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
