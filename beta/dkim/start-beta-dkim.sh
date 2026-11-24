#!/bin/sh
set -eu
# CN12 Postfix chroot DNS
mkdir -p /var/spool/postfix/etc
printf 'nameserver 10.10.0.53\noptions timeout:2 attempts:2\n' > /var/spool/postfix/etc/resolv.conf.new
chmod 644 /var/spool/postfix/etc/resolv.conf.new
mv /var/spool/postfix/etc/resolv.conf.new /var/spool/postfix/etc/resolv.conf

opendkim -x /etc/opendkim.conf
exec /usr/local/bin/start-beta-imap.sh
