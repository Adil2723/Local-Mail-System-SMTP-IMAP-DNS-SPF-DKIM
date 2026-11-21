FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       iproute2 iputils-ping traceroute bind9-dnsutils swaks python3 \
    && rm -rf /var/lib/apt/lists/*
