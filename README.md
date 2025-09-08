# Disk Extractor - Movie Metadata Manager

A modern web-based application for managing movie metadata and encoding .img movie files with HandBrake integration, real-time WebSocket updates, and comprehensive encoding queue management.

## Features

### Core Functionality
- **Real-time Web Interface**: Modern, responsive UI with WebSocket-based live updates
- **File Management**: Automatic scanning and monitoring of .img files with file system watcher
- **Multi-title Support**: Scan and manage multiple titles per disc with individual metadata
- **Enhanced Metadata**: Rich metadata including audio/subtitle tracks, duration, and technical details
- **Visual Status Indicators**: Color-coded file status (green=has metadata, red=no metadata)

### Encoding & Processing
- **HandBrake Integration**: Built-in HandBrake CLI for video processing with real-time progress
- **Encoding Queue**: Multi-job queue system with status tracking and progress monitoring
- **Template System**: Customizable encoding presets and settings management
- **Concurrent Processing**: Configurable concurrent encoding jobs
- **Progress Tracking**: Real-time encoding progress with FPS, bitrate, and time estimates

### Advanced Features
- **WebSocket Communication**: Real-time updates for file changes, encoding progress, and notifications
- **File System Monitoring**: Automatic detection of new/modified/deleted files
- **Caching System**: Intelligent caching of HandBrake scan results and metadata
- **Security**: Path traversal protection, input validation, and security headers
- **Docker Ready**: Containerized with all dependencies and user ID mapping

## Quick Start

### Option 1: Docker Compose (Recommended)

1. **Configure your movie directory:**
   ```bash
   # Edit docker-compose.yml and update the volume path:
   - /your/movie/directory:/movies
   ```

2. **Start the application:**
   ```bash
   docker-compose up -d
   ```

3. **Access the web interface:**
   ```
   http://localhost:5000
   ```

### Option 2: Manual Docker Build

```bash
# Build the image
docker build -t disk-extractor .

# Run with volume mount
docker run -d -p 5000:5000 \
  -v /path/to/your/movies:/movies \
  --name disk-extractor \
  disk-extractor:latest \
  python3 app.py /movies
```

## Web Interface

### Main Layout
- **Left Sidebar**: File list with color-coded status indicators and encoding section
- **Main Content**: Metadata editing interface with title management
- **Real-time Updates**: Live file list updates and encoding progress via WebSocket

### File Status Colors
- 🟢 **Green**: File has complete metadata
- 🔴 **Red**: File missing metadata
- 🟡 **Yellow**: File currently being encoded
- 🔵 **Blue**: File queued for encoding

### Key Interface Elements
- **Scan Media Button**: Triggers HandBrake scan to detect titles and tracks
- **Title Cards**: Individual metadata forms for each detected title
- **Encoding Controls**: Queue management and progress monitoring
- **Settings Page**: Encoding presets and application configuration

## API Endpoints

### Core Web Interface
- `GET /` - Main web interface
- `GET /settings` - Settings and configuration page
- `GET /setup` - Initial directory setup (if no directory configured)
- `GET /health` - Health check with HandBrake and system status

### File Management API
- `GET /api/file_list` - Get current file list with metadata status
- `POST /api/save_metadata` - Save metadata for a specific file
- `GET /api/enhanced_metadata/<filename>` - Get enhanced metadata with HandBrake scan results
- `GET /api/scan_file/<filename>` - Trigger HandBrake scan for specific file
- `GET /api/raw_output/<filename>` - Get raw HandBrake CLI output for debugging
- `GET /api/handbrake/test` - Test HandBrake functionality

### Encoding Queue API
- `POST /api/encoding/queue` - Queue a title for encoding
- `DELETE /api/encoding/queue/<job_id>` - Remove job from queue
- `POST /api/encoding/cancel/<job_id>` - Cancel active encoding job
- `GET /api/encoding/status` - Get status of all encoding jobs
- `GET /api/encoding/progress/<job_id>` - Get progress for specific job
- `GET /api/encoding/file/<file_name>/jobs` - Get all jobs for specific file
- `POST /api/encoding/queue/bulk` - Perform bulk queue operations
- `GET /api/encoding/failure-logs/<file_name>/<title_number>` - Get failure logs
- `POST /api/encoding/clear-failure/<file_name>/<title_number>` - Clear failed job
- `POST /api/encoding/output-file-size` - Get output file size
- `POST /api/encoding/delete` - Delete output file and remove from history
- `GET /api/encoding/download/<filename>` - Download completed encoded file

### Settings API
- `GET /api/settings` - Get current encoding settings
- `POST /api/settings` - Update encoding settings

### Template Management API
- `GET /api/templates` - List all available templates
- `POST /api/templates/upload` - Upload new HandBrake template
- `GET /api/templates/<template_name>` - Get specific template details
- `DELETE /api/templates/<template_name>` - Delete template
- `POST /api/templates/validate` - Validate template without saving
- `POST /api/templates/preview-command` - Preview HandBrake command

### Directory Management API
- `POST /api/directory/browse` - Browse directories on server

### WebSocket Events
- `connect/disconnect` - Client connection management
- `file_list_update` - Real-time file list changes
- `encoding_progress` - Live encoding progress updates
- `encoding_status_change` - Job status changes
- `metadata_updated` - Metadata change notifications
- `notification` - System notifications

