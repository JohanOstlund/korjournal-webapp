export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body className="max-w-3xl mx-auto p-6 font-sans">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: 24, fontWeight: 700 }}>Körjournal</h1>
          <nav style={{ display: 'flex', gap: 12 }}>
            <a href="/" style={{ textDecoration: 'underline' }}>Resor</a>
            <a href="/settings" style={{ textDecoration: 'underline' }}>Inställningar</a>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
