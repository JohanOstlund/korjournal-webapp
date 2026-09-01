'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export function Nav() {
  const pathname = usePathname();
  if (pathname === '/login') return null;

  const isActive = (path: string) => (pathname === path ? 'active' : '');

  const doLogout = async () => {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  };

  return (
    <nav className="nav">
      <Link href="/" className={isActive('/')}>Resor</Link>
      <Link href="/templates" className={isActive('/templates')}>Mallar</Link>
      <Link href="/reseavdrag" className={isActive('/reseavdrag')}>Milersättning</Link>
      <Link href="/settings" className={isActive('/settings')}>Inställningar</Link>
      <Link href="/admin" className={isActive('/admin')}>Admin</Link>
      <button onClick={doLogout} className="nav-logout">Logga ut</button>
    </nav>
  );
}
