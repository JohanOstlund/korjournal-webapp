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

  // Formulär för ny användare
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [creating, setCreating] = useState(false);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const r = await fetchAuth(`${API}/admin/users`, { cache: 'no-store' });
      if (!r.ok) {
        if (r.status === 403) {
          setError('Du har inte admin-behörighet');
          return;
        }
        throw new Error(`GET /admin/users ${r.status}`);
      }
      const data = (await r.json()) as User[];
      setUsers(data);
      setStatus(`${data.length} användare laddade`);
    } catch (e: any) {
      setError(`Fel vid laddning av användare: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) {
      alert('Både användarnamn och lösenord krävs');
      return;
    }
    if (newPassword.length < 8) {
      alert('Lösenord måste vara minst 8 tecken');
      return;
    }
    try {
      setCreating(true);
      setError('');
      const r = await fetchAuth(`${API}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword,
        }),
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte skapa användare: ${txt}`);
        return;
      }
      setNewUsername('');
      setNewPassword('');
      setStatus('Användare skapad!');
      await loadUsers();
    } catch (e: any) {
      setError(`Fel vid skapande av användare: ${e?.message || e}`);
    } finally {
      setCreating(false);
    }
  };

  const deleteUser = async (userId: number, username: string) => {
    if (!confirm(`Är du säker på att du vill ta bort användaren "${username}"?`)) {
      return;
    }
    try {
      setError('');
      const r = await fetchAuth(`${API}/admin/users/${userId}`, {
        method: 'DELETE',
      });
      if (!r.ok) {
        const txt = await r.text();
        alert(`Kunde inte ta bort användare: ${txt}`);
        return;
      }
      setStatus(`Användare "${username}" borttagen`);
      await loadUsers();
    } catch (e: any) {
      setError(`Fel vid borttagning av användare: ${e?.message || e}`);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Admin - Användarhantering</h1>

      {error && (
        <div style={{ padding: 12, background: '#ffebee', color: '#c62828', borderRadius: 8, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Skapa ny användare */}
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24, background: '#fafafa' }}>
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>Skapa ny användare</h2>
        <form onSubmit={createUser} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label>
            Användarnamn
            <input
              type="text"
              value={newUsername}
              onChange={e => setNewUsername(e.target.value)}
              placeholder="användarnamn"
              style={{ marginLeft: 8, padding: 6 }}
              required
            />
          </label>
          <label>
            Lösenord (minst 8 tecken)
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="lösenord"
              style={{ marginLeft: 8, padding: 6 }}
              required
              minLength={8}
            />
          </label>
          <button type="submit" disabled={creating} style={{ padding: '6px 12px' }}>
            {creating ? 'Skapar...' : 'Skapa användare'}
          </button>
        </form>
      </div>

      {/* Lista användare */}
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Användare</h2>
      {loading ? (
        <div>Laddar...</div>
      ) : users.length === 0 ? (
        <div style={{ color: '#666' }}>Inga användare hittades</div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #ddd' }}>
              <th align="left" style={{ padding: 8 }}>ID</th>
              <th align="left" style={{ padding: 8 }}>Användarnamn</th>
              <th align="left" style={{ padding: 8 }}>Åtgärder</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: 8 }}>{u.id}</td>
                <td style={{ padding: 8 }}>{u.username}</td>
                <td style={{ padding: 8 }}>
                  <button
                    onClick={() => deleteUser(u.id, u.username)}
                    style={{ color: '#b00020', padding: '4px 8px' }}
                  >
                    Ta bort
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Statusrad */}
      <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
        {status}
      </div>
    </div>
  );
}
