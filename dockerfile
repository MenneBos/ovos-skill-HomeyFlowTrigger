# Base image met OVOS / Mycroft dependencies
FROM python:3.12-slim

ARG DEBIAN_FRONTEND=noninteractive

# Zet maintainer info
LABEL maintainer="you@example.com"

# Install OS deps and Node 20 LTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg build-essential \
  && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y nodejs \
  && npm install -g npm@latest \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Omgevingsvariabelen (runtime kan deze overrulen)
ENV OVOS_USER=ovos \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Gebruik bestaande user (via userns keep-id)
USER $OVOS_USER

# Skill code in container
WORKDIR /home/ovos/ovos-skill-homeyflowtrigger
COPY . .

# Install Node dependencies
WORKDIR /home/$OVOS_USER/homeyflowtrigger/nodejs
RUN if [ -f package.json ]; then npm ci; else npm install homey-api; fi

# Python deps 
WORKDIR /home/ovos/ovos-skill-homeyflowtrigger
RUN pip install --upgrade pip \
 && pip install -e .

# Start je skill
CMD ["python", "-m", "ovos_skill_homeyflowtrigger"]