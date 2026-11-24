#!/bin/sh
set -eu

echo "Preparing Alpha Maildir..."

install -d -o zaid -g zaid -m 0700 /home/zaid/Maildir
install -d -o zaid -g zaid -m 0700 /home/zaid/Maildir/new
install -d -o zaid -g zaid -m 0700 /home/zaid/Maildir/cur
install -d -o zaid -g zaid -m 0700 /home/zaid/Maildir/tmp

echo "Preparing Zaid IMAP authentication..."

cp /run/secrets/zaid-imap-users /etc/dovecot/users
chown root:dovecot /etc/dovecot/users
chmod 640 /etc/dovecot/users

echo "Checking Dovecot configuration..."

doveconf -n > /dev/null

echo "Starting Alpha Dovecot..."

dovecot

echo "Starting existing Alpha DKIM and Postfix..."

exec sh /usr/local/bin/start-alpha-dkim
