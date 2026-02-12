#!/bin/bash
set -e

# Colors and formatting (matches release.sh)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

print_step() { echo -e "\n${BOLD}${GREEN}=== $1 ===${NC}\n"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}WARNING: $1${NC}"; }
print_error() { echo -e "${RED}ERROR: $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
confirm() { echo -e -n "${BOLD}$1 (y/N) ${NC}"; read -r response; [[ "$response" == "y" ]]; }

# Header
echo -e "${BOLD}${GREEN}"
echo "╔═════════════════════════════════════════════╗"
echo "║   marimo dependency version bump script     ║"
echo "╚═════════════════════════════════════════════╝"
echo -e "${NC}"

# Change to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)
print_info "Project root: $PROJECT_ROOT"

# Validate argument
if [ -z "$1" ]; then
  echo -e "\nUsage: ./scripts/bump-marimo.sh <new-version>"
  echo "  Example: ./scripts/bump-marimo.sh 0.20.0"
  exit 1
fi

NEW_VERSION=$1

# Validate version format
if ! echo "$NEW_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  print_error "Invalid version format. Expected X.Y.Z (e.g., 0.20.0)"
  exit 1
fi

# Auto-detect current version from executable.py (canonical source)
CURRENT_VERSION=$(sed -n 's/.*marimo\[sandbox\]>=\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' marimo_jupyter_extension/executable.py)

if [ -z "$CURRENT_VERSION" ]; then
  print_error "Could not detect current marimo version from executable.py"
  exit 1
fi

if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
  print_info "Already at version $NEW_VERSION"
  exit 0
fi

# Target files containing marimo version references
FILES=(
  "marimo_jupyter_extension/executable.py"
  "marimo_jupyter_extension/handlers.py"
  "README.md"
  "CLAUDE.md"
  "docs/installation.md"
  "docs/index.md"
  "docs/jupyterhub.md"
  "docs/troubleshooting.md"
)

# Summary
print_step "Version Bump Summary"
print_info "Current version (from executable.py): $CURRENT_VERSION"
print_info "New version: $NEW_VERSION"
echo ""
echo "Files to update:"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    echo "  $f"
  else
    echo "  $f (NOT FOUND - skipping)"
  fi
done

if ! confirm "Proceed with version bump?"; then
  print_warning "Cancelled"
  exit 1
fi

# Replace current version with new version in all target files
print_step "Updating versions"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    sed -i.bak "s/$CURRENT_VERSION/$NEW_VERSION/g" "$f"
    rm -f "$f.bak"
    print_success "Updated $f"
  fi
done

# Show changes
print_step "Changes"
git diff --stat
echo ""
git diff

# Commit
if confirm "Commit changes?"; then
  git add "${FILES[@]}"
  git commit -m "bump: marimo $NEW_VERSION"
  print_success "Committed: bump: marimo $NEW_VERSION"
else
  print_warning "Not committed. Review changes and commit manually."
fi
