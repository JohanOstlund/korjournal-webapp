'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

type HASettings = {
  base_url?: string;
  entity_id?: string;
  force_domain: string;
  force_service: string;
  has_token: boolean;
  token_last4?: string | null;
};

export default function SettingsPage() {
  const [s, setS] = useState<HASettings | null>(null);
  const [form, setForm] = useState({
    base_url: '',
    entity_id: '',
    token: '', // aldrig visad i klartext efter spar
    force_domain: 'kia_uvo',
    force_service: 'force_update',
    force_data_json: '' as string, // JSON text
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string>('');

  const load = async () => {
    const r = await fetch(`${API}/settings/ha`);
    if (!r.ok) {
      setMsg(`Kunde inte läsa inställningar: ${r.status}`);
      return;
    }
    const data: HASettings = await r.json();
    setS(data);
    setForm(f => ({
      ...f,
      base_url: data.base_url || '',
      entity_id: data.entity_id || '',
      force_domain: data.force_domain,
      force_service: data.force_service,
      // token fylls INTE i (syns aldrig). Vill man byta, skriver man nytt värde.
      force_data_json: '',
    }));
  };

  useEffect(() => { load(); }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setMsg('');
    try {
      let parsed: any = undefined;
      if (form.force_data_json.trim()) {
        try { parsed = JSON.parse(form.force_data_json); }
        catch { alert('force_data_json är inte giltig JSON'); return; }
      }
      const body: any = {
        base_url: form.base_url || null,
        entity_id: form.entity_id || null,
        force_domain: form.force_domain || null,
        force_service: form.force_service || null,
        force_data_json: parsed ?? null,
      };
      if (form.token.trim()) body.token = form.token.trim(); // skickas bara om användaren matat in nytt

      const r = await fetch(`${API}/settings/ha`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) { alert(await r.text()); return; }
      await load();
      // rensa tokenfältet direkt så det inte ligger kvar i minnet/UI
      setForm(f => ({ ...f, token: '' }));
      setMsg('Inställningar sparade.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700 }}>Home Assistant-inställningar</h2>
      {s && (
        <p style={{ color: '#555' }}>
          Token: {s.has_token ? `sparad (••••${s.token_last4 || ''})` : 'ej sparad'}
        </p>
      )}

      <form onSubmit={save} style={{ display: 'grid', gap: 10, marginTop: 12, maxWidth: 560 }}>
        <label>
          HA Base URL
          <input placeholder="http://homeassistant.local:8123"
                 value={form.base_url}
                 onChange={e=>setForm({...form, base_url: e.target.value})} />
        </label>

        <label>
          Odometer entity_id
          <input placeholder="sensor.kia_uvo_odometer"
                 value={form.entity_id}
                 onChange={e=>setForm({...form, entity_id: e.target.value})} />
        </label>

        <label>
          Long-Lived Token (lagras säkert – visas aldrig)
          <input
            type="password"
            placeholder="Klistra in nytt om du vill byta"
            value={form.token}
            onChange={e=>setForm({...form, token: e.target.value})}
          />
        </label>

        <label>
          Force Update – domain
          <input value={form.force_domain}
                 onChange={e=>setForm({...form, force_domain: e.target.value})} />
        </label>
        <label>
          Force Update – service
          <input value={form.force_service}
                 onChange={e=>setForm({...form, force_service: e.target.value})} />
        </label>
        <label>
          Force Update – data (JSON, valfritt)
          <textarea placeholder='{"entity_id":"sensor.kia_uvo_odometer"}'
                    value={form.force_data_json}
                    onChange={e=>setForm({...form, force_data_json: e.target.value})} />
        </label>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button type="submit" disabled={saving}>{saving ? 'Sparar…' : 'Spara'}</button>
          {msg && <span>{msg}</span>}
        </div>
      </form>

      <p style={{ marginTop: 16, color: '#666' }}>
        Tips: Om du kör via Docker env-variabler (HA_BASE_URL, HA_TOKEN, HA_ODOMETER_ENTITY, etc) så används de med högre prioritet än dessa inställningar.
      </p>
    </div>
  );
}