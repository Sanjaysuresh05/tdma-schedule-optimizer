# One consolidated container for Part 2 (EMANE 1.5.3 + this project's bridge and runner).
#
# NOTE: Docker is not installed on the machine this project was developed on, so this
# image has NOT been built or run there.  The identical experiment was executed
# natively (rootless) on WSL2 Ubuntu 24.04 with emane/install_rootless.sh +
# emane/runner/run_experiments.sh; see emane/results/.  This file follows the
# official install instructions (https://github.com/adjacentlink/emane/wiki/Install).
#
# Build : docker build -f emane/docker/Dockerfile -t vmn-tdma-emane .
# Run   : docker run --rm --privileged -v "$PWD/emane/results:/work/emane/results" vmn-tdma-emane
#         (--privileged: network namespaces, bridges and TAP devices for 16 emulated nodes)
FROM ubuntu:24.04

ARG EMANE_BUNDLE=emane-1.5.3-release-1.ubuntu-24_04.amd64.tar.gz
ARG EMANE_SHA256=a60a2fd1ebf73cc2a26e7fa48e8eef0c5cac44e17b11ab7e31dd06de6cf53638
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl iproute2 python3 python3-lxml python3-protobuf util-linux \
    && rm -rf /var/lib/apt/lists/*

# Official Adjacent Link release bundle; install only the packages this project uses.
RUN curl -fsSLO https://adjacentlink.com/downloads/emane/${EMANE_BUNDLE} \
    && echo "${EMANE_SHA256}  ${EMANE_BUNDLE}" | sha256sum -c - \
    && tar xzf ${EMANE_BUNDLE} \
    && cd emane-1.5.3-release-1/debs/ubuntu-24_04/amd64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
         ./emane-libs_*.deb ./emane_*.deb ./emane-dtds_*.deb ./emane-manifest_*.deb \
         ./emane-trans-common_*.deb ./emane-trans-virtual_*.deb \
         ./emane-model-tdmaeventscheduler_*.deb ./emane-eventservice_*.deb ./python3-emane_*.deb \
    && cd / && rm -rf emane-1.5.3-release-1 ${EMANE_BUNDLE} /var/lib/apt/lists/*

WORKDIR /work
COPY emane/bridge /work/emane/bridge
COPY emane/runner /work/emane/runner
COPY emane/scenarios /work/emane/scenarios
COPY emane/schema /work/emane/schema

# System-wide install: no sysroot; the runner then uses /usr/share/emane paths.  As real root in a
# --privileged container the runner skips the user namespace, so realtime scheduling (-r) can work.
ENV VMN_EMANE_ENV=/dev/null VMN_EMANE_SYSROOT="" VMN_EMANE_WORK=/tmp/vmn-emane-work VMN_EMANE_REALTIME=1
CMD ["bash", "emane/runner/run_experiments.sh", "20", "40"]
