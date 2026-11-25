FROM eclipse-temurin:11-jre

ARG DSBULK_VERSION=1.11.1

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && curl -fsSL "https://github.com/datastax/dsbulk/releases/download/${DSBULK_VERSION}/dsbulk-${DSBULK_VERSION}.tar.gz" \
  -o /tmp/dsbulk.tar.gz \
  && tar -xzf /tmp/dsbulk.tar.gz -C /opt \
  && mv "/opt/dsbulk-${DSBULK_VERSION}" /opt/dsbulk \
  && rm /tmp/dsbulk.tar.gz \
  && ln -s /opt/dsbulk/bin/dsbulk /usr/local/bin/dsbulk

WORKDIR /work
ENTRYPOINT ["dsbulk"]
