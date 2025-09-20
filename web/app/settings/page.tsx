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
    token: '',
    force_domain: 'kia_uvo',
    force_service: 'force_update',
    force_data_json: '' as string,
  });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{type:'ok'|'err', text:string} | null>(null);

  const showNotice = (type:'ok'|'err', text:string) => {
    setNotice({type, text});
    setTimeout(()=> setNotice(null), 4000);
  };

  const load = async () => {
    const r = await fetch(`${API}/settings/ha`);
    if (!r.ok) { showNotice('err', `Kunde inte läsa inställningar (${r.status})`); return; }
    const data: HASettings = await r.json();
    setS(data);
    setForm(f => ({
      ...f,
      base_url: data.base_url || '',
      entity_id: data.entity_id || '',
      force_domain: data.force_domain,
      force_service: data.force_service,
      force_data_json: '',
    }));
  };

  useEffect(() => { load(); }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      let parsed: any = undefined;
      if (form.force_data_json.trim()) {
        try { parsed = JSON.parse(form.force_data_json); }
        catch { showNotice('err','force_data_json är inte giltig JSON'); return; }
      }
      const body: any = {
        base_url: form.base_url || null,
        entity_id: form.entity_id || null,
        force_domain: form.force_domain || null,
        force_service: form.force_service || null,
        force_data_json: parsed ?? null,
      };
      if (form.token.trim()) body.token = form.token.trim();

      const r = await fetch(`${API}/settings/ha`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) { showNotice('err', `Sparning misslyckades (${r.status})`); return; }
      await load();
      setForm(f => ({ ...f, token: '' }));
      showNotice('ok','Inställningar sparade.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700 }}>Home Assistant-inställningar</h2>

      {notice && (
        <div style={{
          marginTop: 12, padding: '8px 12px',
          background: notice.type === 'ok' ? '#e6f6ec' : '#fdecea',
          color: notice.type === 'ok' ? '#067647' : '#b3261e',
          border: `1px solid ${notice.type === 'ok' ? '#95d5b2' : '#f5c2c0'}`,
          borderRadius: 8
        }}>
          {notice.text}
        </div>
      )}

      {s && (
        <p style={{ color: '#555', marginTop: 8 }}>
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
          <input type="password"
                 placeholder="Klistra in nytt om du vill byta"
                 value={form.token}
                 onChange={e=>setForm({...form, token: e.target.value})} />
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
        </div>
      </form>
    </div>
  );
}