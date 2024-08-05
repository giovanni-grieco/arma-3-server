FROM debian:buster-slim

LABEL maintainer="Dzuelu - github.com/Dzuelu"
LABEL org.opencontainers.image.source=https://github.com/Dzuelu/arma-3-server

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && \
    apt-get install -y --no-install-recommends --no-install-suggests \
        ca-certificates \
        lib32gcc1 \
        lib32stdc++6 \
        locales \
        python3 \
        rename \
        wget \
        git \
    && \
    apt-get remove --purge -y \
    && \
    apt-get clean autoclean \
    && \
    apt-get autoremove -y \
    && \
    rm -rf /var/lib/apt/lists/* \
    && \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 \
    && \
    mkdir -p /steamcmd

ENV LANG en_US.utf8
ENV PYTHONUNBUFFERED=1

ENV ARMA_BINARY="./arma3server"
ENV ARMA_CDLC=
ENV ARMA_CONFIG="main.cfg"
ENV ARMA_LIMITFPS=1000
ENV ARMA_PARAMS=
ENV ARMA_PROFILE="main"
ENV ARMA_WORLD="empty"
ENV DEBUG=0
ENV FORCE_DOWNLOAD_WORKSHOP=0
ENV HEADLESS_CLIENTS=0
ENV PORT=2302
ENV STEAM_BRANCH_PASSWORD=
ENV STEAM_BRANCH="public"
ENV STEAM_PASSWORD=
ENV STEAM_USERNAME=
ENV STEAM_VALIDATE=1
ENV WORKSHOP_MODS=

ENV CHECK_MODS=1
ENV DOWNLOAD_ATTEMPTS=2

EXPOSE 2302/udp
EXPOSE 2303/udp
EXPOSE 2304/udp
EXPOSE 2305/udp
EXPOSE 2306/udp

WORKDIR /arma3

VOLUME /arma3

STOPSIGNAL SIGINT

COPY *.py /

CMD ["python3","/a3update.py"]
