'use client';
import { useEffect, useRef, useState } from 'react';

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

  // QR modal state
  const [qrOpen, setQrOpen] = useState(false);
  const [qrError, setQrError] = useState<string>('');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const stopScanRef = useRef<null | (() => void)>(null);

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

  // --- QR scanning ---
  const openQr = async () => {
    setQrError('');
    setQrOpen(true);
    // dynamisk import så SSR inte krånglar
    const { BrowserMultiFormatReader } = await import('@zxing/browser');

    try {
      const codeReader = new BrowserMultiFormatReader();
      const video = videoRef.current;
      if (!video) return;

      // välj bakre kamera om möjligt
      const devices = await BrowserMultiFormatReader.listVideoInputDevices();
      const backCam = devices.find(d => /back|rear|environment/i.test(`${d.label}`));
      const deviceId = backCam?.deviceId || devices[0]?.deviceId;
      if (!deviceId) throw new Error('Ingen kamera hittades');

      const controls = await codeReader.decodeFromVideoDevice(deviceId, video, (result, err) => {
        if (result) {
          let text = result.getText()?.trim() || '';
          if (text.startsWith('HA_TOKEN:')) {
            text = text.replace(/^HA_TOKEN:/, '').trim();
          }
          if (text) {
            setForm(f => ({ ...f, token: text }));
            closeQr();
          }
        } else if (err) {
          // ignorera enstaka decodefel; sätt bara fel vid kamera/tillståndsproblem
        }
      });
      stopScanRef.current = () => controls?.stop();
    } catch (e: any) {
      setQrError(e?.message || 'Kunde inte starta kamera/QR-läsning');
    }
  };

  const closeQr = () => {
    stopScanRef.current?.();
    stopScanRef.current = null;
    setQrOpen(false);
  };

  const onImagePicked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { BrowserQRCodeReader } = await import('@zxing/browser');
      const reader = new BrowserQRCodeReader();
      const url = URL.createObjectURL(file);
      const res = await reader.decodeFromImageUrl(url);
      URL.revokeObjectURL(url);
      let text = res.getText()?.trim() || '';
      if (text.startsWith('HA_TOKEN:')) text = text.replace(/^HA_TOKEN:/, '').trim();
      if (text) {
        setForm(f => ({ ...f, token: text }));
        setMsg('Token läst från bild.');
      } else {
        setMsg('Ingen token hittades i bilden.');
      }
    } catch (err: any) {
      setMsg('Kunde inte läsa QR från bild.');
    }
    // rensa file input
    e.currentTarget.value = '';
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

        <div style={{ display: 'grid', gap: 6 }}>
          <label>
            Long-Lived Token (lagras säkert – visas aldrig)
            <input
              type="password"
              placeholder="Skriv eller skanna QR"
              value={form.token}
              onChange={e=>setForm({...form, token: e.target.value})}
            />
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={openQr}>Skanna QR</button>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span>Läs från bild</span>
              <input type="file" accept="image/*" onChange={onImagePicked} />
            </label>
          </div>
          <small style={{ color: '#666' }}>
            Tips: QR kan innehålla bara token, eller formatet <code>HA_TOKEN:&lt;din-token&gt;</code>.
            Kamera kräver HTTPS på publik domän (eller fungerar på <code>localhost</code>).
          </small>
        </div>

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

      {/* QR Modal */}
      {qrOpen && (
        <div style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.5)',
          display:'grid', placeItems:'center', zIndex: 50
        }}>
          <div style={{ background:'#fff', padding:16, borderRadius:12, width:'min(92vw, 480px)' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
              <strong>Skanna token-QR</strong>
              <button onClick={closeQr}>Stäng</button>
            </div>
            <div style={{ aspectRatio:'4 / 3', background:'#000', borderRadius:8, overflow:'hidden' }}>
              <video ref={videoRef} style={{ width:'100%', height:'100%', objectFit:'cover' }} />
            </div>
            {qrError && <p style={{ color:'crimson', marginTop:8 }}>{qrError}</p>}
            <p style={{ color:'#666', marginTop:8 }}>
              Rikta kameran mot QR-koden. Token fylls automatiskt och visas inte i klartext.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}