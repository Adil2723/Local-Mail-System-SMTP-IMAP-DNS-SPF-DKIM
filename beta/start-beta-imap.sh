#!/bin/sh
set -eu
echo "Preparing Dovecot authentication..."
cp /run/secrets/adil-imap-users /etc/dovecot/users
chown root:dovecot /etc/dovecot/users
chmod 640 /etc/dovecot/users
echo "Checking Dovecot configuration..."
doveconf -n > /dev/null
echo "Starting Dovecot..."
dovecot
echo "Starting existing Beta Postfix setup..."
exec /usr/local/bin/start-beta.sh
