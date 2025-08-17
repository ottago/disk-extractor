# Disk Extractor - Movie Metadata Manager

A web-based application for managing movie metadata stored alongside .img movie files, with HandBrake integration for video processing.

## Features

- **Web Interface**: Modern, responsive web UI for managing movie metadata
- **File Management**: Automatically scans directories for .img files
- **Metadata Editing**: Edit movie name, release date, and synopsis with auto-save
- **Visual Status**: Color-coded indicators for files with/without metadata
- **HandBrake Integration**: Built-in HandBrake CLI for video processing
- **Docker Ready**: Containerized application with all dependencies

## Quick Start

### Option 1: Docker Compose (Recommended)

1. **Edit the movie directory path:**
   ```bash
   # Edit docker-compose.yml and change this line:
   - /path/to/your/movies:/movies
   # to your actual movie directory, for example:
   - /home/user/Movies:/movies
   ```

2. **Start the application:**
   ```bash
   # You may require this library to build the image.
   sudo apt install python3-setuptools
   docker-compose up -d
   ```

3. **Access the web interface:**
   ```
   http://localhost:5000
   ```

### Option 2: Environment Variables

1. **Create a .env file:**
   ```bash
   cp .env.example .env
   # Edit .env and set your movie directory path
   ```

2. **Start with environment config:**
   ```bash
   docker-compose -f docker-compose.env.yml up -d
   ```

### Option 3: Manual Docker Build

```bash
# Build the Docker image
./build.sh

# Run with volume mount
sudo docker run -d -p 5000:5000 \
  -v /path/to/your/movies:/movies \
  --name disk-extractor \
  disk-extractor:latest \
  python3 app.py /movies
```

## Configuration

### Docker Compose Configuration

**Basic setup** (edit `docker-compose.yml`):
```yaml
volumes:
  - /home/user/Movies:/movies  # Change this path
```

**Environment-based setup** (create `.env` file):
```bash
MOVIES_DIR=/home/user/Movies
PORT=5000
```

### Directory Structure

Your movie directory should contain:
- `.img` files: Your movie files
- `.mmm` files: JSON metadata files (created automatically)

Example:
```
/home/user/Movies/
├── movie1.img
├── movie1.mmm          # Created automatically
├── movie2.img
└── movie2.mmm          # Created automatically
```

## Usage

1. **Setup**: The application will automatically use the mounted directory
2. **Browse**: View all .img files with color-coded metadata status
   - 🟢 Green: Has metadata
   - 🔴 Red: No metadata
3. **Edit**: Click on any file to edit its metadata (auto-saves as you type)
4. **Navigate**: Use arrow keys for keyboard navigation

## Metadata Format

```json
{
  "movie_name": "Example Movie",
  "release_date": "2023-01-01",
  "synopsis": "A great movie about...",
  "file_name": "example.img"
}
```

## HandBrake Integration

The application includes HandBrake CLI for video processing:

```bash
# Test HandBrake in the container
docker exec disk-extractor /usr/local/bin/HandBrakeCLI --version

# Use HandBrake for processing
docker exec disk-extractor /usr/local/bin/HandBrakeCLI \
  --input /movies/movie.img \
  --output /movies/movie.mp4 \
  --preset "Fast 1080p30"
```

## Management Commands

```bash
# View logs
docker-compose logs -f

# Stop the application
docker-compose down

# Restart the application
docker-compose restart

# Update the application
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## API Endpoints

- `GET /` - Main interface
- `GET /setup` - Directory setup page (if no directory specified)
- `POST /api/save_metadata` - Save metadata for a file
- `GET /api/file_list` - Get updated file list
- `GET /health` - Health check with HandBrake status
- `GET /api/handbrake/test` - Test HandBrake functionality

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python3 app.py /path/to/movies
```

### Docker Development

```bash
# Build development image
docker-compose build

# Run with live code mounting
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

## Technical Details

- **Base Image**: Ubuntu 24.04 (for GLIBC 2.39 compatibility)
- **HandBrake**: Extracted from Flatpak with selective media codec libraries
- **Python**: 3.12 with Flask web framework
- **Port**: 5000 (configurable via environment)
- **User**: Non-root (appuser, UID 1001)

## Troubleshooting

### HandBrake Issues
```bash
# Check HandBrake status
curl http://localhost:5000/api/handbrake/test

# Debug HandBrake libraries
docker exec disk-extractor /usr/local/bin/HandBrakeCLI --debug --version
```

### Container Issues
```bash
# Check container logs
docker-compose logs disk-extractor

# Access container shell
docker exec -it disk-extractor bash
```

### File Permissions
Ensure your movie directory is readable by the container (UID 1001):
```bash
# Fix permissions if needed
sudo chown -R 1001:1001 /path/to/your/movies
# Or make it readable by all
chmod -R 755 /path/to/your/movies
```

### Port Conflicts
If port 5000 is in use, change it in docker-compose.yml:
```yaml
ports:
  - "8080:5000"  # Use port 8080 instead
```

## License

This project is open source. See LICENSE file for details.
