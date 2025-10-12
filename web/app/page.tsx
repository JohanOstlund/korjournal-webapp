'use client';
import { useEffect, useMemo, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const fetchAuth = (url: string, options: RequestInit = {}) =>
  fetch(url, { credentials: 'include', ...options });

type Trip = {
  id: number;
  vehicle_reg: string;
  started_at: string;
  ended_at: string | null;
  distance_km?: number | null;
  start_odometer_km?: number | null;
  end_odometer_km?: number | null;
  purpose?: string | null;
  business: boolean;
  driver_name?: string | null;
  start_address?: string | null;
  end_address?: string | null;
};

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

// Tolka serverns datum (UTC/naivt) -> Date
const parseServerDate = (isoOrNaive: string | null): Date | null => {
  if (!isoOrNaive) return null;
  const s = isoOrNaive.trim();
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
};

// För display i UI (lokal tid)
const fmtLocal = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  return d ? d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '';
};

// För <input type="datetime-local"> krävs "YYYY-MM-DDTHH:mm"
const toLocalInputValue = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  if (!d) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
};

// Från <input datetime-local> (lokal) -> ISO UTC-string
const fromLocalInputToISOStringUTC = (val: string | null) => {
  if (!val) return null;
  const d = new Date(val);
  return isNaN(d.getTime()) ? null : d.toISOString();
};

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [vehicle, setVehicle] = useState(''); // filter: visa bara detta regnr
  const [status, setStatus] = useState<string>('');

  // Formfält för ny/pågående resa
  const [purpose, setPurpose] = useState<string>('Kundbesök');
  const [business, setBusiness] = useState<boolean>(true);
  const [driver, setDriver] = useState<string>('');
  const [startAddress, setStartAddress] = useState<string>('');
  const [endAddress, setEndAddress] = useState<string>('');

  // Odo-fält
  const [startOdo, setStartOdo] = useState<number | null>(null);
  const [endOdo, setEndOdo] = useState<number | null>(null);

  // UI states
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);

  // ==== Redigera resa ====
  const [editId, setEditId] = useState<number | null>(null);
  const [editVehicle, setEditVehicle] = useState('');
  const [editPurpose, setEditPurpose] = useState('');
  const [editBusiness, setEditBusiness] = useState<boolean>(true);
  const [editDriver, setEditDriver] = useState('');
  const [editStartAddr, setEditStartAddr] = useState('');
  const [editEndAddr, setEditEndAddr] = useState('');
  const [editStartOdo, setEditStartOdo] = useState<number | null>(null);
  const [editEndOdo, setEditEndOdo] = useState<number | null>(null);
  const [editStartedAt, setEditStartedAt] = useState(''); // datetime-local
  const [editEndedAt, setEditEndedAt] = useState(''); // datetime-local
  const [editSaving, setEditSaving] = useState(false);
  const [editDeleting, setEditDeleting] = useState(false);

  // ==== Använd mall (dropdown) ====
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<number | ''>('');

  const loadTrips = async () => {
    try {
      setLoading(true);
      const urlBase = vehicle.trim()
        ? `${API}/trips?vehicle=${encodeURIComponent(vehicle.trim())}`
        : `${API}/trips`;
      const url = `${urlBase}${urlBase.includes('?') ? '&' : '?'}include_active=true&_ts=${Date.now()}`;
      const r = await fetchAuth(url, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } });
      if (!r.ok) throw new Error(`GET /trips ${r.status}`);
      const data = (await r.json()) as Trip[];
      setTrips(data);
      setStatus(`OK – ${data.length} resor laddade från ${API}`);
    } catch (e: any) {
      setStatus(`Fel vid laddning av resor: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrips(); }, [vehicle]);

  // Ladda mallar för dropdown (utan CRUD här)
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const r = await fetchAuth(`${API}/templates?_ts=${Date.now()}`, { cache: 'no-store' });
        if (r.ok) setTemplates(await r.json());
      } catch (e) {
        console.error('Kunde inte ladda mallar', e);
      }
    };
    loadTemplates();
  }, []);

  // Aktiv resa för det valda fordonet (eller första aktiva om vehicle är tomt)
  const activeTrip = useMemo(() => {
    const list = trips.filter(t => t.ended_at === null);
    if (vehicle.trim()) return list.find(t => t.vehicle_reg === vehicle.trim()) || null;
    return list[0] || null;
  }, [trips, vehicle]);

  const round1 = (n: number) => Math.round(n * 10) / 10;

  // HA: endast läsa sensor (utan force), returnerar km eller null
  const haPollOdometerNoForce = async (): Promise<number | null> => {
    try {
      const res = await fetchAuth(`${API}/integrations/home-assistant/poll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_reg: (vehicle || 'UNKNOWN').trim() }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return typeof data.value_km === 'number' ? data.value_km : null;
    } catch {
      return null;
    }
  };

  // HA: Force update + poll (med force)
  const haForceUpdateAndPoll = async (): Promise<number | null> => {
    try {
      const res = await fetchAuth(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_reg: (vehicle || 'UNKNOWN').trim() }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return typeof data.value_km === 'number' ? data.value_km : null;
    } catch {
      return null;
    }
  };

  // ====== Starta/avsluta resa ======
  const startTrip = async () => {
    if (!vehicle.trim()) {
      alert('Fyll i Regnr först (eller välj).');
      return;
    }
    try {
      setStarting(true);

      // 1) Om användaren matat in start-odo → använd det, ring inte HA.
      let odo = startOdo;

      // 2) Annars: prova att bara läsa nuvarande värde från HA (utan force).
      if (odo == null) {
        odo = await haPollOdometerNoForce();
      }

      // 3) Om fortfarande null: prova force update + poll.
      if (odo == null) {
        odo = await haForceUpdateAndPoll();
      }

      const body = {
        vehicle_reg: vehicle.trim(),
        start_odometer_km: odo ?? undefined, // undefined = utelämna fältet om vi inte fick värde
        purpose: purpose || undefined,
        business,
        driver_name: driver || undefined,
        start_address: startAddress || undefined,
        end_address: endAddress || undefined, // spara slutadress vid START
      };
      const r = await fetchAuth(`${API}/trips/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte starta resa: ${txt}`);
        return;
      }
      setStartOdo(odo ?? null);
      setEndOdo(null);
      await loadTrips();
    } finally {
      setStarting(false);
    }
  };

  const finishTrip = async () => {
    if (!activeTrip) {
      alert('Ingen pågående resa att avsluta.');
      return;
    }
    try {
      setStopping(true);

      // 1) Om användaren matat in slut-odo → använd det, ring inte HA.
      let endVal = endOdo;

      // 2) Annars: prova med force update först (ofta färskast värde vid stopp).
      if (endVal == null) {
        endVal = await haForceUpdateAndPoll();
      }

      // 3) Om fortfarande null: prova enkel poll utan force.
      if (endVal == null) {
        endVal = await haPollOdometerNoForce();
      }

      // Skicka endast fält som ska ändras vid avslut
      const body: any = { trip_id: activeTrip.id };
      if (endVal != null) body.end_odometer_km = endVal;

      const r = await fetchAuth(`${API}/trips/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte avsluta resa: ${txt}`);
        return;
      }
      setEndOdo(endVal ?? null);
      await loadTrips();
    } finally {
      setStopping(false);
    }
  };

  // Mall → fyll reseformulär
  const onPickTemplate = (val: string) => {
    if (!val) { setSelectedTemplate(''); return; }
    const id = parseInt(val, 10);
    setSelectedTemplate(id);
    const t = templates.find(x => x.id === id);
    if (t) {
      if (t.default_vehicle_reg) setVehicle(t.default_vehicle_reg);
      if (t.default_driver_name) setDriver(t.default_driver_name);
      if (t.default_start_address) setStartAddress(t.default_start_address);
      if (t.default_end_address) setEndAddress(t.default_end_address);
      if (typeof t.business === 'boolean') setBusiness(t.business);
      if (t.default_purpose) setPurpose(t.default_purpose);
    }
  };

  const activeKmLive = useMemo(() => {
    if (!activeTrip) return undefined;
    if (startOdo != null && endOdo != null) return Math.round((endOdo - startOdo) * 10) / 10;
    return undefined;
  }, [activeTrip, startOdo, endOdo]);

  // ====== Ladda en resa i redigeringsformuläret ======
  const loadTripIntoEditor = (t: Trip) => {
    setEditId(t.id);
    setEditVehicle(t.vehicle_reg || '');
    setEditPurpose(t.purpose || '');
    setEditBusiness(!!t.business);
    setEditDriver(t.driver_name || '');
    setEditStartAddr(t.start_address || '');
    setEditEndAddr(t.end_address || '');
    setEditStartOdo(t.start_odometer_km ?? null);
    setEditEndOdo(t.end_odometer_km ?? null);
    setEditStartedAt(toLocalInputValue(t.started_at));
    setEditEndedAt(toLocalInputValue(t.ended_at));
    setTimeout(() => {
      document.getElementById('edit-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
  };

  const resetEditor = () => {
    setEditId(null);
    setEditVehicle('');
    setEditPurpose('');
    setEditBusiness(true);
    setEditDriver('');
    setEditStartAddr('');
    setEditEndAddr('');
    setEditStartOdo(null);
    setEditEndOdo(null);
    setEditStartedAt('');
    setEditEndedAt('');
  };

  // ====== Spara (PUT) / Ta bort (DELETE) resa ======
  const saveEdit = async () => {
    if (!editId) return;
    if (!editVehicle.trim()) {
      alert('Regnr krävs.');
      return;
    }
    if (!editStartedAt) {
      alert('Starttid krävs.');
      return;
    }
    try {
      setEditSaving(true);
      const payload: any = {
        vehicle_reg: editVehicle.trim(),
        started_at: fromLocalInputToISOStringUTC(editStartedAt),
        ended_at: editEndedAt ? fromLocalInputToISOStringUTC(editEndedAt) : null,
        start_odometer_km: editStartOdo ?? null,
        end_odometer_km: editEndOdo ?? null,
        purpose: editPurpose || null,
        business: editBusiness,
        driver_name: editDriver || null,
        start_address: editStartAddr || null,
        end_address: editEndAddr || null,
        distance_km: null, // låt backend räkna från odo om möjligt
      };
      const r = await fetchAuth(`${API}/trips/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte spara resan: ${txt}`);
        return;
      }
      await loadTrips();
      resetEditor();
    } finally {
      setEditSaving(false);
    }
  };

  const deleteEdit = async () => {
    if (!editId) return;
    if (!confirm('Ta bort den här resan?')) return;
    try {
      setEditDeleting(true);
      const r = await fetchAuth(`${API}/trips/${editId}`, { method: 'DELETE' });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte ta bort resan: ${txt}`);
        return;
      }
      await loadTrips();
      resetEditor();
    } finally {
      setEditDeleting(false);
    }
  };

  return (
    <div>
      {/* Filter + export */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <label>
          Regnr (lämna tomt = visa alla)
          <input
            value={vehicle}
            onChange={e=> setVehicle(e.target.value)}
            placeholder="t.ex. ABC123, eller tomt för alla"
            style={{ marginLeft: 8 }}
          />
        </label>
        {/* OBS: window.open skickar cookies automatiskt till samma domän/subdomän */}
        <button onClick={()=> window.open(`${API}/exports/journal.csv${vehicle ? `?vehicle=${vehicle}` : ''}`, '_blank')}>Exportera CSV</button>
        <button onClick={()=> window.open(`${API}/exports/journal.pdf${vehicle ? `?vehicle=${vehicle}` : ''}`, '_blank')}>Exportera PDF</button>
      </div>

      {/* Mallval + basfält för ny/pågående resa */}
      <div style={{ display:'grid', gap:8, marginTop:12, gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))' }}>
        <label>
          Mall
          <select value={String(selectedTemplate)} onChange={e=>onPickTemplate(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="">– Välj mall –</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label>
          Syfte
          <input value={purpose} onChange={e=>setPurpose(e.target.value)} />
        </label>
        <label style={{ alignItems:'center', display:'flex', gap:8 }}>
          Tjänst
          <input type="checkbox" checked={business} onChange={e=>setBusiness(e.target.checked)} />
        </label>
        <label>
          Förare
          <input value={driver} onChange={e=>setDriver(e.target.value)} />
        </label>
        <label>
          Startadress
          <input value={startAddress} onChange={e=>setStartAddress(e.target.value)} />
        </label>
        <label>
          Slutadress
          <input value={endAddress} onChange={e=>setEndAddress(e.target.value)} />
        </label>
      </div>

      {/* Pågående resa – panel */}
      {activeTrip ? (
        <div style={{ marginTop: 16, padding: 12, border: '1px solid #ddd', borderRadius: 8, background: '#fffbea' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', gap: 8, flexWrap:'wrap' }}>
            <div>
              <strong>Pågående resa</strong> — {activeTrip.vehicle_reg} • start {fmtLocal(activeTrip.started_at)}
              <div style={{ color:'#444', marginTop: 6 }}>
                Förare: <strong>{activeTrip.driver_name || driver || '-'}</strong>
                {' • '}
                Start-odo: <strong>{activeTrip.start_odometer_km ?? startOdo ?? '-'}</strong>
                {activeKmLive != null && <> • Km (auto): <strong>{activeKmLive}</strong></>}
                {(activeTrip.start_address || startAddress) && <> • Startadress: <strong>{activeTrip.start_address || startAddress}</strong></>}
              </div>
            </div>
            <div style={{ display:'flex', gap:8, alignItems:'center' }}>
              <label>
                Slut mätarställning (km)
                <input
                  inputMode="decimal"
                  value={endOdo ?? ''}
                  onChange={e=> setEndOdo(e.target.value === '' ? null : Number(e.target.value))}
                  placeholder="t.ex. 12358.1"
                  style={{ marginLeft: 8 }}
                />
              </label>
              <button onClick={finishTrip} disabled={stopping}>
                {stopping ? 'Avslutar…' : 'Avsluta resa'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 16, padding: 12, border: '1px solid #eee', borderRadius: 8 }}>
          <div style={{ display:'flex', gap:12, alignItems:'center', flexWrap:'wrap' }}>
            <label>
              Start mätarställning (km)
              <input
                inputMode="decimal"
                value={startOdo ?? ''}
                onChange={e=> setStartOdo(e.target.value === '' ? null : Number(e.target.value))}
                placeholder="t.ex. 12345.6"
                style={{ marginLeft: 8 }}
              />
            </label>
            <button onClick={startTrip} disabled={starting || !vehicle.trim()}>
              {starting ? 'Startar…' : 'Starta resa'}
            </button>
            <span style={{ color:'#666' }}>Tips: lämna fältet tomt så försöker vi läsa odo från Home Assistant.</span>
          </div>
        </div>
      )}

      {/* Redigera/ta bort resa */}
      <h2 id="edit-panel" style={{ marginTop: 28, fontSize: 18 }}>Redigera resa</h2>
      {editId ? (
        <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12, background:'#fafafa' }}>
          <div style={{ display:'grid', gap:8, gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))' }}>
            <label>
              Regnr
              <input value={editVehicle} onChange={e=>setEditVehicle(e.target.value)} />
            </label>
            <label>
              Syfte
              <input value={editPurpose} onChange={e=>setEditPurpose(e.target.value)} />
            </label>
            <label style={{ alignItems:'center', display:'flex', gap:8 }}>
              Tjänst
              <input type="checkbox" checked={editBusiness} onChange={e=>setEditBusiness(e.target.checked)} />
            </label>
            <label>
              Förare
              <input value={editDriver} onChange={e=>setEditDriver(e.target.value)} />
            </label>
            <label>
              Startadress
              <input value={editStartAddr} onChange={e=>setEditStartAddr(e.target.value)} />
            </label>
            <label>
              Slutadress
              <input value={editEndAddr} onChange={e=>setEditEndAddr(e.target.value)} />
            </label>
            <label>
              Start mätarställning (km)
              <input
                inputMode="decimal"
                value={editStartOdo ?? ''}
                onChange={e=> setEditStartOdo(e.target.value === '' ? null : Number(e.target.value))}
              />
            </label>
            <label>
              Slut mätarställning (km)
              <input
                inputMode="decimal"
                value={editEndOdo ?? ''}
                onChange={e=> setEditEndOdo(e.target.value === '' ? null : Number(e.target.value))}
              />
            </label>
            <label>
              Starttid
              <input
                type="datetime-local"
                value={editStartedAt}
                onChange={e=> setEditStartedAt(e.target.value)}
              />
            </label>
            <label>
              Sluttid
              <input
                type="datetime-local"
                value={editEndedAt}
                onChange={e=> setEditEndedAt(e.target.value)}
              />
            </label>
          </div>
          <div style={{ display:'flex', gap:8, marginTop:12 }}>
            <button onClick={saveEdit} disabled={editSaving}>{editSaving ? 'Sparar…' : 'Spara ändringar'}</button>
            <button type="button" onClick={resetEditor}>Avbryt</button>
            <button type="button" onClick={deleteEdit} disabled={editDeleting} style={{ color:'#b00020' }}>
              {editDeleting ? 'Tar bort…' : 'Ta bort'}
            </button>
          </div>
        </div>
      ) : (
        <div style={{ color:'#666' }}>Klicka “Redigera” på en resa i listan nedan för att ändra eller ta bort.</div>
      )}

      {/* Lista resor */}
      <h2 style={{ marginTop: 28, fontSize: 18 }}>Resor</h2>
      {loading ? (
        <div>Laddar…</div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align="left">Start</th>
              <th align="left">Slut</th>
              <th align="left">Regnr</th>
              <th align="left">Förare</th>
              <th align="left">Startadress</th>
              <th align="left">Slutadress</th>
              <th align="left">Start-odo</th>
              <th align="left">Slut-odo</th>
              <th align="left">Km</th>
              <th align="left">Syfte</th>
              <th align="left">Typ</th>
              <th align="left">Åtgärd</th>
            </tr>
          </thead>
          <tbody>
            {trips.map(t => (
              <tr key={t.id} style={{ borderTop: '1px solid #eee' }}>
                <td>{fmtLocal(t.started_at)}</td>
                <td>{t.ended_at ? fmtLocal(t.ended_at) : <em>Pågående…</em>}</td>
                <td>{t.vehicle_reg}</td>
                <td>{t.driver_name || ''}</td>
                <td>{t.start_address || ''}</td>
                <td>{t.end_address || ''}</td>
                <td>{t.start_odometer_km ?? '-'}</td>
                <td>{t.ended_at ? (t.end_odometer_km ?? '-') : <em>–</em>}</td>
                <td>{t.ended_at ? (t.distance_km ?? '-') : <em>Pågår</em>}</td>
                <td>{t.purpose || ''}</td>
                <td>{t.business ? 'Tjänst' : 'Privat'}</td>
                <td>
                  <button onClick={()=> loadTripIntoEditor(t)}>Redigera</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Statusrad */}
      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
        API: <code>{API}</code> — {status}
      </div>
    </div>
  );
}
