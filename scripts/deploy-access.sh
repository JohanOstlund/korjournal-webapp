#!/usr/bin/env bash
#
# Öppnar Körjournalen utifrån bakom den befintliga nginx-proxyn — utan att
# lägga appen öppet på internet.
#
# Grinden är en engångsregistrerad cookie per person: du öppnar
# https://<host>/enroll/<hemlighet> en gång på telefonen, och därefter är
# enheten inne för gott. Enheter på LAN släpps förbi utan cookie. Allt annat
# får 404 — en portscanner ska inte ens se att det finns något här.
#
# Appens egen inloggning (bcrypt + JWT + rate limit på 5 försök/minut) gäller
# fortfarande. Grinden är ett lager UTANPÅ den, inte i stället för den.
#
# Idempotent. Vid omkörning återanvänds befintliga hemligheter så att inga
# enheter kastas ut — --rotate genererar nya och av-registrerar alla.
#
# Kör som din vanliga användare; skriptet höjer sig själv med sudo där det
# behövs.

set -euo pipefail

# ─── Konfiguration ────────────────────────────────────────────────────────────

# Värdnamn och personer läses ur .env, som är gitignorerad. Repot är publikt,
# och det ska inte annonsera vilken adress som ligger bakom grinden eller vilka
# som har en länk. Säkerheten vilar på hemligheterna och inte på att adressen är
# okänd — men det finns ingen anledning att skylta med måltavlan.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"

env_value() { sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | head -1 | tr -d '"' | cut -d'#' -f1; }

if [[ -f "$ENV_FILE" ]]; then
    PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-$(env_value PUBLIC_ORIGIN)}"
    ACCESS_PEOPLE="${ACCESS_PEOPLE:-$(env_value ACCESS_PEOPLE)}"
    WEB_PORT="${WEB_PORT:-$(env_value WEB_PORT)}"
    API_PORT="${API_PORT:-$(env_value API_PORT)}"
fi

