import './globals.css';
import type { Metadata, Viewport } from 'next';
import { Nav } from './nav';
import { ServiceWorker } from './service-worker';

export const metadata: Metadata = {
  title: 'Körjournal',
  description: 'Resor, mätarställning och milersättning.',
  manifest: '/manifest.webmanifest',
  icons: {
    icon: '/favicon.png',
    apple: '/apple-touch-icon.png',
  },
  appleWebApp: {
    capable: true,
    title: 'Körjournal',
    // 'default' i stället för 'black-translucent': innehållet börjar under
    // statusraden i stället för bakom den, så ingenting kan hamna under
    // klockan på en iPhone.
    statusBarStyle: 'default',
  },
  formatDetection: {
    // Registreringsnummer och mätarställningar ska inte bli telefonlänkar.
    telephone: false,
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Ytan går ut i kanterna; safe-area-insets i globals.css håller innehållet
  // borta från hörn och hemknappsstreck.
  viewportFit: 'cover',
  themeColor: '#2563eb',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sv">
      <body>
        <Nav />
        <main className="main-container">{children}</main>
        <ServiceWorker />
      </body>
    </html>
  );
}
