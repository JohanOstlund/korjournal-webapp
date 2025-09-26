'use client';
import { useState } from 'react';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const doLogin = async () => {
    setErr('');
    if (!username || !password) { setErr('Fyll i användarnamn och lösenord'); return; }
    try {
      setBusy(true);
      const r = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',               // ⬅️ viktigt för cookie
        body: JSON.stringify({ username, password }),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(txt || 'Login failed');
      }
      // Vid lyckad inloggning, gå till startsidan
      window.location.href = '/';
    } catch (e:any) {
      setErr(e.message || 'Fel vid inloggning');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 360, margin: '40px auto', padding: 16, border: '1px solid #eee', borderRadius: 8 }}>
      <h1>Logga in</h1>
      <div style={{ display:'grid', gap:8 }}>
        <label>Användarnamn
          <input value={username} onChange={e=>setUsername(e.target.value)} />
        </label>
        <label>Lösenord
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} />
        </label>
        <button onClick={doLogin} disabled={busy}>{busy ? 'Loggar in…' : 'Logga in'}</button>
        {err && <div style={{ color:'#b00020' }}>{err}</div>}
      </div>
    </div>
  );
}
