#!/bin/sh
set -eu

ip route replace 10.10.0.0/24 via 10.10.1.254
ip route replace 10.10.2.0/24 via 10.10.1.254
install -d -o alice -g alice -m 0700 /home/alice/Maildir

tls_dir=/etc/postfix/tls
identity="$tls_dir/server.pem"
install -d -o root -g postfix -m 0750 "$tls_dir"

if [ ! -s "$identity" ]; then
    temp_dir=$(mktemp -d "$tls_dir/.new.XXXXXX")
    trap 'rm -rf "$temp_dir"' 0

    openssl req -x509 -newkey rsa:2048 -sha256 -noenc -days 90 \
        -subj '/CN=mail.alpha.lab' \
        -addext 'subjectAltName=DNS:mail.alpha.lab' \
        -addext 'basicConstraints=critical,CA:FALSE' \
        -addext 'keyUsage=critical,digitalSignature,keyEncipherment' \
        -addext 'extendedKeyUsage=serverAuth' \
        -keyout "$temp_dir/key.pem" \
        -out "$temp_dir/cert.pem"

    cat "$temp_dir/key.pem" "$temp_dir/cert.pem" > "$temp_dir/server.pem"
    chown root:postfix "$temp_dir/server.pem"
    chmod 0640 "$temp_dir/server.pem"
    mv "$temp_dir/server.pem" "$identity"
    rm -rf "$temp_dir"
    trap - 0
fi

openssl x509 -in "$identity" -out /run/lab-certs/.alpha.crt
chmod 0644 /run/lab-certs/.alpha.crt
mv -f /run/lab-certs/.alpha.crt /run/lab-certs/alpha.crt
exec postfix start-fg
