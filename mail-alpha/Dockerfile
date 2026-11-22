FROM cn-mail-lab-tools:local

RUN printf '%s\n' \
       'postfix postfix/main_mailer_type select Internet Site' \
       'postfix postfix/mailname string alpha.lab' \
    | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postfix openssl \
    && rm -rf /var/lib/apt/lists/*

COPY main.cf /etc/postfix/main.cf
COPY start.sh /usr/local/bin/start-mail-alpha

RUN useradd --create-home --user-group zaid \
    && chmod 644 /etc/postfix/main.cf \
    && printf 'postmaster: root\n' > /etc/aliases \
    && newaliases \
    && postconf -F 'smtp/inet/chroot=n' 'smtp/unix/chroot=n' \
    && postconf -M 'postlog/unix-dgram=postlog unix-dgram n - n - 1 postlogd' \
    && postfix check
