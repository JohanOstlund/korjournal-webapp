// API:t nås alltid på samma origin som webben, via /api. Det gör att cookies
// följer med utan CORS, och att sidan fungerar likadant hemma (http mot
// containern) som utifrån (https genom nginx).
//
// Utifrån fångar nginx /api/ före Next och proxar direkt till API-containern.
// Den här rewriten är vägen för den som går direkt mot Next på LAN.
const INTERNAL_API = process.env.INTERNAL_API_URL || 'http://korjournal-api:8080';

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${INTERNAL_API}/:path*` },
    ];
  },
};
module.exports = nextConfig;
