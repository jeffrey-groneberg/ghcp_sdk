FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# The base image's stale Yarn apt source breaks Codespaces prebuilds when its
# signing key is unavailable, so drop it. Bubblewrap is the Linux backend of the
# runtime sandbox used by examples 08 and 13.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bubblewrap \
        openssh-server \
    && rm -rf /var/lib/apt/lists/*
