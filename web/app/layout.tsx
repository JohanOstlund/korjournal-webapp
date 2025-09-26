'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const linkStyle = (path: string) => ({
    padding: '8px 12px',
    borderRadius: 6,
    textDecoration: 'none',
    color: pathname === path ? '#fff' : '#333',
    background: pathname === path ? '#0070f3' : 'transparent',
  });
  return (
    <html lang="sv">
      <body style={{ fontFamily: 'system-ui, sans-serif', margin: 0 }}>
        <nav style={{ display:'flex', gap:12, padding:12, borderBottom:'1px solid #eee' }}>
          <Link href="/" style={linkStyle('/')}>Resor</Link>
          <Link href="/templates" style={linkStyle('/templates')}>Mallar</Link>
          <Link href="/settings" style={linkStyle('/settings')}>Inställningar</Link>
        </nav>
        <main style={{ padding:16 }}>{children}</main>
      </body>
    </html>
  );
}
