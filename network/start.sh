#!/bin/sh
set -eu

case "$ROLE" in

  r1)
    ip route replace 10.10.2.0/24 via 10.10.0.12
    ;;

  r2)
    ip route replace 10.10.1.0/24 via 10.10.0.11
    ;;

  alpha)
    ip route replace default via 10.10.1.254
    ;;

  beta)
    ip route replace default via 10.10.2.254
    ;;

  *)
    echo "Unknown role"
    exit 1
    ;;
esac

echo "$ROLE network configured"
ip route

exec sleep infinity
