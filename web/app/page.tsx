'use client';
import { useEffect, useMemo, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

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
  default_distance_km?: number | null;
  default_vehicle_reg?: string | null;
  default_driver_name?: string | null;
  default_start_address?: string | null;
  default_end_address?: string | null;
};

// Tolka serverns datum som UTC om ingen tidszon anges
const parseServerDate = (isoOrNaive: string | null): Date | null => {
  if (!isoOrNaive) return null;
  const s = isoOrNaive.trim();
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
};

// Visa i användarens lokala tidszon
const fmtLocal = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  return d ? d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '';
};

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [vehicle, setVehicle] = useState(''); // filter: visa bara detta regnr
  const [status, setStatus] = useState<string>('');

  // Formfält (resa)
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

  // Mall-val (för att fylla formulär)
  const [selectedTemplate, setSelectedTemplate] = useState<number | ''>('');

  // Mall-hantering (redigera/ta bort/skapa)
  const [editTplId, setEditTplId] = useState<number | ''>('');
  const [tplName, setTplName] = useState('');
  const [tplBusiness, setTplBusiness] = useState<boolean>(false);
  const [tplPurpose, setTplPurpose] = useState('');
  const [tplVehicle, setTplVehicle] = useState('');
  const [tplDriver, setTplDriver] = useState('');
  const [tplStartAddr, setTplStartAddr] = useState('');
  const [tplEndAddr, setTplEndAddr] = useState('');

  const loadTrips = async () => {
    try {
      setLoading(true);
      const urlBase = vehicle.trim()
        ? `${API}/trips?vehicle=${encodeURIComponent(vehicle.trim())}`
        : `${API}/trips`;
      const url = `${urlBase}${urlBase.includes('?') ? '&' : '?'}include_active=true&_ts=${Date.now()}`;
      const r = await fetch(url, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } });
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

  const loadTemplates = async () => {
    try {
      const r = await fetch(`${API}/templates?_ts=${Date.now()}`, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache' } });
      if (r.ok) setTemplates(await r.json());
    } catch {}
  };

  useEffect(() => { loadTrips(); }, [vehicle]);
  useEffect(() => { loadTemplates(); }, []);

  // Aktiv resa för det valda fordonet (eller första aktiva om vehicle är tomt)
  const activeTrip = useMemo(() => {
    const list = trips.filter(t => t.ended_at === null);
    if (vehicle.trim()) return list.find(t => t.vehicle_reg === vehicle.trim()) || null;
    return list[0] || null;
  }, [trips, vehicle]);

  const round1 = (n: number) => Math.round(n * 10) / 10;

  // HA: Force update + poll (returnerar km)
  const haPollOdometer = async (): Promise<number | null> => {
    try {
      const res = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
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

  // Starta resa
  const startTrip = async () => {
    if (!vehicle.trim()) {
      alert('Fyll i Regnr först (eller välj).');
      return;
    }
    try {
      setStarting(true);
      let odo = await haPollOdometer();
      if (odo == null) odo = startOdo ?? null;

      const body = {
        vehicle_reg: vehicle.trim(),
        start_odometer_km: odo ?? undefined,
        purpose: purpose || undefined,
        business,
        driver_name: driver || undefined,
        start_address: startAddress || undefined,
      };
      const r = await fetch(`${API}/trips/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte starta resa: ${txt}`);
        return;
      }
      setStartOdo(odo);
      setEndOdo(null);
      await loadTrips();
    } finally {
      setStarting(false);
    }
  };

  // Avsluta resa
  const finishTrip = async () => {
    if (!activeTrip) {
      alert('Ingen pågående resa att avsluta.');
      return;
    }
    try {
      setStopping(true);
      let endVal = endOdo;
      if (endVal == null) endVal = await haPollOdometer();

      const body: any = {
        trip_id: activeTrip.id,
        end_odometer_km: endVal ?? undefined,
        purpose: purpose || undefined,
        business,
        driver_name: driver || activeTrip.driver_name || undefined,
        end_address: endAddress || undefined,
      };
      const r = await fetch(`${API}/trips/finish`, {
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

  // Välj mall → fyll resformulär
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
    if (startOdo != null && endOdo != null) return round1(endOdo - startOdo);
    return undefined;
  }, [activeTrip, startOdo, endOdo]);

  // -------- Mall-hantering --------
  const resetTplForm = () => {
    setEditTplId('');
    setTplName('');
    setTplBusiness(false);
    setTplPurpose('');
    setTplVehicle('');
    setTplDriver('');
    setTplStartAddr('');
    setTplEndAddr('');
  };

  const loadTplIntoForm = (tpl: Template) => {
    setEditTplId(tpl.id);
    setTplName(tpl.name || '');
    setTplBusiness(!!tpl.business);
    setTplPurpose(tpl.default_purpose || '');
    setTplVehicle(tpl.default_vehicle_reg || '');
    setTplDriver(tpl.default_driver_name || '');
    setTplStartAddr(tpl.default_start_address || '');
    setTplEndAddr(tpl.default_end_address || '');
  };

  const onSelectTplToEdit = (idStr: string) => {
    if (!idStr) { resetTplForm(); return; }
    const id = parseInt(idStr, 10);
    const tpl = templates.find(t => t.id === id);
    if (tpl) loadTplIntoForm(tpl);
  };

  const saveTemplate = async () => {
    const payload = {
      name: tplName.trim(),
      business: tplBusiness,
      default_purpose: tplPurpose || null,
      default_vehicle_reg: tplVehicle || null,
      default_driver_name: tplDriver || null,
      default_start_address: tplStartAddr || null,
      default_end_address: tplEndAddr || null,
      default_distance_km: null,
    };
    const isEdit = !!editTplId;
    const url = isEdit ? `${API}/templates/${editTplId}` : `${API}/templates`;
    const method = isEdit ? 'PUT' : 'POST';
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte spara mall: ${txt}`);
      return;
    }
    await loadTemplates();
    resetTplForm();
  };

  const deleteTemplate = async () => {
    if (!editTplId) return;
    if (!confirm('Ta bort den här mallen?')) return;
    const r = await fetch(`${API}/templates/${editTplId}`, { method: 'DELETE' });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte ta bort mall: ${txt}`);
      return;
    }
    await loadTemplates();
    resetTplForm();
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
        <button onClick={()=> window.open(`${API}/exports/journal.csv${vehicle ? `?vehicle=${vehicle}` : ''}`, '_blank')}>Exportera CSV</button>
        <button onClick={()=> window.open(`${API}/exports/journal.pdf${vehicle ? `?vehicle=${vehicle}` : ''}`, '_blank')}>Exportera PDF</button>
      </div>

      {/* Mallval till resa + basfält */}
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
      </div>

      {/* Förare + adresser */}
      <div style={{ display:'grid', gap:8, marginTop:12, gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))' }}>
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

      {/* Hantera mallar */}
      <h2 style={{ marginTop: 28, fontSize: 18 }}>Hantera mallar</h2>
      <div style={{ display:'grid', gap:8, gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))' }}>
        <label>
          Välj mall
          <select value={String(editTplId)} onChange={e=>onSelectTplToEdit(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="">– Ny mall –</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label>
          Namn
          <input value={tplName} onChange={(e)=>setTplName(e.target.value)} />
        </label>
        <label style={{ alignItems:'center', display:'flex', gap:8 }}>
          Privat (avmarkera = tjänst)
          <input type="checkbox" checked={!tplBusiness ? true : false} onChange={(e)=>setTplBusiness(!e.target.checked)} />
        </label>
        <label>
          Syfte
          <input value={tplPurpose} onChange={(e)=>setTplPurpose(e.target.value)} />
        </label>
        <label>
          Regnr
          <input value={tplVehicle} onChange={(e)=>setTplVehicle(e.target.value)} />
        </label>
        <label>
          Förare
          <input value={tplDriver} onChange={(e)=>setTplDriver(e.target.value)} />
        </label>
        <label>
          Startadress
          <input value={tplStartAddr} onChange={(e)=>setTplStartAddr(e.target.value)} />
        </label>
        <label>
          Slutadress
          <input value={tplEndAddr} onChange={(e)=>setTplEndAddr(e.target.value)} />
        </label>
      </div>
      <div style={{ display:'flex', gap:8, marginTop:8 }}>
        <button onClick={saveTemplate}>{editTplId ? 'Spara ändringar' : 'Skapa mall'}</button>
        <button onClick={resetTplForm} type="button">Rensa</button>
        <button onClick={deleteTemplate} type="button" disabled={!editTplId}>Ta bort</button>
      </div>

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
