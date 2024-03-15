ARG BASE_IMAGE=ghcr.io/flux-iac/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.4

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base as runner-base

FROM ubuntu
LABEL org.opencontainers.image.source="https://github.com/flux-iac/tofu-controller"

ARG TF_VERSION=1.7.1
ARG JUJU_SERIES=3.1
ARG JUJU_PATCH=7
ARG TARGETARCH=amd64

RUN apt-get update -y \
    && apt-get install --no-install-recommends -y \
    ca-certificates \
    python3-ldap \
    git \
    libssl-dev \
    openssh-client \
    tini \
    xz-utils \
    unzip

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
    rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
    chmod +x /usr/local/bin/terraform

ADD https://launchpad.net/juju/${JUJU_SERIES}/${JUJU_SERIES}.${JUJU_PATCH}/+download/juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz

RUN tar -xf juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz -C /usr/local/bin && chmod +x /usr/local/bin/juju && \
    rm /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz

COPY entrypoint.sh providers.tf /

COPY --from=runner-base /usr/local/bin/tf-runner /usr/local/bin/tf-runner

RUN terraform providers mirror /usr/local/share/terraform/plugins && rm -f providers.tf

# Switch back to the non-root user after operations
USER 65532:65532

ENTRYPOINT ["/entrypoint.sh"]