# Strippa schema och eventuell sökväg: https://exempel.se/ -> exempel.se
HOST="${HOST:-${PUBLIC_ORIGIN:-}}"
HOST="${HOST#*://}"
HOST="$(echo "${HOST%%/*}" | tr -d '[:space:]')"

WEB_PORT="$(echo "${WEB_PORT:-3001}" | tr -d '[:space:]')"   # Next.js-containern
API_PORT="$(echo "${API_PORT:-8080}" | tr -d '[:space:]')"   # FastAPI-containern

# En länk per person, inte per enhet — samma länk funkar på personens telefon
# och surfplatta. Vill du kunna spärra en enskild enhet, namnge per enhet
# i stället: ACCESS_PEOPLE=anna-iphone,anna-ipad,bo-iphone
read -r -a PEOPLE <<< "$(echo "${PEOPLE_OVERRIDE:-${ACCESS_PEOPLE:-}}" | tr ',' ' ')"

# nginx-include med certet för värdnamnet. SAN-listan verifieras nedan innan
# något skrivs.
SSL_INCLUDE="${SSL_INCLUDE:-ssl_2.conf}"

NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
VHOST="$NGINX_AVAILABLE/$HOST"
BACKUP_DIR="$HOME/.korjournal-access-backups/$(date +%Y%m%d-%H%M%S)"
SECRETS_OUT="/root/korjournal-enrolment-$HOST.txt"

ROTATE=0
[[ "${1:-}" == "--rotate" ]] && ROTATE=1

# ─── Hjälpare ─────────────────────────────────────────────────────────────────

say()  { printf '\n\033[1;32m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\033[1;33m    ! %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mAvbryter:\033[0m %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "saknar $1"; }
need openssl; need curl; need nginx

[[ -n "$HOST" ]] || die "inget värdnamn. Sätt PUBLIC_ORIGIN i $ENV_FILE (t.ex. https://korjournal.exempel.se) eller kör med HOST=..."
[[ ${#PEOPLE[@]} -gt 0 && -n "${PEOPLE[0]:-}" ]] || die "inga personer att skapa länkar för. Sätt ACCESS_PEOPLE i $ENV_FILE (t.ex. ACCESS_PEOPLE=anna,bo)"

# ─── Förkontroller ────────────────────────────────────────────────────────────

say "Förkontroller"

[[ -f "$VHOST" ]] || die "hittar ingen vhost på $VHOST — förväntade en befintlig konfiguration att bygga vidare på."

# Certet måste täcka värdnamnet, annars vägrar iOS installera PWA:n.
if ! echo | openssl s_client -connect 127.0.0.1:443 -servername "$HOST" 2>/dev/null \
     | openssl x509 -noout -ext subjectAltName 2>/dev/null | grep -q "DNS:$HOST"; then
    die "certet som presenteras för $HOST saknar $HOST i SAN-listan. Fixa certet först."
fi
info "cert täcker $HOST"

# Appen måste svara lokalt, annars proxar vi mot ingenting.
curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/login"  || die "webben svarar inte på 127.0.0.1:$WEB_PORT"
curl -sf -o /dev/null "http://127.0.0.1:$API_PORT/health" || die "API:t svarar inte på 127.0.0.1:$API_PORT"
info "web ($WEB_PORT) och api ($API_PORT) svarar"

# LAN-bypassen bygger på att externa anrop har publika käll-IP:n. Router som
# source-NAT:ar port forwards skulle få hela internet att se ut som LAN och
# därmed öppna appen helt. Vi kan inte testa utifrån härifrån, men vi kan
# titta på vad nginx faktiskt har sett.
say "Kontrollerar att LAN-bypassen inte är en bakdörr"
if sudo test -r /var/log/nginx/access.log; then
    publika=$(sudo awk '{print $1}' /var/log/nginx/access.log \
              | grep -Ecv '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.)' || true)
    if [[ "${publika:-0}" -gt 0 ]]; then
        info "nginx har loggat $publika anrop från publika IP:n — källadresser bevaras, bypassen är säker"
    else
        warn "access.log innehåller BARA privata käll-IP:n."
        warn "Antingen har ingen nått servern utifrån ännu, eller så source-NAT:ar routern"
        warn "port forwarden — i det senare fallet skulle LAN-bypassen släppa in hela internet."
        warn "Grinden verifieras ändå nedan från 127.0.0.1, som INTE ligger i bypassen."
    fi
else
    warn "kan inte läsa access.log — hoppar över kontrollen"
fi

# ─── Hemligheter ──────────────────────────────────────────────────────────────

declare -a NAMES=() SECRETS=()

if [[ $ROTATE -eq 0 ]] && sudo grep -q '^map \$cookie_korjournal' "$VHOST" 2>/dev/null; then
    say "Återanvänder befintliga hemligheter (kör med --rotate för att byta ut dem)"
    while read -r secret name; do
        NAMES+=("$name"); SECRETS+=("$secret")
    done < <(sudo sed -n 's/^    "\([0-9a-f]\{32\}\)" 1;[[:space:]]*#[[:space:]]*\(.*\)$/\1 \2/p' "$VHOST")
    info "${#NAMES[@]} registrerade: ${NAMES[*]}"
    # Nytillkomna personer i PEOPLE får en ny hemlighet, befintliga behåller sin.
    for p in "${PEOPLE[@]}"; do
        found=0
        for n in "${NAMES[@]}"; do [[ "$n" == "$p" ]] && found=1 && break; done
        if [[ $found -eq 0 ]]; then
            NAMES+=("$p"); SECRETS+=("$(openssl rand -hex 16)")
            info "ny: $p"
        fi
    done
else
    say "Genererar nya hemligheter"
    [[ $ROTATE -eq 1 ]] && warn "--rotate: alla enheter måste registrera sig igen"
    for p in "${PEOPLE[@]}"; do
        NAMES+=("$p"); SECRETS+=("$(openssl rand -hex 16)")
    done
fi

[[ ${#SECRETS[@]} -gt 0 ]] || die "inga hemligheter att skriva"

# ─── Skriv vhost ──────────────────────────────────────────────────────────────

mkdir -p "$BACKUP_DIR"
sudo cp "$VHOST" "$BACKUP_DIR/$(basename "$VHOST").bak"
info "backup: $BACKUP_DIR/$(basename "$VHOST").bak"

say "Genererar vhost"
tmp="$(mktemp)"
{
    echo "# Körjournal — $HOST"
    echo "# Genererad av scripts/deploy-access.sh $(date +%Y-%m-%d). Handredigera inte;"
    echo "# kör om skriptet i stället, annars försvinner ändringarna vid nästa körning."
    echo "#"
    echo "# Åtkomst utifrån kräver en engångsregistrerad cookie. LAN släpps förbi."
    echo "# Allt annat får 404. Appens egen inloggning gäller fortfarande."
    echo "#"
    echo "# IPv4 only med flit — se varningen i 00-default-reject innan du lägger till [::]."
    echo
    echo "upstream korjournal_web {"
    echo "    server 127.0.0.1:$WEB_PORT;"
    echo "    keepalive 32;"
    echo "}"
    echo
    echo "upstream korjournal_api {"
    echo "    server 127.0.0.1:$API_PORT;"
    echo "    keepalive 32;"
    echo "}"
    echo
    echo "map \$http_upgrade \$connection_upgrade {"
    echo "    default upgrade;"
    echo "    ''      close;"
    echo "}"
    echo
    echo "# Enheter hemma slipper registrera sig. 127.0.0.1 är med flit INTE med:"
    echo "# det gör att grinden kan testas skarpt lokalt med curl (verify nedan)."
    echo "geo \$kj_lan {"
    echo "    default 0;"
    echo "    10.0.0.0/8      1;"
    echo "    172.16.0.0/12   1;"
    echo "    192.168.0.0/16  1;"
    echo "}"
    echo
    echo "map \$cookie_korjournal \$kj_enrolled {"
    echo "    default 0;"
    for i in "${!SECRETS[@]}"; do
        printf '    "%s" 1;   # %s\n' "${SECRETS[$i]}" "${NAMES[$i]}"
    done
    echo "}"
    echo
    echo "# Blockera bara den som varken är på LAN eller har en giltig cookie."
    echo "map \"\$kj_lan\$kj_enrolled\" \$kj_blocked {"
    echo "    default 0;"
    echo "    \"00\"    1;"
    echo "}"
    echo
    echo "server {"
    echo "    listen 443 ssl http2;"
    echo "    server_name $HOST;"
    echo "    include $SSL_INCLUDE;"
    echo
    echo "    add_header X-Content-Type-Options nosniff always;"
    echo "    add_header X-Frame-Options DENY always;"
    echo "    add_header Referrer-Policy strict-origin-when-cross-origin always;"
    echo
    echo "    # ACME aldrig bakom grinden. Certet är ett SAN-cert som även täcker"
    echo "    # hassio, cs2, nasen och poddar — en spärrad förnyelse här skulle ta"
    echo "    # ner TLS för allihop."
    echo "    location ^~ /.well-known/ {"
    echo "        root /var/www/html;"
    echo "    }"
    echo
    for i in "${!SECRETS[@]}"; do
        echo "    # ${NAMES[$i]} — access_log av, annars hamnar hemligheten i klartext i"
        echo "    # access.log där vem som helst med logg-läsning kan registrera sig själv."
        echo "    location = /enroll/${SECRETS[$i]} {"
        echo "        access_log off;"
        echo "        add_header Set-Cookie \"korjournal=${SECRETS[$i]}; Path=/; Max-Age=315360000; Secure; HttpOnly; SameSite=Lax\";"
        echo "        return 302 /;"
        echo "    }"
    done
    echo
    echo "    # Bakåtkompatibel redirect: /auth/* -> /api/auth/*"
    echo "    # Måste ligga före /api/-blocket."
    echo "    location ^~ /auth/ {"
    echo "        return 308 /api\$uri;"
    echo "    }"
    echo
    echo "    location ^~ /api/ {"
    echo "        # Grinden måste gälla API:t också — annars är hela appen nåbar"
    echo "        # runt den, eftersom frontenden bara är ett skal ovanpå API:t."
    echo "        if (\$kj_blocked) { return 404; }"
    echo
    echo "        # Avslutande slash: strippar /api innan det går vidare. API:t"
    echo "        # serverar /trips, inte /api/trips."
    echo "        proxy_pass http://korjournal_api/;"
    echo "        proxy_http_version 1.1;"
    echo
    echo "        proxy_set_header Host               \$host;"
    echo "        proxy_set_header X-Real-IP          \$remote_addr;"
    echo "        proxy_set_header X-Forwarded-For    \$proxy_add_x_forwarded_for;"
    echo "        proxy_set_header X-Forwarded-Proto  https;"
    echo "        proxy_pass_header Set-Cookie;"
    echo
    echo "        proxy_set_header Upgrade    \$http_upgrade;"
    echo "        proxy_set_header Connection \$connection_upgrade;"
    echo
    echo "        add_header Cache-Control \"no-store\";"
    echo "    }"
    echo
    echo "    location / {"
    echo "        # 404 i stället för 403 — en scanner ska inte se att här finns något."
    echo "        if (\$kj_blocked) { return 404; }"
    echo
    echo "        proxy_pass http://korjournal_web;"
    echo "        proxy_http_version 1.1;"
    echo
    echo "        proxy_set_header Host               \$host;"
    echo "        proxy_set_header X-Real-IP          \$remote_addr;"
    echo "        proxy_set_header X-Forwarded-For    \$proxy_add_x_forwarded_for;"
    echo "        proxy_set_header X-Forwarded-Proto  https;"
    echo
    echo "        proxy_set_header Upgrade    \$http_upgrade;"
    echo "        proxy_set_header Connection \$connection_upgrade;"
    echo "    }"
    echo "}"
    echo
    echo "server {"
    echo "    listen 80;"
    echo "    server_name $HOST;"
    echo
    echo "    location ^~ /.well-known/ {"
    echo "        root /var/www/html;"
    echo "    }"
    echo
    echo "    location / {"
    echo "        return 301 https://\$host\$request_uri;"
    echo "    }"
    echo "}"
} > "$tmp"

sudo install -m 640 -o root -g root "$tmp" "$VHOST"
rm -f "$tmp"
sudo ln -sfn "$VHOST" "$NGINX_ENABLED/$HOST"

# ─── Testa och ladda om ───────────────────────────────────────────────────────

say "Testar konfigurationen"
if ! sudo nginx -t 2>&1 | sed 's/^/    /'; then
    warn "nginx -t underkände konfigurationen — återställer"
    sudo cp "$BACKUP_DIR/$(basename "$VHOST").bak" "$VHOST"
    sudo nginx -t >/dev/null 2>&1 && sudo systemctl reload nginx
    die "konfigurationen återställd, inget ändrat"
fi
sudo systemctl reload nginx
info "nginx omladdad"

# ─── Verifiera grinden ────────────────────────────────────────────────────────

say "Verifierar grinden (från 127.0.0.1, som ligger utanför LAN-bypassen)"

check() {
    local label="$1" expect="$2" path="$3"; shift 3
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --resolve "$HOST:443:127.0.0.1" \
           "https://$HOST$path" "$@" --max-time 10)
    if [[ "$code" == "$expect" ]]; then
        info "OK   $label → $code"
    else
        warn "FEL  $label → $code (väntade $expect)"
        return 1
    fi
}

fail=0
check "utan cookie, webb"  404 "/login"        || fail=1
check "utan cookie, api"   404 "/api/health"   || fail=1
check "med cookie, webb"   200 "/login"        -H "Cookie: korjournal=${SECRETS[0]}" || fail=1
check "med cookie, api"    200 "/api/health"   -H "Cookie: korjournal=${SECRETS[0]}" || fail=1

if [[ $fail -ne 0 ]]; then
    warn "Grinden beter sig inte som väntat. Konfigurationen ligger kvar —"
    warn "backup finns i $BACKUP_DIR om du vill rulla tillbaka."
    exit 1
fi

# ─── Registreringslänkar ──────────────────────────────────────────────────────

say "Registreringslänkar — öppna en gång per person, på varje enhet"
{
    echo "# Körjournal — registreringslänkar för $HOST"
    echo "# Genererad $(date '+%Y-%m-%d %H:%M'). Bearer-hemligheter: dela via"
    echo "# säker kanal, inte i en gruppchatt som ligger kvar för evigt."
    echo
    for i in "${!SECRETS[@]}"; do
        printf '%-12s https://%s/enroll/%s\n' "${NAMES[$i]}" "$HOST" "${SECRETS[$i]}"
    done
} | sudo tee "$SECRETS_OUT" >/dev/null
sudo chmod 600 "$SECRETS_OUT"

for i in "${!SECRETS[@]}"; do
    printf '    %-12s https://%s/enroll/%s\n' "${NAMES[$i]}" "$HOST" "${SECRETS[$i]}"
done

echo
info "Sparade också i $SECRETS_OUT (läsbar bara för root)."
info "Cookien lever i 10 år och överlever att PWA:n stängs — men inte att"
info "webbplatsdata rensas. Då är det bara att öppna länken igen."
echo
warn "Kontrollera att port $WEB_PORT och $API_PORT INTE är port-forwardade i routern"
warn "parallellt med 443 — då går hela grinden att gå runt."
