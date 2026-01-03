#!/bin/bash
set -e

# Colors and formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_step() {
  echo -e "\n${BOLD}${GREEN}=== $1 ===${NC}\n"
}

print_warning() {
  echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
  echo -e "${RED}ERROR: $1${NC}"
}

confirm() {
  echo -e -n "${BOLD}$1 (y/N) ${NC}"
  read -r response
  [[ "$response" == "y" ]]
}

# Header
echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════╗"
echo "║   jupyter-marimo-proxy release     ║"
echo "╚════════════════════════════════════╝"
echo -e "${NC}"

# Change to repo root
cd "$(dirname "$0")/.."

# Check if version type is provided
if [ -z "$1" ]; then
  echo -e "\nAvailable version types:"
  echo "  - minor (0.x.0)"
  echo "  - patch (0.0.x)"
  print_error "Please specify version type: ./scripts/release.sh <minor|patch>"
  exit 1
fi

VERSION_TYPE=$1

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(minor|patch)$ ]]; then
  print_error "Invalid version type. Use: minor or patch"
  exit 1
fi

# Check if on main branch
print_step "Checking git branch"
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
  print_error "Not on main branch. Current branch: $BRANCH"
  echo "Please run: git checkout main"
  exit 1
fi

# Check git state
print_step "Checking git status"
if [ -n "$(git status --porcelain)" ]; then
  print_error "Git working directory is not clean"
  echo "Please commit or stash your changes first:"
  git status
  exit 1
fi

# Pull latest changes
print_step "Pulling latest changes"
git pull origin main

# Get current version from python package (source of truth)
CURRENT_VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' jupyter_marimo_proxy/__init__.py)
echo "Current version: $CURRENT_VERSION"

# Parse version parts
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Calculate new version
if [ "$VERSION_TYPE" == "minor" ]; then
  MINOR=$((MINOR + 1))
  PATCH=0
elif [ "$VERSION_TYPE" == "patch" ]; then
  PATCH=$((PATCH + 1))
fi

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Update version in files
print_step "Updating version to $NEW_VERSION"

# Update jupyter_marimo_proxy/__init__.py
sed -i '' "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" jupyter_marimo_proxy/__init__.py

# Update labextension/package.json
sed -i '' "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" labextension/package.json

# Update package-lock.json
print_step "Updating package-lock.json"
cd labextension
npm install
cd ..

# Run Python linting
print_step "Running Python linting"
uvx ruff format --check . && uvx ruff check .

# Run Python tests
print_step "Running Python tests"
uv run pytest

# Run TypeScript checks
print_step "Running TypeScript checks"
cd labextension
npm run lint:check
npm run typecheck
cd ..

# Summary and confirmation
echo -e "\n${BOLD}Release Summary:${NC}"
echo "  • Old Version: $CURRENT_VERSION"
echo "  • New Version: $NEW_VERSION"
echo ""
echo "  ${BOLD}This release will:${NC}"
echo "    1. Commit version bump (3 files)"
echo "    2. Push to origin/main"
echo "    3. Create tag v$NEW_VERSION"
echo "    4. Push tag to trigger CI which will:"
echo "       - Build labextension"
echo "       - Publish to PyPI"

if ! confirm "Proceed with release?"; then
  print_warning "Release cancelled"
  # Restore files
  git checkout jupyter_marimo_proxy/__init__.py labextension/package.json labextension/package-lock.json
  exit 1
fi

# Commit version change
print_step "Committing version change"
git add jupyter_marimo_proxy/__init__.py labextension/package.json labextension/package-lock.json
git commit -m "release: v$NEW_VERSION"

# Push changes
if confirm "Push changes to remote?"; then
  git push origin main
  echo -e "${GREEN}✓ Changes pushed successfully${NC}"
fi

# Create and push tag
if confirm "Create and push tag v$NEW_VERSION?"; then
  git tag -a "v$NEW_VERSION" -m "release: v$NEW_VERSION"
  git push origin "v$NEW_VERSION"
  echo -e "${GREEN}✓ Tag pushed successfully${NC}"
fi

# Final success message
echo -e "\n${BOLD}${GREEN}🎉 Release v$NEW_VERSION completed successfully! 🎉${NC}\n"
echo -e "${YELLOW}Monitor the release:${NC}"
echo "  • GitHub Actions: https://github.com/marimo-team/jupyter-marimo-proxy/actions/workflows/publish.yml"
echo "  • PyPI Package: https://pypi.org/project/jupyter-marimo-proxy/$NEW_VERSION/"
echo ""
