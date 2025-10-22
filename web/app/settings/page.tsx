'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// >>> NYTT: hjälpare som alltid skickar cookies <<<
async function fetchAuth(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(input, { credentials: 'include', ...init, headers });
}

type Settings = {
  ha_base_url?: string | null;
  ha_token_set?: boolean;
  ha_token?: string | null;
  ha_odometer_entity?: string | null;
  force_domain?: string | null;
  force_service?: string | null;
  force_data_json?: Record<string, any> | null;
};

export default function SettingsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const [haUrl, setHaUrl] = useState('');
  const [haEntity, setHaEntity] = useState('');
  const [haTokenInput, setHaTokenInput] = useState('');
  const [haTokenAlreadySet, setHaTokenAlreadySet] = useState(false);

  const [forceDomain, setForceDomain] = useState('');
  const [forceService, setForceService] = useState('');
  const [forceDataJson, setForceDataJson] = useState('');

  const loadSettings = async () => {
    try {
      setLoading(true);
      const r = await fetchAuth(`${API}/settings?_ts=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`GET /settings ${r.status}`);
      const s = (await r.json()) as Settings;
      setHaUrl((s.ha_base_url || '') as string);
      setHaEntity((s.ha_odometer_entity || '') as string);
      setHaTokenAlreadySet(!!s.ha_token_set);
      setForceDomain((s.force_domain || '') as string);
      setForceService((s.force_service || '') as string);
      setForceDataJson(s.force_data_json ? JSON.stringify(s.force_data_json) : '');
      setStatus('Inställningar laddade.');
    } catch (e: any) {
      setStatus(`Fel vid laddning: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  const saveSettings = async () => {
    let parsed: any = undefined;
    if (forceDataJson.trim()) {
      try { parsed = JSON.parse(forceDataJson.trim()); }
      catch { alert('force_data_json är inte giltig JSON'); return; }
    }
    const payload: any = {
      ha_base_url: haUrl || null,
      ha_odometer_entity: haEntity || null,
      force_domain: forceDomain || null,
      force_service: forceService || null,
      force_data_json: parsed || null,
    };
    if (haTokenInput.trim().length > 0) {
      payload.ha_token = haTokenInput.trim();
    }

    const r = await fetchAuth(`${API}/settings`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte spara inställningar: ${txt}`);
      return;
    }
    setHaTokenInput('');
    await loadSettings();
  };

  const testPoll = async () => {
    try {
      const r = await fetchAuth(`${API}/integrations/home-assistant/poll`, {
        method: 'POST',
        body: JSON.stringify({ vehicle_reg: 'TEST' }),
      });
      const data = await r.json();
      alert(r.ok ? `Poll OK: ${JSON.stringify(data)}` : `Poll FEL: ${JSON.stringify(data)}`);
    } catch (e: any) {
      alert(`Poll FEL: ${e?.message || e}`);
    }
  };

  const testForce = async () => {
    try {
      const r = await fetchAuth(`${API}/integrations/home-assistant/force-update-and-poll`, {
        method: 'POST',
        body: JSON.stringify({ vehicle_reg: 'TEST' }),
      });
      const data = await r.json();
      alert(r.ok ? `Force OK: ${JSON.stringify(data)}` : `Force FEL: ${JSON.stringify(data)}`);
    } catch (e: any) {
      alert(`Force FEL: ${e?.message || e}`);
    }
  };

  return (
    <div>
      <h1>Inställningar</h1>

      <div style={{ display:'grid', gap:8, maxWidth: 520 }}>
        <label>
          Home Assistant URL
          <input
            placeholder="t.ex. https://ha.example.com"
            value={haUrl}
            onChange={e=>setHaUrl(e.target.value)}
          />
        </label>

        <label>
          Odometer Entity-ID
          <input
            placeholder="sensor.kia_niro_odometer"
            value={haEntity}
            onChange={e=>setHaEntity(e.target.value)}
          />
        </label>

        <label>
          HA Token (lagras säkert)
          <input
            type="password"
            placeholder={haTokenAlreadySet ? '••••••••' : 'klistra in token'}
            value={haTokenInput}
            onChange={e=>setHaTokenInput(e.target.value)}
          />
          <div style={{ fontSize:12, color:'#666' }}>
            {haTokenAlreadySet
              ? 'En token finns redan lagrad. Lämna tomt för att behålla.'
              : 'Ingen token lagrad ännu.'}
          </div>
        </label>

        <label>
          Force domain (t.ex. kia_uvo)
          <input value={forceDomain} onChange={e=>setForceDomain(e.target.value)} />
        </label>
        <label>
          Force service (t.ex. force_update)
          <input value={forceService} onChange={e=>setForceService(e.target.value)} />
        </label>
        <label>
          Force data JSON
          <textarea
            rows={4}
            placeholder='{"vin":"..."}'
            value={forceDataJson}
            onChange={e=>setForceDataJson(e.target.value)}
          />
        </label>

        <div style={{ display:'flex', gap:8, marginTop:8 }}>
          <button onClick={saveSettings} disabled={loading}>Spara</button>
          <button onClick={loadSettings} disabled={loading}>Ladda om</button>
          <button onClick={testPoll} type="button">Testa Poll</button>
          <button onClick={testForce} type="button">Testa Force</button>
        </div>
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
        API: <code>{API}</code> — {status}
      </div>
    </div>
  );
}
