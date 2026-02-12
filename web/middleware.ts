import { NextResponse, NextRequest } from 'next/server';

const API = process.env.INTERNAL_API_URL
  || process.env.NEXT_PUBLIC_API_URL
  || 'http://host.docker.internal:8080';

// Vägar som ska vara publika (tillåtna utan inloggning)
const PUBLIC_PATHS = new Set<string>([
  '/login',
  '/_next',          // Next.js assets
  '/favicon.ico',
  '/robots.txt',
  '/sitemap.xml',
]);

function isPublicPath(pathname: string) {
  if (pathname === '/') return false; // startsida ska kräva auth
  for (const pub of PUBLIC_PATHS) {
    if (pathname === pub || pathname.startsWith(pub + '/')) return true;
  }
  // Tillåt också statiska filer under /public med filändelser
  if (/\.(?:png|jpg|jpeg|gif|svg|webp|ico|txt|xml|css|js|map)$/.test(pathname)) return true;
  return false;
}

export async function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  // Släpp igenom öppna paths
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Kolla session via /auth/me på API:t
  try {
    const cookie = req.headers.get('cookie') || '';
    const r = await fetch(`${API}/auth/me`, {
      method: 'GET',
      headers: { cookie }, // vidarebefordra cookies till API
      // OBS: middleware kör på Edge – credentials: 'include' behövs ej när vi skickar headern själva
    });

    if (r.ok) {
      // Inloggad → fortsätt
      return NextResponse.next();
    }
  } catch (_e) {
    // Ignorera, vi redirectar nedan
  }

  // Inte inloggad → redirect till /login med returnTo
  const loginUrl = req.nextUrl.clone();
  loginUrl.pathname = '/login';
  loginUrl.search = `?returnTo=${encodeURIComponent(pathname + (search || ''))}`;
  return NextResponse.redirect(loginUrl);
}

// Använd middleware på alla vägar (Next exkluderar statiska filer själv efter vår isPublicPath-koll)
export const config = {
  matcher: '/:path*',
};
