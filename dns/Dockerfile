FROM cn-mail-lab-tools:local

RUN apt-get update \
    && apt-get install -y --no-install-recommends bind9 bind9-utils \
    && rm -rf /var/lib/apt/lists/*

COPY named.conf db.lab /etc/bind/

RUN install -d -o bind -g bind /run/named \
    && chown bind:bind /var/cache/bind \
    && chmod 644 /etc/bind/named.conf /etc/bind/db.lab \
    && named-checkconf -z /etc/bind/named.conf
