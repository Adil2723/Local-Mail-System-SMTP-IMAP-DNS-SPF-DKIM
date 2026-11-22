#!/bin/sh
set -eu
test -s /etc/opendkim/keys/mail.private || { echo 'STOP: Alpha DKIM key missing'; exit 1; }
opendkim -x /etc/opendkim.conf
exec /usr/local/bin/start-mail-alpha
