#!/bin/sh
set -eu

echo "Starting Beta mail server..."
ip route replace default via 10.10.2.254

mkdir -p \
  /home/adil/Maildir/new \
  /home/adil/Maildir/cur \
  /home/adil/Maildir/tmp

chown -R adil:adil /home/adil/Maildir
postfix check

echo "Beta routing configured:"
ip route

echo "Starting Postfix..."
exec postfix start-fg
