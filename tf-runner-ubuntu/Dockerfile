ARG BASE_IMAGE=ghcr.io/flux-iac/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.5

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base as runner-base

FROM docker.io/library/ubuntu:24.04
LABEL org.opencontainers.image.source="https://github.com/flux-iac/tofu-controller"

ENV DEBIAN_FRONTEND=noninteractive
ARG TF_VERSION=1.14.3
ARG TARGETARCH=amd64

RUN apt-get update -y \
    && apt-get install --no-install-recommends -y \
    ca-certificates \
    curl \
    python3-boto3 \
    python3-ldap \
    python3-launchpadlib \
    python3-hvac \
    libldap2-dev \
    libsasl2-dev \
    libldap-common \
    git \
    libssl-dev \
    openssh-client \
    tini \
    xz-utils \
    vim \
    unzip

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
    rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
    chmod +x /usr/local/bin/terraform

COPY --from=runner-base /usr/local/bin/tf-runner /usr/local/bin/tf-runner

RUN addgroup --gid 65532 --system runner \
    && adduser --uid 65532 --system runner --group --home /home/runner

USER runner:runner

RUN mkdir /home/runner/temp
COPY providers.tf /home/runner/temp
ENV TF_PLUGIN_CACHE_DIR="/home/runner/.terraform.d/plugin-cache/"
RUN mkdir -p $TF_PLUGIN_CACHE_DIR
WORKDIR /home/runner/temp
RUN terraform init
WORKDIR /home/runner
RUN rm -rf /home/runner/temp

ENTRYPOINT [ "/bin/tini", "--", "tf-runner" ]
