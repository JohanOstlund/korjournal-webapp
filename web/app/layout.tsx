'use client';
import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === '/login';
  const isActive = (path: string) => pathname === path ? 'active' : '';

  const doLogout = async () => {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  };

  return (
    <html lang="sv">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Körjournal</title>
      </head>
      <body>
        {!isLogin && (
          <nav className="nav">
            <Link href="/" className={isActive('/')}>Resor</Link>
            <Link href="/templates" className={isActive('/templates')}>Mallar</Link>
            <Link href="/reseavdrag" className={isActive('/reseavdrag')}>Milersättning</Link>
            <Link href="/settings" className={isActive('/settings')}>Inställningar</Link>
            <Link href="/admin" className={isActive('/admin')}>Admin</Link>
            <button onClick={doLogout} className="nav-logout">Logga ut</button>
          </nav>
        )}
        <main className="main-container">{children}</main>
      </body>
    </html>
  );
}
