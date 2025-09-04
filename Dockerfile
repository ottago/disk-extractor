# Multi-stage build: Compile HandBrake from source
FROM ubuntu:24.04 AS handbrake-builder

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies for HandBrake
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    ninja-build \
    pkg-config \
    autoconf \
    automake \
    autopoint \
    appstream \
    # Media libraries and development headers
    libass-dev \
    libbz2-dev \
    libfontconfig1-dev \
    libfreetype6-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libjansson-dev \
    liblzma-dev \
    libmp3lame-dev \
    libnuma-dev \
    libogg-dev \
    libopus-dev \
    libsamplerate0-dev \
    libspeex-dev \
    libtheora-dev \
    libtool \
    libtool-bin \
    libturbojpeg0-dev \
    libvorbis-dev \
    libx264-dev \
    libxml2-dev \
    libvpx-dev \
    m4 \
    make \
    meson \
    nasm \
    patch \
    tar \
    yasm \
    zlib1g-dev \
    # DVD support
    libdvdread-dev \
    libdvdnav-dev \
    libdvdcss-dev \
    # Hardware acceleration
    libva-dev \
    libdrm-dev \
    # Additional codecs
    libx265-dev \
    libnuma-dev \
    && rm -rf /var/lib/apt/lists/*

# Set HandBrake version
ARG HANDBRAKE_VERSION=1.8.2

# Download and compile HandBrake
WORKDIR /tmp
RUN git clone --branch ${HANDBRAKE_VERSION} --depth 1 https://github.com/HandBrake/HandBrake.git && \
    cd HandBrake && \
    # Configure build
    ./configure \
        --prefix=/opt/handbrake \
        --disable-gtk \
        --enable-x265 \
        --enable-numa \
        --enable-libdav1d \
        --enable-nvenc \
        --enable-vce \
        --enable-qsv && \
    # Build HandBrake (this will take a while)
    cd build && \
    make -j$(nproc) && \
    make install

# Production stage
FROM ubuntu:24.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    # Python and tools
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    # Core system libraries
    libc6 \
    libgcc-s1 \
    libstdc++6 \
    libglib2.0-0 \
    # Media and graphics libraries
    libass9 \
    libbz2-1.0 \
    libfontconfig1 \
    libfreetype6 \
    libfribidi0 \
    libharfbuzz0b \
    libjansson4 \
    liblzma5 \
    libmp3lame0 \
    libnuma1 \
    libogg0 \
    libopus0 \
    libsamplerate0 \
    libspeex1 \
    libtheora0 \
    libturbojpeg \
    libvorbis0a \
    libvorbisenc2 \
    libx264-164 \
    libxml2 \
    libvpx9 \
    zlib1g \
    # DVD support libraries
    libdvdread8 \
    libdvdnav4 \
    libdvdcss2 \
    # Hardware acceleration libraries
    libva-drm2 \
    libdrm2 \
    libva2 \
    # Additional codec libraries
    libx265-199 \
    meson \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled HandBrake from builder stage
COPY --from=handbrake-builder /opt/handbrake /opt/handbrake

# Add HandBrake to PATH and set up library paths
ENV PATH="/opt/handbrake/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/handbrake/lib"

# Set up DVD CSS environment variables
ENV DVDCSS_CACHE="/tmp/dvdcss"
ENV DVDCSS_METHOD="key"
ENV DVDCSS_VERBOSE="0"

# Create HandBrakeCLI wrapper script for better error handling and debugging
RUN cat > /usr/local/bin/HandBrakeCLI <<'EOF'
#!/bin/bash
set -e

HANDBRAKE_CLI="/opt/handbrake/bin/HandBrakeCLI"

if [ ! -f "$HANDBRAKE_CLI" ]; then
    echo "Error: HandBrakeCLI not found at $HANDBRAKE_CLI" >&2
    exit 1
fi

# Create DVD CSS cache directory if it doesn't exist
mkdir -p "$DVDCSS_CACHE"

# Debug mode
if [ "$1" = "--debug" ]; then
    echo "Using HandBrakeCLI: $HANDBRAKE_CLI" >&2
    echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
    echo "PATH=$PATH" >&2
    echo "DVDCSS_CACHE=$DVDCSS_CACHE" >&2
    echo "Checking library dependencies..." >&2
    ldd "$HANDBRAKE_CLI" 2>&1 | head -20 >&2 || echo "ldd failed" >&2
    shift
fi

# Run HandBrakeCLI
exec "$HANDBRAKE_CLI" "$@"
EOF

RUN chmod +x /usr/local/bin/HandBrakeCLI

# Verify HandBrake installation
RUN echo "=== HandBrake Installation Verification ===" && \
    HandBrakeCLI --version && \
    echo "=== HandBrake build completed successfully ==="

# Create user
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN if [ "${USER_ID}" = "1000" ]; then \
        # Use existing ubuntu user and group
        usermod -l appuser ubuntu && \
        groupmod -n appuser ubuntu && \
        usermod -d /home/appuser -m appuser; \
    else \
        # Create new user with custom UID/GID
        (groupadd -g ${GROUP_ID} appuser || true) && \
        useradd -m -u ${USER_ID} -g ${GROUP_ID} appuser; \
    fi

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code
COPY . .

# Download JavaScript dependencies during build
RUN mkdir -p /app/static/js/vendor && \
    curl -o /app/static/js/vendor/socket.io.js \
    https://cdn.socket.io/4.7.2/socket.io.min.js && \
    echo "Downloaded Socket.IO $(stat -c%s /app/static/js/vendor/socket.io.js) bytes"

# Set proper ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create AACS directory (placeholder for now)
RUN mkdir -p /home/appuser/.config/aacs && \
    echo "AACS configuration placeholder" > /home/appuser/.config/aacs/README.txt

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command
CMD ["python3", "app.py"]
