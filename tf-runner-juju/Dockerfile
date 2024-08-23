ARG BASE_IMAGE=ghcr.io/flux-iac/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.4

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base

LABEL org.opencontainers.image.source="https://github.com/flux-iac/tofu-controller"

ARG TF_VERSION=1.9.5
ARG JUJU_SERIES=3.5
ARG JUJU_PATCH=3
ARG TARGETARCH=amd64

# Switch to root to have permissions for operations
USER root

# Install python3 and python-ldap
RUN apk add gcc musl-dev python3-dev openldap-dev py3-pip py3-ldap py3-boto3

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
    rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
    chmod +x /usr/local/bin/terraform

ADD https://launchpad.net/juju/${JUJU_SERIES}/${JUJU_SERIES}.${JUJU_PATCH}/+download/juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz

RUN tar -xf juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz -C /usr/local/bin && chmod +x /usr/local/bin/juju && \
    rm /juju-${JUJU_SERIES}.${JUJU_PATCH}-linux-${TARGETARCH}.tar.xz

# Switch back to the non-root user after operations
USER runner:runner

RUN mkdir -p /home/runner/temp
COPY providers.tf /home/runner/temp
ENV TF_PLUGIN_CACHE_DIR="/home/runner/.terraform.d/plugin-cache/"
RUN mkdir -p $TF_PLUGIN_CACHE_DIR
WORKDIR /home/runner/temp
RUN terraform init
WORKDIR /home/runner
RUN rm -rf /home/runner/temp

RUN mkdir -p /home/runner/.local/share/juju
ENTRYPOINT [ "/sbin/tini", "--", "tf-runner" ]