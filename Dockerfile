FROM ubuntu:24.04

LABEL org.opencontainers.image.source="https://github.com/openwatersio/gebco"
LABEL org.opencontainers.image.description="GEBCO bathymetry to vector tile pipeline"

ENV DEBIAN_FRONTEND=noninteractive

# GDAL (with Python bindings for terrain-rgb encoding), jq, and build deps.
RUN apt-get update && apt-get install -y \
    gdal-bin \
    python3-gdal \
    python3-numpy \
    python3-pip \
    python3-venv \
    bc \
    jq \
    curl \
    unzip \
    sqlite3 \
    build-essential \
    libsqlite3-dev \
    zlib1g-dev \
    git \
  && rm -rf /var/lib/apt/lists/*

# Install rio-rgbify for Terrain-RGB encoding.
RUN python3 -m venv /opt/rio-venv \
  && /opt/rio-venv/bin/pip install --no-cache-dir rio-rgbify
ENV PATH="/opt/rio-venv/bin:$PATH"

# Install tippecanoe (Felt fork).
RUN git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe \
  && cd /tmp/tippecanoe \
  && make -j$(nproc) \
  && make install \
  && rm -rf /tmp/tippecanoe

# Install pmtiles CLI.
RUN ARCH=$(dpkg --print-architecture) \
  && curl -L -o /tmp/go-pmtiles.tar.gz \
    "https://github.com/protomaps/go-pmtiles/releases/latest/download/go-pmtiles_${ARCH}_linux.tar.gz" \
  && tar -xzf /tmp/go-pmtiles.tar.gz -C /usr/local/bin pmtiles \
  && chmod +x /usr/local/bin/pmtiles \
  && rm /tmp/go-pmtiles.tar.gz

WORKDIR /app
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

ENTRYPOINT ["/app/scripts/pipeline.sh"]
