'use client';
import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const fetchAuth = (url: string, options: RequestInit = {}) =>
  fetch(url, { credentials: 'include', ...options });

type User = {
  id: number;
  username: string;
};

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string>('');

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [creating, setCreating] = useState(false);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const r = await fetchAuth(`${API}/admin/users`, { cache: 'no-store' });
      if (!r.ok) {
        if (r.status === 403) { setError('Du har inte admin-behörighet'); return; }
        throw new Error(`GET /admin/users ${r.status}`);
      }
      const data = (await r.json()) as User[];
      setUsers(data);
      setStatus(`${data.length} användare`);
    } catch (e: any) {
      setError(`Fel: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) { alert('Båda fält krävs'); return; }
    if (newPassword.length < 8) { alert('Lösenord måste vara minst 8 tecken'); return; }
    try {
      setCreating(true);
      setError('');
      const r = await fetchAuth(`${API}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: newUsername.trim(), password: newPassword }),
      });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte skapa användare: ${txt}`); return; }
      setNewUsername('');
      setNewPassword('');
      setStatus('Användare skapad!');
      await loadUsers();
    } catch (e: any) {
      setError(`Fel: ${e?.message || e}`);
    } finally {
      setCreating(false);
    }
  };

  const deleteUser = async (userId: number, username: string) => {
    if (!confirm(`Är du säker på att du vill ta bort "${username}"?`)) return;
    try {
      setError('');
      const r = await fetchAuth(`${API}/admin/users/${userId}`, { method: 'DELETE' });
      if (!r.ok) { const txt = await r.text(); alert(`Kunde inte ta bort: ${txt}`); return; }
      setStatus(`"${username}" borttagen`);
      await loadUsers();
    } catch (e: any) {
      setError(`Fel: ${e?.message || e}`);
    }
  };

  return (
    <div>
      <h1>Admin</h1>

      {error && <div className="alert-error">{error}</div>}

      {/* Create user */}
      <div className="card">
        <div className="card-header">Skapa ny användare</div>
        <form onSubmit={createUser}>
          <div className="form-grid">
            <div className="field">
              <span className="field-label">Användarnamn</span>
              <input type="text" value={newUsername} onChange={e => setNewUsername(e.target.value)} required />
            </div>
            <div className="field">
              <span className="field-label">Lösenord (minst 8 tecken)</span>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required minLength={8} />
            </div>
          </div>
          <div className="mt-16">
            <button className="btn btn-primary" type="submit" disabled={creating}>
              {creating ? 'Skapar…' : 'Skapa användare'}
            </button>
          </div>
        </form>
      </div>

      {/* User list */}
      <div className="section">
        <h2>Användare <span className="text-light text-sm">({users.length})</span></h2>
        {loading ? (
          <p className="text-muted">Laddar…</p>
        ) : users.length === 0 ? (
          <p className="text-muted">Inga användare hittades</p>
        ) : (
          <>
            {/* Desktop */}
            <div className="responsive-table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Användarnamn</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td><strong>{u.username}</strong></td>
                      <td>
                        <button className="btn btn-danger btn-sm" onClick={() => deleteUser(u.id, u.username)}>Ta bort</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile */}
            <div className="responsive-cards">
              {users.map(u => (
                <div key={u.id} className="card flex-between">
                  <div>
                    <strong>{u.username}</strong>
                    <span className="text-xs text-light"> (ID: {u.id})</span>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => deleteUser(u.id, u.username)}>Ta bort</button>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="status-bar">{status}</div>
    </div>
  );
}
