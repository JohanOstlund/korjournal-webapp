'use client';
import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isActive = (path: string) => pathname === path ? 'active' : '';

  return (
    <html lang="sv">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Körjournal</title>
      </head>
      <body>
        <nav className="nav">
          <Link href="/" className={isActive('/')}>Resor</Link>
          <Link href="/templates" className={isActive('/templates')}>Mallar</Link>
          <Link href="/settings" className={isActive('/settings')}>Inställningar</Link>
          <Link href="/admin" className={isActive('/admin')}>Admin</Link>
        </nav>
        <main className="main-container">{children}</main>
      </body>
    </html>
  );
}
