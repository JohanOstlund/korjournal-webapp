export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body className="max-w-3xl mx-auto p-6 font-sans">
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Körjournal</h1>
        {children}
      </body>
    </html>
  );
}
