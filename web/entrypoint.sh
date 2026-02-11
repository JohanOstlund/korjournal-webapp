#!/bin/sh
set -e

# Replace build-time placeholder with runtime NEXT_PUBLIC_API_URL
if [ -n "$NEXT_PUBLIC_API_URL" ]; then
  find /app/.next -type f -name '*.js' -exec \
    sed -i "s|__NEXT_PUBLIC_API_URL__|$NEXT_PUBLIC_API_URL|g" {} +
fi

exec "$@"
