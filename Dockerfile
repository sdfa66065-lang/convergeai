FROM eclipse-temurin:17-jdk-jammy

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
