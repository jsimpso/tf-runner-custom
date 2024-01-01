ARG BASE_IMAGE=ghcr.io/weaveworks/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.3

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base

ARG TF_VERSION=1.5.7
ARG BW_VERSION=2023.12.1
ARG TARGETARCH=amd64

# Switch to root to have permissions for operations
USER root

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
    rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
    chmod +x /usr/local/bin/terraform

ADD https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/bw-linux-${BW_VERSION}.zip /bw-linux-${BW_VERSION}.zip

RUN unzip -q /bw-linux-${BW_VERSION}.zip -d /usr/local/bin/ && \
    rm /bw-linux-${BW_VERSION}.zip && \
    chmod +x /usr/local/bin/bw

COPY entrypoint.sh /

# Switch back to the non-root user after operations
USER 65532:65532

ENTRYPOINT ["/entrypoint.sh"]

