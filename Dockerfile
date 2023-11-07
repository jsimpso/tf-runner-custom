ARG BASE_IMAGE=ghcr.io/weaveworks/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.3

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base

ARG TF_VERSION=1.5.7
ARG JUJU_SERIES=3.1
ARG JUJU_PATCH=6
ARG TARGETARCH=amd64



# Switch to root to have permissions for operations
USER root

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
    rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
    chmod +x /usr/local/bin/terraform

ADD https://launchpad.net/juju/${JUJU_SERIES}/${JUJU_SERIES}.${JUJU_PATCH}/+download/juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz
RUN tar -xf juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz && \
    install -o root -g root -m 0755 juju /usr/local/bin/juju && \
    rm /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz

# Switch back to the non-root user after operations
USER 65532:65532