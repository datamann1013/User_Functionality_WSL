#!/usr/bin/env bash
docker build -f docker/dev-base/python-slim-base.Dockerfile -t runecore/python-slim-dev:latest docker/
docker build -f docker/dev-base/python-alpine-base.Dockerfile -t runecore/python-alpine-dev:latest docker/
docker build -f docker/dev-base/node-base.Dockerfile -t runecore/node-dev:latest docker/
docker build -f docker/dev-base/rust-builder-base.Dockerfile -t runecore/rust-builder-dev:latest docker/
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

ARTIFACT_DIR="$ROOT/artifacts/dev-bases"
mkdir -p "$ARTIFACT_DIR"

build_and_save() {
	local dockerfile="$1"
	local tag="$2"
	local tries=${3:-3}
	local attempt=1
	while [ $attempt -le $tries ]; do
		echo "Building $tag (attempt $attempt/$tries) from $dockerfile"
		if docker build -f "$dockerfile" -t "$tag" docker/; then
			echo "Build succeeded: $tag"
			# Save image tarball for fast local reuse
			tarfile="$ARTIFACT_DIR/$(echo "$tag" | tr '/:' '_').tar"
			echo "Saving $tag -> $tarfile"
			docker save -o "$tarfile" "$tag"
			return 0
		else
			echo "Build failed for $tag (attempt $attempt)"
			attempt=$((attempt+1))
			sleep 2
		fi
	done
	echo "Failed to build $tag after $tries attempts" >&2
	return 1
}

build_and_save docker/dev-base/python-slim-base.Dockerfile runecore/python-slim-dev:latest || exit 1
build_and_save docker/dev-base/python-alpine-base.Dockerfile runecore/python-alpine-dev:latest || true
build_and_save docker/dev-base/node-base.Dockerfile runecore/node-dev:latest || true
build_and_save docker/dev-base/rust-builder-base.Dockerfile runecore/rust-builder-dev:latest || true

echo "Built and saved dev base images (where builds succeeded) to $ARTIFACT_DIR"
