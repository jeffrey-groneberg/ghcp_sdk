FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bubblewrap \
        openssh-server \
    && rm -rf /var/lib/apt/lists/*
