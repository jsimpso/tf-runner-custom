ARG BASE_IMAGE=ghcr.io/flux-iac/tf-runner
ARG TF_CONTROLLER_VERSION=v0.16.0-rc.5

FROM ${BASE_IMAGE}:${TF_CONTROLLER_VERSION}-base as runner-base

FROM ubuntu
LABEL org.opencontainers.image.source="https://github.com/flux-iac/tofu-controller"

ARG TF_VERSION=1.11.1
ARG BW_VERSION=2023.12.1
ARG TARGETARCH=amd64

RUN apt-get update -y \
  && apt-get install -y \
  ca-certificates \
  git \
  gnupg \
  libssl-dev \
  openssh-client \
  tini \
  unzip

ADD https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${TARGETARCH}.zip /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip
RUN unzip -q /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip -d /usr/local/bin/ && \
  rm /terraform_${TF_VERSION}_linux_${TARGETARCH}.zip && \
  chmod +x /usr/local/bin/terraform

ADD https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/bw-linux-${BW_VERSION}.zip /bw-linux-${BW_VERSION}.zip

RUN unzip -q /bw-linux-${BW_VERSION}.zip -d /usr/local/bin/ && \
  rm /bw-linux-${BW_VERSION}.zip && \
  chmod +x /usr/local/bin/bw

COPY --from=runner-base /usr/local/bin/tf-runner /usr/local/bin/tf-runner 

RUN echo 'hosts: files dns' > /etc/nsswitch.conf
RUN addgroup --gid 65532 --system runner \
  && adduser --uid 65532 --system runner --group

USER 65532:65532
ENV GNUPGHOME=/tmp

ENTRYPOINT [ "/bin/tini", "--", "tf-runner" ]