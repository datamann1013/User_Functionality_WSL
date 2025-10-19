# RuneCore Artifacts Directory

This directory contains pre-built binaries and dependencies for the RuneCore ecosystem, organized by platform and architecture to optimize CI/CD pipeline performance and ensure consistent deployments.

## Directory Structure

```
artifacts/
├── linux/
│   ├── x86_64/           # Linux 64-bit binaries
│   └── arm64/            # Future: ARM64 Linux support
├── windows/
│   └── x86_64/
│       └── wsl2/         # WSL2-specific builds
├── containers/
│   ├── kali/             # Kali Linux container artifacts
│   ├── arch/             # Arch Linux container artifacts
│   └── debian/           # Debian container artifacts
└── checksums.txt         # SHA256 integrity verification
```

## Artifact Naming Convention

```
{component}-v{version}-{platform}-{arch}.{ext}
```

Examples:
- `runecore-v1.0.0-linux-x86_64.tar.gz`
- `runedrop-v1.2.3-windows-x86_64.zip`
- `runeguard-v2.1.0-linux-arm64.tar.gz`

## Artifact Management

### Retention Policy
- **Versions Kept**: Last 5 versions per component
- **Cleanup**: Automated via CI/CD pipeline
- **Storage**: Git LFS for large binaries (>100MB)

### Update Process
1. Successful CI/CD builds generate new artifacts
2. Artifacts are tested across platform matrix
3. Verified artifacts are committed to repository
4. Old versions are automatically cleaned up
5. Checksums are updated for integrity verification

### Integrity Verification
All artifacts include SHA256 checksums for verification:
```bash
# Verify artifact integrity
sha256sum -c checksums-linux-x86_64.txt
```

## Usage in CI/CD

### Faster Test Execution
Tests download pre-built artifacts instead of compiling from source:
```yaml
- name: Download Platform Artifacts
  run: |
    wget https://github.com/datamann1013/RuneCore_Ecosystem/raw/main/artifacts/linux/x86_64/runecore-latest.tar.gz
    tar -xzf runecore-latest.tar.gz
```

### Fallback Strategy
If artifacts are unavailable or corrupted, the pipeline falls back to source compilation:
```yaml
- name: Build from Source (Fallback)
  if: steps.download-artifacts.outcome == 'failure'
  run: |
    make build-all
```

## Component Artifacts

### RuneCore Foundation
- **Binary**: Core service daemon
- **Libraries**: Shared libraries for module communication
- **Configs**: Default configuration templates

### RuneDrop File Sharing
- **Binary**: File sharing service
- **UI Assets**: Web interface components
- **QR Generator**: QR code generation utilities

### RunePulse System Monitor
- **Binary**: System monitoring daemon
- **TUI**: Terminal user interface
- **Collectors**: Platform-specific metric collectors

### RuneGuard Security
- **Binary**: Security monitoring service
- **Rules**: Security pattern definitions
- **Tools**: Analysis and detection utilities

### RuneMind AI Integration
- **Models**: Pre-trained AI models (if applicable)
- **Service**: AI inference service
- **Adapters**: Platform-specific AI integrations

## Deployment Integration

Artifacts are used by:
- **install-runecore.sh**: Downloads appropriate platform artifacts
- **Docker builds**: Pre-built components for faster container builds
- **Package managers**: Distribution-specific packages
- **Development setup**: Quick local development environment

## Future Enhancements

### Planned Features
- **Digital Signatures**: GPG signing for artifact authenticity
- **Mirror Network**: Distributed artifact hosting
- **Delta Updates**: Incremental update packages
- **Multi-Architecture**: ARM64, RISC-V support

### Security Considerations
- All artifacts are built in isolated CI/CD environments
- Build provenance is tracked and auditable
- Checksums prevent tampering detection
- Regular vulnerability scanning of artifacts
