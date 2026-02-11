'use client';
import { useEffect, useMemo, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

async function fetchAuth(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(input, { credentials: 'include', ...init, headers });
}

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

// Datumhjälpare
const parseServerDate = (isoOrNaive: string | null): Date | null => {
  if (!isoOrNaive) return null;
  const s = isoOrNaive.trim();
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
};
const fmtLocal = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  return d ? d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '';
};
const fmtDate = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';
};
const fmtTime = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  return d ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '';
};
const toLocalInputValue = (isoOrNaive: string | null) => {
  const d = parseServerDate(isoOrNaive);
  if (!d) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const fromLocalInputToISOStringUTC = (val: string | null) => {
  if (!val) return null;
  const d = new Date(val);
  return isNaN(d.getTime()) ? null : d.toISOString();
};

/* Decimal-safe input: hanterar komma som decimaltecken (mobil, sv_SE) */
function DecimalInput({ value, onValueChange, className, ...props }: {
  value: number | null;
  onValueChange: (v: number | null) => void;
  placeholder?: string;
  style?: React.CSSProperties;
  className?: string;
}) {
  const [raw, setRaw] = useState(value != null ? String(value) : '');

  useEffect(() => {
    const cur = parseFloat(raw.replace(',', '.'));
    if (value == null) {
      if (raw !== '') setRaw('');
    } else if (isNaN(cur) || Math.abs(cur - value) > 0.0001) {
      setRaw(String(value));
    }
  }, [value]);

  return (
    <input
      inputMode="decimal"
      value={raw}
      onChange={e => {
        const v = e.target.value;
        setRaw(v);
        if (v === '') { onValueChange(null); return; }
        const n = parseFloat(v.replace(',', '.'));
        if (!isNaN(n)) onValueChange(n);
      }}
      className={className}
      {...props}
    />
  );
}

export default function Home() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [vehicle, setVehicle] = useState('');
  const [status, setStatus] = useState<string>('');

  const [year, setYear] = useState<number>(new Date().getFullYear());
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 2, y - 1, y, y + 1, y + 2];
  }, []);

  const [purpose, setPurpose] = useState<string>('Kundbesök');
  const [business, setBusiness] = useState<boolean>(true);
  const [driver, setDriver] = useState<string>('');
  const [startAddress, setStartAddress] = useState<string>('');
  const [endAddress, setEndAddress] = useState<string>('');
  const [startOdo, setStartOdo] = useState<number | null>(null);
  const [endOdo, setEndOdo] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);

  const [editId, setEditId] = useState<number | null>(null);
  const [editVehicle, setEditVehicle] = useState('');
  const [editPurpose, setEditPurpose] = useState('');
  const [editBusiness, setEditBusiness] = useState<boolean>(true);
  const [editDriver, setEditDriver] = useState('');
  const [editStartAddr, setEditStartAddr] = useState('');
  const [editEndAddr, setEditEndAddr] = useState('');
  const [editStartOdo, setEditStartOdo] = useState<number | null>(null);
  const [editEndOdo, setEditEndOdo] = useState<number | null>(null);
  const [editStartedAt, setEditStartedAt] = useState('');
  const [editEndedAt, setEditEndedAt] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [editDeleting, setEditDeleting] = useState(false);

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
      setStatus(`${data.length} resor`);
    } catch (e: any) {
      setStatus(`Fel: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrips(); }, [vehicle]);

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

  const activeTrip = useMemo(() => {
    const list = trips.filter(t => t.ended_at === null);
    if (vehicle.trim()) return list.find(t => t.vehicle_reg === vehicle.trim()) || null;
    return list[0] || null;
  }, [trips, vehicle]);

  // HA helpers
  const haPollOdometerNoForce = async (): Promise<number | null> => {
    try {
      const res = await fetchAuth(`${API}/integrations/home-assistant/poll`, {
        method: 'POST',
        body: JSON.stringify({ vehicle_reg: (vehicle || 'UNKNOWN').trim() }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return typeof data.value_km === 'number' ? data.value_km : null;
    } catch { return null; }
  };
  const haForceUpdateAndPoll = async (): Promise<number | null> => {
    try {
      const res = await fetchAuth(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST',
        body: JSON.stringify({ vehicle_reg: (vehicle || 'UNKNOWN').trim() }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return typeof data.value_km === 'number' ? data.value_km : null;
    } catch { return null; }
  };

  const startTrip = async () => {
    if (!vehicle.trim()) { alert('Fyll i Regnr först (eller välj).'); return; }
    try {
      setStarting(true);
      let odo = startOdo ?? await haPollOdometerNoForce() ?? await haForceUpdateAndPoll();
      const body = {
        vehicle_reg: vehicle.trim(),
        start_odometer_km: odo ?? undefined,
        purpose: purpose || undefined,
        business,
        driver_name: driver || undefined,
        start_address: startAddress || undefined,
        end_address: endAddress || undefined,
      };
      const r = await fetchAuth(`${API}/trips/start`, { method: 'POST', body: JSON.stringify(body) });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte starta resa: ${txt}`); return; }
      setStartOdo(odo ?? null);
      setEndOdo(null);
      await loadTrips();
    } finally { setStarting(false); }
  };

  const finishTrip = async () => {
    if (!activeTrip) { alert('Ingen pågående resa att avsluta.'); return; }
    try {
      setStopping(true);
      let endVal = endOdo ?? await haForceUpdateAndPoll() ?? await haPollOdometerNoForce();
      const body: any = { trip_id: activeTrip.id };
      if (endVal != null) body.end_odometer_km = endVal;
      const r = await fetchAuth(`${API}/trips/finish`, { method: 'POST', body: JSON.stringify(body) });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte avsluta resa: ${txt}`); return; }
      setEndOdo(endVal ?? null);
      await loadTrips();
    } finally { setStopping(false); }
  };

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
    setEditId(null); setEditVehicle(''); setEditPurpose(''); setEditBusiness(true);
    setEditDriver(''); setEditStartAddr(''); setEditEndAddr('');
    setEditStartOdo(null); setEditEndOdo(null); setEditStartedAt(''); setEditEndedAt('');
  };

  const saveEdit = async () => {
    if (!editId) return;
    if (!editVehicle.trim()) { alert('Regnr krävs.'); return; }
    if (!editStartedAt) { alert('Starttid krävs.'); return; }
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
        distance_km: null,
      };
      const r = await fetchAuth(`${API}/trips/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte spara resan: ${txt}`); return; }
      await loadTrips();
      resetEditor();
    } finally { setEditSaving(false); }
  };

  const deleteEdit = async () => {
    if (!editId) return;
    if (!confirm('Ta bort den här resan?')) return;
    try {
      setEditDeleting(true);
      const r = await fetchAuth(`${API}/trips/${editId}`, { method: 'DELETE' });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte ta bort resan: ${txt}`); return; }
      await loadTrips();
      resetEditor();
    } finally { setEditDeleting(false); }
  };

  const csvUrl = `${API}/exports/journal.csv?year=${year}${vehicle ? `&vehicle=${encodeURIComponent(vehicle)}` : ''}`;
  const pdfUrl = `${API}/exports/journal.pdf?year=${year}${vehicle ? `&vehicle=${encodeURIComponent(vehicle)}` : ''}`;

  return (
    <div>
      {/* Toolbar: filter + export */}
      <div className="toolbar">
        <div className="field">
          <span className="field-label">Regnr</span>
          <input
            type="text"
            value={vehicle}
            onChange={e => setVehicle(e.target.value)}
            placeholder="Alla fordon"
            style={{ width: 150 }}
          />
        </div>
        <div className="field">
          <span className="field-label">År</span>
          <select value={year} onChange={e => setYear(Number(e.target.value))} style={{ width: 100 }}>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="field" style={{ alignSelf: 'flex-end' }}>
          <div className="btn-group">
            <button className="btn btn-ghost btn-sm" onClick={() => window.open(csvUrl, '_blank')}>CSV</button>
            <button className="btn btn-ghost btn-sm" onClick={() => window.open(pdfUrl, '_blank')}>PDF</button>
          </div>
        </div>
      </div>

      {/* Template + form fields */}
      <div className="card section">
        <div className="card-header">Resuppgifter</div>
        <div className="form-grid">
          <div className="field">
            <span className="field-label">Mall</span>
            <select value={String(selectedTemplate)} onChange={e => onPickTemplate(e.target.value)}>
              <option value="">– Välj mall –</option>
              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="field">
            <span className="field-label">Syfte</span>
            <input type="text" value={purpose} onChange={e => setPurpose(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Typ</span>
            <div className="field-row" style={{ minHeight: 44 }}>
              <input type="checkbox" checked={business} onChange={e => setBusiness(e.target.checked)} id="chk-business" />
              <label htmlFor="chk-business" style={{ fontSize: 15, cursor: 'pointer' }}>Tjänsteresa</label>
            </div>
          </div>
          <div className="field">
            <span className="field-label">Förare</span>
            <input type="text" value={driver} onChange={e => setDriver(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Startadress</span>
            <input type="text" value={startAddress} onChange={e => setStartAddress(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">Slutadress</span>
            <input type="text" value={endAddress} onChange={e => setEndAddress(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Active trip / Start trip */}
      {activeTrip ? (
        <div className="card card-warning section">
          <div className="card-header">
            <span className="badge badge-active">Pågående</span>
            {activeTrip.vehicle_reg} — start {fmtLocal(activeTrip.started_at)}
          </div>
          <div style={{ fontSize: 14, color: '#78350f', marginBottom: 12 }}>
            Förare: <strong>{activeTrip.driver_name || driver || '–'}</strong>
            {' · '}Start-odo: <strong>{activeTrip.start_odometer_km ?? startOdo ?? '–'}</strong>
            {(startOdo != null && endOdo != null) && <> · Km: <strong>{Math.round((endOdo - startOdo) * 10) / 10}</strong></>}
            {(activeTrip.start_address || startAddress) && <> · {activeTrip.start_address || startAddress}</>}
          </div>
          <div className="form-grid" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="field">
              <span className="field-label">Slut mätarställning (km)</span>
              <DecimalInput value={endOdo} onValueChange={setEndOdo} placeholder="t.ex. 12358,1" />
            </div>
            <div className="field" style={{ alignSelf: 'flex-end' }}>
              <button className="btn btn-danger" onClick={finishTrip} disabled={stopping}>
                {stopping ? 'Avslutar…' : 'Avsluta resa'}
              </button>
            </div>
          </div>
          <p className="text-xs text-light mt-8">Lämna tomt för att hämta från Home Assistant.</p>
        </div>
      ) : (
        <div className="card card-success section">
          <div className="card-header">Starta ny resa</div>
          <div className="form-grid" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="field">
              <span className="field-label">Start mätarställning (km)</span>
              <DecimalInput value={startOdo} onValueChange={setStartOdo} placeholder="t.ex. 12345,6" />
            </div>
            <div className="field" style={{ alignSelf: 'flex-end' }}>
              <button className="btn btn-success" onClick={startTrip} disabled={starting || !vehicle.trim()}>
                {starting ? 'Startar…' : 'Starta resa'}
              </button>
            </div>
          </div>
          <p className="text-xs text-light mt-8">Lämna tomt för att hämta från Home Assistant.</p>
        </div>
      )}

      {/* Edit panel */}
      <div className="section" id="edit-panel">
        <h2>Redigera resa</h2>
        {editId ? (
          <div className="card">
            <div className="form-grid">
              <div className="field">
                <span className="field-label">Regnr</span>
                <input type="text" value={editVehicle} onChange={e => setEditVehicle(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Syfte</span>
                <input type="text" value={editPurpose} onChange={e => setEditPurpose(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Typ</span>
                <div className="field-row" style={{ minHeight: 44 }}>
                  <input type="checkbox" checked={editBusiness} onChange={e => setEditBusiness(e.target.checked)} id="chk-edit-biz" />
                  <label htmlFor="chk-edit-biz" style={{ fontSize: 15, cursor: 'pointer' }}>Tjänsteresa</label>
                </div>
              </div>
              <div className="field">
                <span className="field-label">Förare</span>
                <input type="text" value={editDriver} onChange={e => setEditDriver(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Startadress</span>
                <input type="text" value={editStartAddr} onChange={e => setEditStartAddr(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Slutadress</span>
                <input type="text" value={editEndAddr} onChange={e => setEditEndAddr(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Start mätarställning</span>
                <DecimalInput value={editStartOdo} onValueChange={setEditStartOdo} />
              </div>
              <div className="field">
                <span className="field-label">Slut mätarställning</span>
                <DecimalInput value={editEndOdo} onValueChange={setEditEndOdo} />
              </div>
              <div className="field">
                <span className="field-label">Starttid</span>
                <input type="datetime-local" value={editStartedAt} onChange={e => setEditStartedAt(e.target.value)} />
              </div>
              <div className="field">
                <span className="field-label">Sluttid</span>
                <input type="datetime-local" value={editEndedAt} onChange={e => setEditEndedAt(e.target.value)} />
              </div>
            </div>
            <div className="btn-group mt-16">
              <button className="btn btn-primary" onClick={saveEdit} disabled={editSaving}>
                {editSaving ? 'Sparar…' : 'Spara ändringar'}
              </button>
              <button className="btn btn-ghost" onClick={resetEditor}>Avbryt</button>
              <button className="btn btn-danger" onClick={deleteEdit} disabled={editDeleting}>
                {editDeleting ? 'Tar bort…' : 'Ta bort'}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-muted">Klicka &quot;Redigera&quot; på en resa nedan.</p>
        )}
      </div>

      {/* Trip list */}
      <div className="section">
        <h2>Resor {!loading && <span className="text-light text-sm">({trips.length})</span>}</h2>

        {loading ? (
          <p className="text-muted">Laddar…</p>
        ) : (
          <>
            {/* Desktop table */}
            <div className="trip-list-desktop">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Start</th>
                    <th>Slut</th>
                    <th>Regnr</th>
                    <th>Förare</th>
                    <th>Startadress</th>
                    <th>Slutadress</th>
                    <th>Start-odo</th>
                    <th>Slut-odo</th>
                    <th>Km</th>
                    <th>Syfte</th>
                    <th>Typ</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {trips.map(t => (
                    <tr key={t.id}>
                      <td>{fmtLocal(t.started_at)}</td>
                      <td>{t.ended_at ? fmtLocal(t.ended_at) : <span className="badge badge-active">Pågår</span>}</td>
                      <td><strong>{t.vehicle_reg}</strong></td>
                      <td>{t.driver_name || ''}</td>
                      <td>{t.start_address || ''}</td>
                      <td>{t.end_address || ''}</td>
                      <td>{t.start_odometer_km ?? '–'}</td>
                      <td>{t.ended_at ? (t.end_odometer_km ?? '–') : '–'}</td>
                      <td><strong>{t.ended_at ? (t.distance_km ?? '–') : '–'}</strong></td>
                      <td>{t.purpose || ''}</td>
                      <td><span className={`badge ${t.business ? 'badge-business' : 'badge-private'}`}>{t.business ? 'Tjänst' : 'Privat'}</span></td>
                      <td><button className="btn btn-ghost btn-sm" onClick={() => loadTripIntoEditor(t)}>Redigera</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="trip-list-mobile">
              {trips.map(t => (
                <div key={t.id} className={`trip-card ${!t.ended_at ? 'trip-card-active' : ''}`}>
                  <div className="trip-card-row">
                    <span className="trip-card-date">
                      {fmtDate(t.started_at)} {fmtTime(t.started_at)}
                      {t.ended_at ? ` → ${fmtTime(t.ended_at)}` : ''}
                    </span>
                    <span className={`badge ${t.business ? 'badge-business' : 'badge-private'}`}>
                      {t.business ? 'Tjänst' : 'Privat'}
                    </span>
                  </div>
                  <div className="trip-card-row">
                    <span className="trip-card-km">
                      {t.ended_at
                        ? (t.distance_km != null ? `${t.distance_km} km` : '–')
                        : <span className="badge badge-active">Pågår</span>
                      }
                    </span>
                    <span className="trip-card-detail">{t.vehicle_reg}</span>
                  </div>
                  {t.purpose && <div className="trip-card-purpose">{t.purpose}</div>}
                  {(t.start_address || t.end_address) && (
                    <div className="trip-card-addresses">
                      {t.start_address || '?'} → {t.end_address || '?'}
                    </div>
                  )}
                  <div className="trip-card-row" style={{ marginTop: 8 }}>
                    <span className="text-xs text-light">
                      {t.start_odometer_km ?? '–'} → {t.ended_at ? (t.end_odometer_km ?? '–') : '–'}
                      {t.driver_name ? ` · ${t.driver_name}` : ''}
                    </span>
                    <button className="btn btn-ghost btn-sm" onClick={() => loadTripIntoEditor(t)}>Redigera</button>
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
