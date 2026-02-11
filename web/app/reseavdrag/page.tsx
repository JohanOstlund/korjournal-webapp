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
};

/* Decimal-safe input */
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

// --- Constants ---
const SCHABLON: Record<string, number> = {
  egen_bil: 25,
  formansbil_el: 9.5,
  formansbil_fossil: 12,
};
const SCHABLON_LABEL: Record<string, string> = {
  egen_bil: 'Egen bil (25 kr/mil)',
  formansbil_el: 'Förmånsbil elbil (9,50 kr/mil)',
  formansbil_fossil: 'Förmånsbil fossil (12 kr/mil)',
};
const AVDRAGSGRANS = (year: number) => year >= 2026 ? 15_000 : 11_000;
const SKIKTGRANS = (year: number) => year >= 2026 ? 643_000 : 625_800;

type VehicleType = 'egen_bil' | 'formansbil_el' | 'formansbil_fossil';

type Settings = {
  vehicleType: VehicleType;
  monthlySalary: number | null;
  municipalTax: number | null;
  evKwhPerMil: number | null;
  electricityPrice: number | null;
  fuelLPerMil: number | null;
  fuelPrice: number | null;
  purposeFilter: string;
};

const DEFAULT_SETTINGS: Settings = {
  vehicleType: 'egen_bil',
  monthlySalary: null,
  municipalTax: 32,
  evKwhPerMil: 1.8,
  electricityPrice: 2,
  fuelLPerMil: 0.6,
  fuelPrice: 18,
  purposeFilter: 'Pendling',
};

const STORAGE_KEY = 'reseavdrag-settings';

function loadSettings(): Settings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch { return DEFAULT_SETTINGS; }
}

function saveSettings(s: Settings) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
}

