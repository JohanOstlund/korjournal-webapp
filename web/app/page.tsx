'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

type Trip = {
  id: number;
  vehicle_reg: string;
  started_at: string;
  ended_at: string;
  distance_km?: number;
  start_odometer_km?: number | null;
  end_odometer_km?: number | null;
  purpose?: string;
  business: boolean;
};

type Template = {
  id: number;
  name: string;
  default_purpose?: string;
  business: boolean;
  default_distance_km?: number;
};

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [vehicle, setVehicle] = useState('ABC123');

  const [form, setForm] = useState({
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

  // === no-cache + cache-bust ===
  const loadTrips = async () => {
    const ts = Date.now();
    const urlBase = vehicle ? `${API}/trips?vehicle=${encodeURIComponent(vehicle)}` : `${API}/trips`;
    const url = `${urlBase}${urlBase.includes('?') ? '&' : '?'}_ts=${ts}`;
    const r = await fetch(url, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } });
    setTrips(await r.json());
  };
  const loadTemplates = async () => {
    const r = await fetch(`${API}/templates?_ts=${Date.now()}`, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } });
    setTemplates(await r.json());
  };

  useEffect(() => { loadTrips(); }, [vehicle]);
  useEffect(() => { loadTemplates(); }, []);

  const round1 = (n: number) => Math.round(n * 10) / 10;
  const toLocalInputValue = (d: Date) => {
    const pad = (x:number)=> String(x).padStart(2,'0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

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
    };
    const r = await fetch(`${API}/templates`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    if (!r.ok) { alert(await r.text()); return; }
    await loadTemplates();
  };

  // --- Start/Stop via HA (med manuellt override möjligt) ---
  const startTrip = async () => {
    try {
      setStarting(true);
      const res = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_reg: vehicle })
      });
      if (!res.ok) {
        alert(`Kunde inte läsa mätarställning (start) — fyll i manuellt nedan.`);
        setStartOdo(null);
      } else {
        const data = await res.json();
        setStartOdo(data.value_km);
      }
      const now = new Date();
      setEndOdo(null);
      setForm(f => ({ ...f, started_at: toLocalInputValue(now), ended_at: '', distance_km: '' }));
    } finally { setStarting(false); }
  };

  const stopTripAndSave = async () => {
    try {
      if (!form.started_at) {
        alert('Ingen pågående resa. Tryck "Starta resa" eller fyll i tider manuellt.');
        return;
      }
      setStopping(true);

      let endVal: number | null = endOdo;
      if (endVal == null) {
        const res = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vehicle_reg: vehicle })
        });
        if (res.ok) {
          const data = await res.json();
          endVal = data.value_km as number;
          setEndOdo(endVal);
        }
      }

      const now = new Date();
      const kmRaw = (startOdo != null && endVal != null) ? (endVal - startOdo) : NaN;
      const km = isFinite(kmRaw) && kmRaw >= 0 ? round1(kmRaw) : (form.distance_km ? parseFloat(form.distance_km) : undefined);

      const payload: any = {
        vehicle_reg: vehicle,
        started_at: new Date(form.started_at).toISOString(),
        ended_at: now.toISOString(),
        purpose: form.purpose,
        business: form.business,
        start_odometer_km: startOdo ?? undefined,
        end_odometer_km: endVal ?? undefined,
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

      setForm(f => ({ ...f, started_at: '', ended_at: '', distance_km: '' }));
      setStartOdo(null); setEndOdo(null); setSelectedTemplate('');
      await loadTrips(); // uppdatera listan direkt
    } finally { setStopping(false); }
  };

  // --- Manuell CRUD ---
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: any = {
      vehicle_reg: vehicle,
      started_at: new Date(form.started_at).toISOString(),
      ended_at: new Date(form.ended_at).toISOString(),
      purpose: form.purpose,
      business: form.business,
      start_odometer_km: startOdo ?? undefined,
      end_odometer_km: endOdo ?? undefined,
    };
    if (form.distance_km) payload.distance_km = parseFloat(form.distance_km);

    const method = editId ? 'PUT' : 'POST';
    const endpoint = editId ? `${API}/trips/${editId}` : `${API}/trips`;
    const res = await fetch(endpoint, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) { alert(await res.text()); return; }
    setForm({ ...form, started_at: '', ended_at: '', distance_km: '' });
    setStartOdo(null); setEndOdo(null); setEditId(null);
    await loadTrips();
  };

  const edit = (t: Trip) => {
    setEditId(t.id);
    setSelectedTemplate('');
    setVehicle(t.vehicle_reg);
    setStartOdo(t.start_odometer_km ?? null);
    setEndOdo(t.end_odometer_km ?? null);
    setForm({
      started_at: t.started_at.slice(0,16),
      ended_at: t.ended_at.slice(0,16),
      purpose: t.purpose || '',
      business: t.business,
      distance_km: t.distance_km?.toString() || '',
    });
  };

  const remove = async (id: number) => {
    if (!confirm('Radera resa?')) return;
    await fetch(`${API}/trips`, { cache: 'no-store' }); // litet nudge
    await fetch(`${API}/trips/${id}`, { method: 'DELETE' });
    await loadTrips();
  };

  const exportCsv = () => window.open(`${API}/exports/journal.csv?vehicle=${vehicle}`, '_blank');
  const exportPdf = () => window.open(`${API}/exports/journal.pdf?vehicle=${vehicle}`, '_blank');

  const liveKm = (startOdo!=null && endOdo!=null) ? round1(endOdo - startOdo) : (form.distance_km ? parseFloat(form.distance_km) : undefined);

  return (
    <div>
      {/* Regnr + Export */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}>
        <label>
          Regnr
          <input value={vehicle} onChange={e=> setVehicle(e.target.value)} />
        </label>
        <button onClick={exportCsv}>Exportera CSV</button>
        <button onClick={exportPdf}>Exportera PDF</button>
      </div>

      {/* Mall */}
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

      {/* Start/Stop + Odometer (editbara) */}
      <div style={{ display:'grid', gap:8, marginTop:12, alignItems:'center', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))' }}>
        <button onClick={startTrip} disabled={starting || !!form.started_at}>
          {starting ? 'Hämtar mätarställning…' : (form.started_at ? 'Start satt' : 'Starta resa (hämta odo)')}
        </button>
        <button onClick={stopTripAndSave} disabled={stopping || !form.started_at}>
          {stopping ? 'Sparar…' : 'Avsluta resa (spara)'}
        </button>
        <label>
          Start mätarställning (km)
          <input
            inputMode="decimal"
            value={startOdo ?? ''}
            onChange={e=> setStartOdo(e.target.value === '' ? null : Number(e.target.value))}
            placeholder="t.ex. 12345.6"
          />
        </label>
        <label>
          Slut mätarställning (km)
          <input
            inputMode="decimal"
            value={endOdo ?? ''}
            onChange={e=> setEndOdo(e.target.value === '' ? null : Number(e.target.value))}
            placeholder="t.ex. 12358.1"
          />
        </label>
        <div style={{ alignSelf:'end', color:'#444' }}>
          Km (auto): {liveKm ?? '-'}
        </div>
      </div>

      {/* Manuell form */}
      <form onSubmit={submit} style={{ display: 'grid', gap: 8, marginTop: 16 }}>
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
          Km (om du vill skriva över)
          <input value={form.distance_km} onChange={e=>setForm({ ...form, distance_km: e.target.value })} />
        </label>
        <label>
          Tjänst
          <input type="checkbox" checked={form.business} onChange={e=>setForm({ ...form, business: e.target.checked })} />
        </label>
        <button type="submit">{editId ? 'Uppdatera resa' : 'Spara resa (manuellt)'}</button>
        {editId && <button type="button" onClick={()=>{ setEditId(null); setForm({...form, started_at:'', ended_at:'', distance_km:''}); setStartOdo(null); setEndOdo(null); }}>Avbryt</button>}
      </form>

      <h2 style={{ marginTop: 24, fontSize: 18 }}>Resor</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">Start</th>
            <th align="left">Slut</th>
            <th align="left">Start-odo</th>
            <th align="left">Slut-odo</th>
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
              <td>{t.start_odometer_km ?? '-'}</td>
              <td>{t.end_odometer_km ?? '-'}</td>
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