#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

ARTIFACT_DIR="$ROOT/artifacts/dev-bases"
mkdir -p "$ARTIFACT_DIR"

# Usage: ./scripts/build_dev_bases.sh [--dispatch]
# Environment:
#  GH_ACTIONS_TOKEN - optional PAT with repo/workflow permissions; if provided or --dispatch is passed,
#                     the script will trigger the GitHub Actions workflow to publish to GHCR.

DISPATCH=false
if [ "${1:-}" = "--dispatch" ]; then
	DISPATCH=true
fi

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

# Optionally dispatch the GitHub Actions workflow to publish these images to GHCR.
if [ "$DISPATCH" = "true" ] || [ -n "${GH_ACTIONS_TOKEN:-}" ]; then
	# Prefer explicit token env var GH_ACTIONS_TOKEN; otherwise fall back to GITHUB_TOKEN if exported.
	TOKEN="${GH_ACTIONS_TOKEN:-${GITHUB_TOKEN:-}}"
	if [ -z "$TOKEN" ]; then
		echo "Dispatch requested but GH_ACTIONS_TOKEN or GITHUB_TOKEN not set" >&2
		exit 1
	fi

	echo "Dispatching GitHub Actions workflow 'publish-dev-bases.yml'..."
		REPO_FULL="$(basename "$ROOT")"
		# Allow explicit override of owner via GH_OWNER. Otherwise derive owner from git remote if possible.
		if [ -n "${GH_OWNER:-}" ]; then
			OWNER="$GH_OWNER"
		else
			OWNER="$(git config --get remote.origin.url 2>/dev/null || true)"
			if echo "$OWNER" | grep -q ':'; then
				# formats like git@github.com:owner/repo.git or https://github.com/owner/repo.git
				OWNER="$(echo "$OWNER" | sed -E 's#.*[:/]{1}([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(.git)?#\1#')"
			else
				OWNER="${GITHUB_ACTOR:-}"  # fallback
			fi
		fi
	if [ -z "$OWNER" ]; then
		echo "Unable to determine GitHub owner; set GH_OWNER env var or run this script from a repo clone with origin configured." >&2
		exit 1
	fi

	API_URL="https://api.github.com/repos/$OWNER/$REPO_FULL/actions/workflows/publish-dev-bases.yml/dispatches"
	PAYLOAD="{\"ref\": \"main\"}"
	http_status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL" \
		-H "Accept: application/vnd.github+json" \
		-H "Authorization: Bearer $TOKEN" \
		-H "Content-Type: application/json" \
		-d "$PAYLOAD")
	if [ "$http_status" -ge 200 ] && [ "$http_status" -lt 300 ]; then
		echo "Workflow dispatched successfully (HTTP $http_status)."
	else
		echo "Failed to dispatch workflow (HTTP $http_status). Check token and repository path." >&2
		exit 1
	fi
fi

