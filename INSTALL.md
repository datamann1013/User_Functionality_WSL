# RuneCore Distributed Installation

This document describes the distributed installation system for RuneCore, which allows users to install the complete ecosystem with a single command, without needing the full codebase.

## Quick Installation

Users can install RuneCore with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore.sh | bash
```

## What Gets Installed

The installer automatically sets up:

### Services
- **Ollama AI Service** (Port 11434) - Local AI model management
- **RuneGuard Security** (Port 5001) - Error monitoring and security
- **RuneMind Backend** (Port 5000) - AI processing and API
- **RuneMind Frontend** (Port 3000) - Web interface

### Installation Structure
```
~/.runecore/
├── docker-compose.yml     # Service orchestration
├── runecore              # Management script
├── data/                 # Persistent data
│   ├── ollama/          # AI models and cache
│   ├── guard/           # Security data
│   └── backend/         # Application data
├── logs/                # Service logs
│   ├── guard/
│   ├── backend/
│   └── frontend/
└── config/              # Configuration files
```

## Management Commands

After installation, users can manage RuneCore with:

```bash
# Start all services
~/.runecore/runecore start

# Stop all services
~/.runecore/runecore stop

# Check service status
~/.runecore/runecore status

# View logs (all or specific service)
~/.runecore/runecore logs
~/.runecore/runecore logs backend

# Update to latest versions
~/.runecore/runecore update

# Complete uninstall
~/.runecore/runecore uninstall
```

## Docker Images

The system uses the existing Dockerfiles from each component to ensure production builds match development:

- **ErrorLogger Service**: Built from `projects/ErrorLogger/Dockerfile`
- **Backend Service**: Built from `projects/ai_service/docker/Dockerfile.backend`  
- **Frontend Service**: Built from `projects/ai_service/docker/Dockerfile.frontend`
- **Ollama AI Service**: Uses official `ollama/ollama:latest` image

Pre-built images are automatically published to GitHub Container Registry:
- `ghcr.io/datamann1013/runecore_ecosystem-errorlogger:latest`
- `ghcr.io/datamann1013/runecore_ecosystem-backend:latest`
- `ghcr.io/datamann1013/runecore_ecosystem-frontend:latest`

## System Requirements

### Minimum Requirements
- **OS**: Linux, WSL2, or macOS
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space (more for AI models)
- **Docker**: Docker and Docker Compose installed

### Supported Platforms
- Ubuntu/Debian (native Docker support)
- Arch Linux (native Docker support) 
- WSL2 with Docker Desktop
- macOS with Docker Desktop

## Installation Process

The installer performs these steps:

1. **System Validation**
   - Checks OS compatibility
   - Verifies Docker installation and permissions
   - Validates network connectivity

2. **Directory Setup**
   - Creates `~/.runecore/` structure
   - Sets up data and log directories
   - Configures proper permissions

3. **Configuration Download**
   - Downloads docker-compose.yml from GitHub
   - Falls back to embedded config if needed
   - Configures environment variables

4. **Image Deployment**
   - Pulls latest Docker images
   - Starts services with health checks
   - Configures networking and volumes

5. **AI Model Setup**
   - Downloads recommended AI model (llama3.2:1b)
   - Configures Ollama for local inference
   - Tests AI functionality

6. **Management Tools**
   - Creates management script
   - Adds to user PATH
   - Provides usage instructions

## Security Features

### Network Security
- All services run in isolated Docker network
- No external network access required for operation
- Local-only communication between services

### Data Security
- All data stored locally in user directory
- No cloud dependencies or telemetry
- Encrypted inter-service communication

### Access Control
- Services run as non-root users in containers
- Minimal required permissions
- Isolated file systems

## Troubleshooting

### Common Issues

**Docker Permission Denied**
```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

**Port Conflicts**
```bash
# Check what's using ports
sudo netstat -tlnp | grep -E ':(3000|5000|5001|11434)'

# Stop conflicting services or modify docker-compose.yml
```

**Low Disk Space**
```bash
# Clean up Docker
docker system prune -a

# Check AI model usage
docker exec runecore-ollama du -sh /root/.ollama/
```

### Getting Help

1. Check service logs: `~/.runecore/runecore logs`
2. Verify service status: `~/.runecore/runecore status`
3. Test connectivity: `curl http://localhost:5000/health`
4. Restart services: `~/.runecore/runecore restart`

## Development Notes

### Building Images Locally

For development, you can build images locally using the existing Dockerfiles:

```bash
# Build all images using existing component Dockerfiles
docker-compose -f docker/docker-compose.prod.yml build

# Build specific service using component's Dockerfile  
cd projects/ai_service && docker build -f docker/Dockerfile.backend -t runecore-backend .
cd projects/ai_service && docker build -f docker/Dockerfile.frontend -t runecore-frontend .
cd projects/ErrorLogger && docker build -f Dockerfile -t runecore-errorlogger .
```

### Updating the Installer

The installer script is version-controlled and can be updated:

1. Modify `install-runecore.sh`
2. Push to main branch
3. GitHub Actions automatically builds new images
4. Users get updates with `runecore update`

### CI/CD Pipeline

GitHub Actions automatically:
- Builds Docker images on push to main
- Publishes to GitHub Container Registry
- Creates release artifacts
- Runs security scans on images

This distributed installation system makes RuneCore accessible to users without requiring the full development environment or source code access.
