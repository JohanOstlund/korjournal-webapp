'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

type Settings = {
  ha_base_url?: string | null;
  ha_token_set?: boolean;          // backend kan returnera flagga istället för token
  ha_token?: string | null;        // skickas endast vid POST/PUT från klient
  ha_odometer_entity?: string | null;
};

export default function SettingsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const [haUrl, setHaUrl] = useState('');
  const [haEntity, setHaEntity] = useState('');
  const [haTokenInput, setHaTokenInput] = useState(''); // skrivs in i ett password-fält
  const [haTokenAlreadySet, setHaTokenAlreadySet] = useState(false); // visa “•••” i UI

  const loadSettings = async () => {
    try {
      setLoading(true);
      const r = await fetch(`${API}/settings?_ts=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`GET /settings ${r.status}`);
      const s = (await r.json()) as Settings;
      setHaUrl((s.ha_base_url || '') as string);
      setHaEntity((s.ha_odometer_entity || '') as string);
      setHaTokenAlreadySet(!!s.ha_token_set); // om backend exponerar detta
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
    };
    // Skicka endast token om användaren angett något nytt
    if (haTokenInput.trim().length > 0) {
      payload.ha_token = haTokenInput.trim();
    }

    const r = await fetch(`${API}/settings`, {
      method: 'PUT', // eller POST beroende på ditt API; byt om nödvändigt
      headers: { 'Content-Type': 'application/json' },
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
      const r = await fetch(`${API}/integrations/home-assistant/poll`, {
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
      const r = await fetch(`${API}/integrations/home-assistant/force-update-and-poll`, {
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

      <div style={{ display:'grid', gap:8, maxWidth: 520 }}>
        <label>
          Home Assistant URL
          <input
            placeholder="t.ex. http://homeassistant.local:8123"
            value={haUrl}
            onChange={e=>setHaUrl(e.target.value)}
          />
        </label>

        <label>
          Odometer Entity-ID
          <input
            placeholder="t.ex. sensor.kia_niro_odometer"
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
