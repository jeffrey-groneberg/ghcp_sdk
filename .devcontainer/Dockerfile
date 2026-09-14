FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Node.js comes from the Dev Container feature; this stale source otherwise
# breaks Codespaces prebuilds when its external signing key is unavailable.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bubblewrap \
        openssh-server \
    && rm -rf /var/lib/apt/lists/*
