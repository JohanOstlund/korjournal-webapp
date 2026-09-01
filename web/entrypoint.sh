#!/bin/sh
set -e

# Replace build-time placeholder with runtime NEXT_PUBLIC_API_URL.
# Även .html/.rsc: förrenderade sidor bär med sig värdet i sin serialiserade
# payload, och missas de syns platshållaren i klartext tills sidan hydrerat.
if [ -n "$NEXT_PUBLIC_API_URL" ]; then
  find /app/.next -type f \( -name '*.js' -o -name '*.html' -o -name '*.rsc' \) -exec \
    sed -i "s|__NEXT_PUBLIC_API_URL__|$NEXT_PUBLIC_API_URL|g" {} +
fi

exec "$@"
