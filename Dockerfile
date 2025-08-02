FROM python:3.11-slim AS flatpak-extractor

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install tools needed for Flatpak extraction
RUN apt-get update && apt-get install -y \
    curl \
    flatpak \
    ca-certificates \
    file \
    # DVD support libraries
    libdvdread8 \
    libdvdnav4 \
    && rm -rf /var/lib/apt/lists/*

# Try to install libdvdcss from multiple sources
RUN apt-get update && \
    # Try to install from universe repository first
    (apt-get install -y libdvdcss2 || \
    # If that fails, try to install from videolan repository
    (curl -fsSL https://download.videolan.org/pub/debian/videolan-apt.asc | apt-key add - && \
     echo "deb https://download.videolan.org/pub/debian/stable/ /" > /etc/apt/sources.list.d/videolan.list && \
     apt-get update && \
     apt-get install -y libdvdcss2) || \
    # If that also fails, build from source
    (apt-get install -y build-essential && \
     cd /tmp && \
     curl -L https://download.videolan.org/pub/libdvdcss/1.4.3/libdvdcss-1.4.3.tar.bz2 | tar xj && \
     cd libdvdcss-1.4.3 && \
     ./configure --prefix=/usr/local && \
     make && make install && \
     ldconfig && \
     cd / && rm -rf /tmp/libdvdcss-1.4.3 && \
     apt-get remove -y build-essential && \
     apt-get autoremove -y) || \
    echo "Warning: Could not install libdvdcss - encrypted DVD support may be limited") && \
    rm -rf /var/lib/apt/lists/*

# Set up Flatpak and install HandBrake
RUN flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo \
    && flatpak install -y --system flathub fr.handbrake.ghb

# Extract HandBrake application
RUN mkdir -p /extracted-handbrake \
    && FLATPAK_DIR="/var/lib/flatpak/app/fr.handbrake.ghb/current/active/files" \
    && cp -r "$FLATPAK_DIR"/* /extracted-handbrake/

# Extract only the media codec libraries we need from the GNOME Platform runtime
RUN mkdir -p /extracted-libs \
    && RUNTIME_DIR="/var/lib/flatpak/runtime/org.gnome.Platform/x86_64/47/active/files" \
    && find "$RUNTIME_DIR" \( \
        -name "libvpx*" -o \
        -name "libopus*" -o \
        -name "libtheora*" -o \
        -name "libvorbis*" -o \
        -name "libmp3lame*" -o \
        -name "libx264*" -o \
        -name "libx265*" -o \
        -name "libass*" -o \
        -name "libturbojpeg*" -o \
        -name "libspeex*" -o \
        -name "libva*" -o \
        -name "libdrm*" -o \
        -name "libogg*" \
    \) -exec cp {} /extracted-libs/ \;

# Production stage - Ubuntu 24.04 for GLIBC 2.39 compatibility
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
    libfreetype6 \
    libfontconfig1 \
    libharfbuzz0b \
    libfribidi0 \
    libbz2-1.0 \
    liblzma5 \
    zlib1g \
    libexpat1 \
    libpng16-16 \
    # Hardware acceleration libraries
    libva-drm2 \
    libdrm2 \
    libva2 \
    # DVD support libraries
    libdvdread8 \
    libdvdnav4 \
    && rm -rf /var/lib/apt/lists/*

# Install libdvdcss for encrypted DVD support
RUN apt-get update && \
    # Install build dependencies
    apt-get install -y build-essential && \
    # Download and build libdvdcss from source
    cd /tmp && \
    curl -L https://download.videolan.org/pub/libdvdcss/1.4.3/libdvdcss-1.4.3.tar.bz2 | tar xj && \
    cd libdvdcss-1.4.3 && \
    ./configure --prefix=/usr/local && \
    make && make install && \
    ldconfig && \
    # Clean up
    cd / && rm -rf /tmp/libdvdcss-1.4.3 && \
    apt-get remove -y build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy extracted HandBrake and media libraries
COPY --from=flatpak-extractor /extracted-handbrake /opt/handbrake
COPY --from=flatpak-extractor /extracted-libs /opt/media-libs

# Create HandBrakeCLI wrapper script
RUN cat > /usr/local/bin/HandBrakeCLI <<'EOF'
#!/bin/bash
set -e

HANDBRAKE_CLI="/opt/handbrake/bin/HandBrakeCLI"

if [ ! -f "$HANDBRAKE_CLI" ]; then
    echo "Error: HandBrakeCLI not found at $HANDBRAKE_CLI" >&2
    exit 1
fi

# Set up library path with extracted media libraries and DVD support
export LD_LIBRARY_PATH="/opt/handbrake/lib:/opt/media-libs:/usr/local/lib:$LD_LIBRARY_PATH"

# Set DVD CSS library path for encrypted DVD support
export DVDCSS_CACHE="/tmp/dvdcss"
export DVDCSS_METHOD="key"
export DVDCSS_VERBOSE="0"

# Create cache directory if it doesn't exist
mkdir -p "$DVDCSS_CACHE"

# Debug mode
if [ "$1" = "--debug" ]; then
    echo "Using HandBrakeCLI: $HANDBRAKE_CLI" >&2
    echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
    echo "DVDCSS_CACHE=$DVDCSS_CACHE" >&2
    echo "Checking for libdvdcss..." >&2
    ldconfig -p | grep dvdcss || echo "libdvdcss not found in ldconfig" >&2
    ldd "$HANDBRAKE_CLI" 2>&1 | head -20 >&2 || echo "ldd failed" >&2
    shift
fi

# Run HandBrakeCLI
exec "$HANDBRAKE_CLI" "$@"
EOF

RUN chmod +x /usr/local/bin/HandBrakeCLI

# Show HandBrake version (for verification, but don't fail build if there are warnings)
RUN echo "=== HandBrake Installation Verification ===" \
    && /usr/local/bin/HandBrakeCLI --version 2>/dev/null | head -1 || echo "HandBrake installed (with warnings)"

# Create application user
RUN useradd -m -u 1001 appuser

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code
COPY . .

# Set proper ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create AACS directory (placeholder for now)
RUN mkdir -p /home/appuser/.config/aacs \
    && echo "AACS configuration placeholder" > /home/appuser/.config/aacs/README.txt

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command
CMD ["python3", "app.py"]
