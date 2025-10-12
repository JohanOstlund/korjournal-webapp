'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const fetchAuth = (url: string, options: RequestInit = {}) =>
  fetch(url, { credentials: 'include', ...options });

type Settings = {
  ha_base_url?: string | null;
  ha_token_set?: boolean;          // backend kan returnera flagga istället för token
  ha_token?: string | null;        // skickas endast vid POST/PUT från klient
  ha_odometer_entity?: string | null;
  force_domain?: string | null;
  force_service?: string | null;
  force_data_json?: any;
};

export default function SettingsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const [haUrl, setHaUrl] = useState('');
  const [haEntity, setHaEntity] = useState('');
  const [haTokenInput, setHaTokenInput] = useState(''); // skrivs in i ett password-fält
  const [haTokenAlreadySet, setHaTokenAlreadySet] = useState(false); // visa "•••" i UI
  const [forceDomain, setForceDomain] = useState('');
  const [forceService, setForceService] = useState('');
  const [forceDataJson, setForceDataJson] = useState(''); // JSON som text

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
      setForceDataJson(s.force_data_json ? JSON.stringify(s.force_data_json, null, 2) : '');
      setStatus('Inställningar laddade.');
    } catch (e: any) {
      setStatus(`Fel vid laddning: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  const saveSettings = async () => {
    const payload: any = {
      ha_base_url: haUrl || null,
      ha_odometer_entity: haEntity || null,
      force_domain: forceDomain || null,
      force_service: forceService || null,
    };
    if (haTokenInput.trim().length > 0) {
      payload.ha_token = haTokenInput.trim();
    }
    // Parsa JSON om ifyllt
    if (forceDataJson.trim().length > 0) {
      try {
        payload.force_data_json = JSON.parse(forceDataJson.trim());
      } catch (e) {
        alert('Ogiltigt JSON-format i Force Data. Kontrollera syntaxen.');
        return;
      }
    } else {
      payload.force_data_json = null;
    }

    const r = await fetchAuth(`${API}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      alert(`Kunde inte spara inställningar: ${txt}`);
      return;
    }
    setHaTokenInput('');
    setStatus('Inställningar sparade!');
    await loadSettings();
  };

  const testPoll = async () => {
    try {
      const r = await fetchAuth(`${API}/integrations/home-assistant/poll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        headers: { 'Content-Type': 'application/json' },
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

      <div style={{ display:'grid', gap:12, maxWidth: 620 }}>
        <h2 style={{ fontSize: 18, marginTop: 16, marginBottom: 0 }}>Home Assistant Konfiguration</h2>
        <p style={{ fontSize: 14, color: '#666', marginTop: 0 }}>
          Konfigurera din egen Home Assistant-instans för automatisk odometer-hämtning.
        </p>

        <label>
          Home Assistant URL
          <input
            placeholder="t.ex. http://homeassistant.local:8123"
            value={haUrl}
            onChange={e=>setHaUrl(e.target.value)}
            style={{ marginTop: 4, padding: 8 }}
          />
        </label>

        <label>
          HA Token (lagras säkert)
          <input
            type="password"
            placeholder={haTokenAlreadySet ? '••••••••' : 'klistra in token'}
            value={haTokenInput}
            onChange={e=>setHaTokenInput(e.target.value)}
            style={{ marginTop: 4, padding: 8 }}
          />
          <div style={{ fontSize:12, color:'#666', marginTop: 4 }}>
            {haTokenAlreadySet
              ? 'En token finns redan lagrad. Lämna tomt för att behålla.'
              : 'Ingen token lagrad ännu.'}
          </div>
        </label>

        <label>
          Odometer Entity-ID
          <input
            placeholder="t.ex. sensor.kia_niro_odometer"
            value={haEntity}
            onChange={e=>setHaEntity(e.target.value)}
            style={{ marginTop: 4, padding: 8 }}
          />
          <div style={{ fontSize:12, color:'#666', marginTop: 4 }}>
            Entitet som innehåller din bils mätarställning.
          </div>
        </label>

        <h3 style={{ fontSize: 16, marginTop: 16, marginBottom: 0 }}>Force Update Inställningar</h3>
        <p style={{ fontSize: 14, color: '#666', marginTop: 0 }}>
          Avancerade inställningar för att tvinga Home Assistant att uppdatera mätarställning.
        </p>

        <label>
          Force Domain
          <input
            placeholder="t.ex. kia_uvo"
            value={forceDomain}
            onChange={e=>setForceDomain(e.target.value)}
            style={{ marginTop: 4, padding: 8 }}
          />
          <div style={{ fontSize:12, color:'#666', marginTop: 4 }}>
            Domain för force update service. Standard: kia_uvo
          </div>
        </label>

        <label>
          Force Service
          <input
            placeholder="t.ex. force_update"
            value={forceService}
            onChange={e=>setForceService(e.target.value)}
            style={{ marginTop: 4, padding: 8 }}
          />
          <div style={{ fontSize:12, color:'#666', marginTop: 4 }}>
            Service-namn för force update. Standard: force_update
          </div>
        </label>

        <label>
          Force Data (JSON)
          <textarea
            placeholder='{"entity_id":"sensor.kia_uvo_odometer"}'
            value={forceDataJson}
            onChange={e=>setForceDataJson(e.target.value)}
            rows={4}
            style={{ marginTop: 4, padding: 8, fontFamily: 'monospace', fontSize: 13 }}
          />
          <div style={{ fontSize:12, color:'#666', marginTop: 4 }}>
            JSON-data som skickas till force update service. Exempel: {`{"entity_id":"sensor.kia_uvo_odometer"}`}
          </div>
        </label>

        <div style={{ display:'flex', gap:8, marginTop:8, flexWrap: 'wrap' }}>
          <button onClick={saveSettings} disabled={loading} style={{ padding: '8px 16px' }}>Spara</button>
          <button onClick={loadSettings} disabled={loading} style={{ padding: '8px 16px' }}>Ladda om</button>
          <button onClick={testPoll} type="button" style={{ padding: '8px 16px' }}>Testa Poll</button>
          <button onClick={testForce} type="button" style={{ padding: '8px 16px' }}>Testa Force</button>
        </div>
      </div>

      <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
        API: <code>{API}</code> — {status}
      </div>
    </div>
  );
}
