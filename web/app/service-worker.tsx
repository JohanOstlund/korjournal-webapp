'use client';
import { useEffect } from 'react';

/**
 * Registrerar service workern. Den kräver secure context, så över LAN:ets
 * http registreras den aldrig — appen fungerar ändå, bara utan offline-sidan
 * och utan att kunna installeras på hemskärmen. Installera från https-adressen.
 */
export function ServiceWorker() {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* degradera tyst — appen ska fungera utan */
    });
  }, []);
  return null;
}