## File Formats

### Metadata Files (.mmm)
Stored alongside .img files with enhanced multi-title structure:

```json
{
  "file_name": "movie.img",
  "size_mb": 4500.2,
  "titles": [
    {
      "title_number": 1,
      "selected": true,
      "movie_name": "Example Movie",
      "release_date": "2023-01-01",
      "synopsis": "A great movie about...",
      "duration_seconds": 7200,
      "audio_tracks": [
        {
          "track_number": 1,
          "language": "English",
          "codec": "DTS-HD MA",
          "channels": "5.1",
          "selected": true
        }
      ],
      "subtitle_tracks": [
        {
          "track_number": 1,
          "language": "English",
          "format": "PGS",
          "selected": false
        }
      ],
      "selected_audio_tracks": [1],
      "selected_subtitle_tracks": []
    }
  ],
  "encoding": {
    "jobs": [
      {
        "job_id": "movie_title1_abc123",
        "title_number": 1,
        "status": "completed",
        "output_filename": "Example Movie (2023).mp4",
        "output_path": "/movies/Example Movie (2023).mp4",
        "created_at": "2023-01-01T12:00:00",
        "completed_at": "2023-01-01T14:30:00",
        "output_size_mb": 2100.5
      }
    ]
  }
}
```

### Encoding Settings (encoding_settings.json)
```json
{
  "max_concurrent_encodes": 1,
  "testing_mode": false,
  "test_duration_seconds": 30,
  "output_directory": "/movies",
  "default_preset": "Fast 1080p30",
  "auto_queue_new_files": false,
  "progress_update_interval": 1,
  "notification_settings": {
    "on_completion": true,
    "on_failure": true,
    "on_queue_empty": true
  }
}
```

## Configuration

### Environment Variables
```bash
# HandBrake settings
HANDBRAKE_TIMEOUT=120
HANDBRAKE_CLI_PATH=/usr/local/bin/HandBrakeCLI

# Cache settings
MAX_CACHE_SIZE=100
CACHE_TTL=3600
ENCODING_JOBS_CACHE_TTL=600

# Flask settings
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
LOG_LEVEL=INFO

# File watching
FILE_WATCHER_ENABLED=true
FILE_WATCHER_DEBOUNCE_DELAY=2.0
```

### Docker Compose Configuration
```yaml
services:
  disk-extractor:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        USER_ID: 1000
        GROUP_ID: 1000
    ports:
      - "5000:5000"
    volumes:
      - /your/movies:/movies
      - ./settings:/app/settings
    environment:
      - LOG_LEVEL=INFO
    command: ["python3", "app.py", "/movies"]
```

## Usage Workflow

### 1. Initial Setup
1. Configure movie directory in docker-compose.yml
2. Start application with `docker-compose up -d`
3. Access web interface at http://localhost:5000

### 2. File Management
1. Application automatically scans for .img files
2. Files appear in left sidebar with status indicators
3. Click file to view/edit metadata
4. Use "Scan Media" to detect titles and tracks

### 3. Metadata Editing
1. Select file from sidebar
2. Click "Scan Media" to detect available titles
3. Edit metadata for each title (auto-saves)
4. Configure audio/subtitle track selections

### 4. Encoding Process
1. Select titles to encode from metadata interface
2. Choose encoding preset and settings
3. Queue jobs for processing
4. Monitor progress in real-time
5. Download completed files

## Technical Architecture

### Backend Components
- **Flask Application**: Main web server with SocketIO for real-time updates
- **Metadata Manager**: Handles .mmm file operations and caching
- **Encoding Engine**: Manages HandBrake job queue and processing
- **File Watcher**: Monitors filesystem changes for automatic updates
- **Template Manager**: Handles encoding preset management

### Frontend Components
- **WebSocket Client**: Real-time communication with server
- **File List Manager**: Dynamic file list with status updates
- **Metadata Editor**: Multi-title metadata editing interface
- **Encoding Monitor**: Real-time progress tracking and queue management

### Security Features
- Path traversal protection
- Input validation and sanitization
- Security headers (CSP, XSS protection)
- File access restrictions
- Request logging and monitoring

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python3 app.py /path/to/movies
```

### Testing
```bash
# Run test suite
python3 run_tests.py
```

## Troubleshooting

### HandBrake Issues
```bash
# Check HandBrake status
curl http://localhost:5000/api/handbrake/test

# Test HandBrake directly
docker exec disk-extractor /usr/local/bin/HandBrakeCLI --version
```

### File Permissions
```bash
# Fix ownership for container user (UID 1000)
sudo chown -R 1000:1000 /path/to/movies

# Or make readable by all
chmod -R 755 /path/to/movies
```

### WebSocket Connection Issues
- Check browser console for connection errors
- Verify port 5000 is accessible
- Check container logs: `docker-compose logs -f`

### Encoding Problems
- Check encoding settings in `/settings/encoding_settings.json`
- Monitor logs for HandBrake errors
- Verify sufficient disk space for output files

## System Requirements

- **Docker & Docker Compose** (recommended)
- **Python 3.12+** (for local development)
- **Minimum 2GB RAM** (4GB+ recommended for encoding)
- **Sufficient disk space** for input and output files

## License

This project is open source. See LICENSE file for details.