const fmt = (n: number, decimals = 0) =>
  n.toLocaleString('sv-SE', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const fmtKr = (n: number) => `${fmt(n)} kr`;

export default function ReseavdragPage() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(false);
  const [year, setYear] = useState(new Date().getFullYear());
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 2, y - 1, y, y + 1, y + 2];
  }, []);

  // Load settings from localStorage on mount
  useEffect(() => { setSettings(loadSettings()); }, []);

  // Save settings on change
  const updateSetting = <K extends keyof Settings>(key: K, val: Settings[K]) => {
    setSettings(prev => {
      const next = { ...prev, [key]: val };
      saveSettings(next);
      return next;
    });
  };

  // Load trips
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const r = await fetchAuth(`${API}/trips?_ts=${Date.now()}`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`${r.status}`);
        setTrips(await r.json());
      } catch (e) {
        console.error('Kunde inte ladda resor', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Filter and compute
  const calc = useMemo(() => {
    const filter = settings.purposeFilter.trim().toLowerCase();

    // Filter trips for selected year + matching purpose
    const matching = trips.filter(t => {
      if (!t.ended_at || t.distance_km == null) return false;
      const d = new Date(t.started_at);
      if (d.getFullYear() !== year) return false;
      if (!filter) return t.business; // no filter = all business trips
      return (t.purpose || '').toLowerCase().includes(filter);
    });

    // Stats
    const totalKm = matching.reduce((sum, t) => sum + (t.distance_km ?? 0), 0);
    const totalMil = totalKm / 10;
    const days = new Set(matching.map(t => t.started_at.slice(0, 10))).size;

    // Odometer range
    const withOdo = matching.filter(t => t.start_odometer_km != null || t.end_odometer_km != null);
    const sorted = [...withOdo].sort((a, b) => a.started_at.localeCompare(b.started_at));
    const firstTrip = sorted[0] as Trip | undefined;
    const lastTrip = sorted[sorted.length - 1] as Trip | undefined;
    const odoStart = firstTrip?.start_odometer_km ?? null;
    const odoEnd = lastTrip?.end_odometer_km ?? null;

    // Schablon
    const schablonPerMil = SCHABLON[settings.vehicleType] ?? 25;
    const schablonTotal = totalMil * schablonPerMil;
    const avdragsgrans = AVDRAGSGRANS(year);
    const avdragsbelopp = Math.max(0, schablonTotal - avdragsgrans);

    // Marginalskatt
    const arsilon = (settings.monthlySalary ?? 0) * 12;
    const skiktgrans = SKIKTGRANS(year);
    const kommunalskatt = (settings.municipalTax ?? 32) / 100;
    const harStatligSkatt = arsilon > skiktgrans + 100_000; // förenklad grundavdragskompensation
    const marginalskatt = kommunalskatt + (harStatligSkatt ? 0.20 : 0);
    const skattebesparing = avdragsbelopp * marginalskatt;

    // Drivmedelskostnad
    let drivmedelskostnad = 0;
    if (settings.vehicleType === 'formansbil_fossil') {
      drivmedelskostnad = totalMil * (settings.fuelLPerMil ?? 0) * (settings.fuelPrice ?? 0);
    } else {
      // Egen bil och förmånsbil elbil → elbilskostnad
      drivmedelskostnad = totalMil * (settings.evKwhPerMil ?? 0) * (settings.electricityPrice ?? 0);
    }

    const netto = skattebesparing - drivmedelskostnad;

    return {
      matching,
      totalKm,
      totalMil,
      days,
      odoStart,
      odoEnd,
      schablonPerMil,
      schablonTotal,
      avdragsgrans,
      avdragsbelopp,
      arsilon,
      marginalskatt,
      harStatligSkatt,
      skattebesparing,
      drivmedelskostnad,
      netto,
    };
  }, [trips, year, settings]);

  const csvUrl = `${API}/exports/journal.csv?year=${year}`;
  const pdfUrl = `${API}/exports/journal.pdf?year=${year}`;

  return (
    <div>
      <h1>Milersättning {year}</h1>

      {/* Year selector */}
      <div className="toolbar">
        <div className="field">
          <span className="field-label">Inkomstår</span>
          <select value={year} onChange={e => setYear(Number(e.target.value))} style={{ width: 120 }}>
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

      {/* Stat cards */}
      <div className="stat-cards section">
        <div className="stat-card">
          <div className="stat-card-value">{calc.days}</div>
          <div className="stat-card-label">Pendlingsdagar</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value">{fmt(calc.totalMil, 1)}</div>
          <div className="stat-card-label">Mil totalt</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value">{fmtKr(calc.avdragsbelopp)}</div>
          <div className="stat-card-label">Avdrag (ruta 2.1)</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value" style={{ color: calc.netto >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {calc.netto >= 0 ? '+' : ''}{fmtKr(Math.round(calc.netto))}
          </div>
          <div className="stat-card-label">Nettoeffekt</div>
        </div>
      </div>

      {loading && <p className="text-muted section">Laddar resor…</p>}

      {/* Beräkning */}
      <div className="card section">
        <div className="card-header">Skatteverkets beräkning</div>
        <dl className="summary-grid">
          <dt>Körsträcka</dt>
          <dd>{fmt(calc.totalKm, 1)} km ({fmt(calc.totalMil, 1)} mil)</dd>

          <dt>Schablon ({SCHABLON_LABEL[settings.vehicleType]})</dt>
          <dd>{fmt(calc.totalMil, 1)} mil &times; {calc.schablonPerMil} kr = {fmtKr(Math.round(calc.schablonTotal))}</dd>

          <dt>Avdragsgräns ({year <= 2025 ? '2025' : '2026+'})</dt>
          <dd>&minus;{fmtKr(calc.avdragsgrans)}</dd>

          <hr className="summary-divider" />

          <dt className="summary-highlight">Avdragsbelopp (ruta 2.1)</dt>
          <dd className="summary-highlight">{fmtKr(calc.avdragsbelopp)}</dd>
        </dl>
      </div>

      {/* Skattebesparing */}
      <div className="card section">
        <div className="card-header">Din skattebesparing</div>
        <dl className="summary-grid">
          <dt>Årslön</dt>
          <dd>{fmtKr(calc.arsilon)}</dd>

          <dt>Marginalskatt</dt>
          <dd>{fmt(calc.marginalskatt * 100, 1)}% {calc.harStatligSkatt ? '(kommun + statlig)' : '(kommun)'}</dd>

          <dt>Skattebesparing</dt>
          <dd>{fmtKr(calc.avdragsbelopp)} &times; {fmt(calc.marginalskatt * 100, 1)}% = <strong>{fmtKr(Math.round(calc.skattebesparing))}</strong></dd>

          <hr className="summary-divider" />

          <dt>Drivmedelskostnad</dt>
          <dd>&minus;{fmtKr(Math.round(calc.drivmedelskostnad))}</dd>

          <hr className="summary-divider" />

          <dt className="summary-highlight">Nettoeffekt</dt>
          <dd className={`summary-highlight ${calc.netto >= 0 ? 'positive' : 'negative'}`}>
            {calc.netto >= 0 ? '+' : ''}{fmtKr(Math.round(calc.netto))}
          </dd>

          <dt className="text-xs text-light">Per mil</dt>
          <dd className="text-xs text-light">
            {calc.totalMil > 0
              ? `${fmt(calc.netto / calc.totalMil, 1)} kr/mil`
              : '–'}
          </dd>
        </dl>
      </div>

      {/* Skatteverket underlag */}
      <div className="card section">
        <div className="card-header">Underlag för Skatteverket</div>
        <dl className="summary-grid">
          <dt>Antal arbetsdagar med pendling</dt>
          <dd>{calc.days} dagar</dd>

          <dt>Total körsträcka</dt>
          <dd>{fmt(calc.totalMil, 1)} mil ({fmt(calc.totalKm, 1)} km)</dd>

          {calc.odoStart != null && calc.odoEnd != null && (
            <>
              <dt>Mätarställning (årets start → slut)</dt>
              <dd>{fmt(calc.odoStart, 1)} → {fmt(calc.odoEnd, 1)} km</dd>
            </>
          )}

          <dt>Antal matchade resor</dt>
          <dd>{calc.matching.length} st</dd>

          <dt>Syftefilter</dt>
          <dd>&quot;{settings.purposeFilter || '(alla tjänsteresor)'}&quot;</dd>
        </dl>
        <p className="text-xs text-light mt-12">
          Skatteverket kräver körjournal vid granskning. Exportera via knapparna ovan (CSV/PDF).
        </p>
      </div>

      {/* Inställningar (collapsible) */}
      <div className="card section">
        <div
          className={`card-toggle ${settingsOpen ? '' : 'collapsed'}`}
          onClick={() => setSettingsOpen(!settingsOpen)}
        >
          <span className="card-header" style={{ marginBottom: 0 }}>Inställningar</span>
        </div>
        {settingsOpen && (
          <div className="form-grid mt-16">
            <div className="field">
              <span className="field-label">Fordonstyp</span>
              <select
                value={settings.vehicleType}
                onChange={e => updateSetting('vehicleType', e.target.value as VehicleType)}
              >
                {Object.entries(SCHABLON_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="field-label">Månadslön (kr)</span>
              <DecimalInput
                value={settings.monthlySalary}
                onValueChange={v => updateSetting('monthlySalary', v)}
                placeholder="t.ex. 60000"
              />
            </div>
            <div className="field">
              <span className="field-label">Kommunalskattesats (%)</span>
              <DecimalInput
                value={settings.municipalTax}
                onValueChange={v => updateSetting('municipalTax', v)}
                placeholder="t.ex. 32"
              />
            </div>

            {settings.vehicleType !== 'formansbil_fossil' ? (
              <>
                <div className="field">
                  <span className="field-label">Förbrukning (kWh/mil)</span>
                  <DecimalInput
                    value={settings.evKwhPerMil}
                    onValueChange={v => updateSetting('evKwhPerMil', v)}
                    placeholder="t.ex. 1.8"
                  />
                </div>
                <div className="field">
                  <span className="field-label">Elpris (kr/kWh)</span>
                  <DecimalInput
                    value={settings.electricityPrice}
                    onValueChange={v => updateSetting('electricityPrice', v)}
                    placeholder="t.ex. 2"
                  />
                </div>
              </>
            ) : (
              <>
                <div className="field">
                  <span className="field-label">Förbrukning (l/mil)</span>
                  <DecimalInput
                    value={settings.fuelLPerMil}
                    onValueChange={v => updateSetting('fuelLPerMil', v)}
                    placeholder="t.ex. 0.6"
                  />
                </div>
                <div className="field">
                  <span className="field-label">Bränslepris (kr/l)</span>
                  <DecimalInput
                    value={settings.fuelPrice}
                    onValueChange={v => updateSetting('fuelPrice', v)}
                    placeholder="t.ex. 18"
                  />
                </div>
              </>
            )}

            <div className="field">
              <span className="field-label">Syftefilter</span>
              <input
                type="text"
                value={settings.purposeFilter}
                onChange={e => updateSetting('purposeFilter', e.target.value)}
                placeholder="t.ex. Pendling"
              />
              <span className="field-hint">Resor vars syfte matchar detta inkluderas. Tomt = alla tjänsteresor.</span>
            </div>
          </div>
        )}
      </div>

      <div className="status-bar">
        Avdragsgräns {year}: {fmtKr(AVDRAGSGRANS(year))} · Schablon: {SCHABLON[settings.vehicleType]} kr/mil ·
        Skiktgräns statlig skatt: {fmtKr(SKIKTGRANS(year))}
      </div>
    </div>
  );
}
