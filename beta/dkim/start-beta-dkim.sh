#!/bin/sh
set -eu
opendkim -x /etc/opendkim.conf
exec /usr/local/bin/start-beta-imap.sh
