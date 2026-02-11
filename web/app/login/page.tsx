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
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(txt || 'Login failed');
      }
      window.location.href = '/';
    } catch (e: any) {
      setErr(e.message || 'Fel vid inloggning');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrapper">
      <div className="card login-card">
        <h1>Körjournal</h1>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="field">
            <span className="field-label">Användarnamn</span>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)} autoFocus />
          </div>
          <div className="field">
            <span className="field-label">Lösenord</span>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doLogin()}
            />
          </div>
          <button className="btn btn-primary" onClick={doLogin} disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Loggar in…' : 'Logga in'}
          </button>
          {err && <div className="alert-error">{err}</div>}
        </div>
      </div>
    </div>
  );
}
