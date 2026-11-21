FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postfix \
    iproute2 \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /usr/sbin/nologin adil

RUN mkdir -p \
    /home/adil/Maildir/new \
    /home/adil/Maildir/cur \
    /home/adil/Maildir/tmp

RUN grep -Eq '^postlog[[:space:]]+unix-dgram' \
    /etc/postfix/master.cf || \
    printf '%s\n' \
    'postlog   unix-dgram n  -  n  -  1  postlogd' \
    >> /etc/postfix/master.cf

COPY postfix/main.cf /etc/postfix/main.cf
COPY start-beta.sh /usr/local/bin/start-beta.sh

RUN chmod +x /usr/local/bin/start-beta.sh

CMD ["/usr/local/bin/start-beta.sh"]
