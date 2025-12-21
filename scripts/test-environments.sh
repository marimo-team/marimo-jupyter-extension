#!/usr/bin/env bash
#
# Test Environment Setup Script
#
# Creates N test Python environments (venv, virtualenv, conda) and launches JupyterLab
# for testing the Jupyter kernel selection feature.
#
# Uses `uv` and `uvx` for environment management:
#   - uv venv: Create virtual environments
#   - uvx virtualenv: Run virtualenv without installing globally
#   - uvx conda: Run conda without installing globally
#   - uv pip: Fast package installation
#   - uv run: Run commands in the environment
#
# Usage:
#   ./scripts/test-environments.sh                    # Default: 1 conda env
#   ./scripts/test-environments.sh --venv 2 --conda 1 # 2 venv + 1 conda
#   ./scripts/test-environments.sh --help              # Show help
#

set -ex

# Colors and formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
TEST_ENV_DIR=".test-envs"
KERNEL_NAMES=()
CONDA_ENVS=()

# Default values
NUM_VENV=0
NUM_VIRTUALENV=0
NUM_CONDA=0

# Functions
print_header() {
  echo -e "${BOLD}${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

show_help() {
  cat << EOF
${BOLD}Usage:${NC} $0 [OPTIONS]

Create test Python environments and launch JupyterLab for testing kernel selection.

${BOLD}Options:${NC}
  --venv N        Create N venv environments (default: 0)
  --virtualenv N  Create N virtualenv environments (default: 0)
  --conda N       Create N conda environments (default: 0, or 1 if no args)
  --help          Show this help message

${BOLD}Examples:${NC}
  $0                                    # Create 1 conda environment (default)
  $0 --venv 2 --conda 1                 # Create 2 venv and 1 conda
  $0 --venv 1 --virtualenv 1 --conda 1  # Create one of each

${BOLD}Behavior:${NC}
  • If no arguments: Creates 1 conda environment
  • If arguments provided: Only creates what's specified (no defaults)

${BOLD}Cleanup:${NC}
  The script automatically cleans up all environments when:
  • JupyterLab exits normally
  • Ctrl+C is pressed
  • Script encounters an error

${BOLD}Testing:${NC}
  1. Run this script to create test environments
  2. JupyterLab opens automatically
  3. Click "New marimo Notebook" in the launcher
  4. Select from the dropdown (includes "Default (no venv)" + test environments)
  5. Verify marimo starts with the selected environment
  6. Press Ctrl+C to exit and cleanup

EOF
}

# Parse command-line arguments
parse_args() {
  # If no arguments provided, default to 1 conda
  if [[ $# -eq 0 ]]; then
    NUM_CONDA=1
    return
  fi

  while [[ $# -gt 0 ]]; do
    case $1 in
      --venv)
        NUM_VENV="$2"
        shift 2
        ;;
      --virtualenv)
        NUM_VIRTUALENV="$2"
        shift 2
        ;;
      --conda)
        NUM_CONDA="$2"
        shift 2
        ;;
      --help)
        show_help
        exit 0
        ;;
      *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
    esac
  done
}

# Cleanup function - runs on exit, interrupt, or error
cleanup() {
  print_header "Cleaning up test environments"

  # Unregister kernels
  if [[ ${#KERNEL_NAMES[@]} -gt 0 ]]; then
    echo "Unregistering kernels: ${KERNEL_NAMES[*]}"
    for kernel in "${KERNEL_NAMES[@]}"; do
      uvx jupyter kernelspec remove -y "$kernel" 2>/dev/null || true
    done
    print_success "Kernels unregistered"
  fi

  # Remove venv/virtualenv directories
  if [ -d "$TEST_ENV_DIR" ]; then
    echo "Removing environment directories from $TEST_ENV_DIR"
    rm -rf "$TEST_ENV_DIR"
    print_success "Environment directories removed"
  fi

  # Remove conda environments
  if [[ ${#CONDA_ENVS[@]} -gt 0 ]]; then
    echo "Removing conda environments: ${CONDA_ENVS[*]}"
    for env in "${CONDA_ENVS[@]}"; do
      if command -v conda &> /dev/null; then
        conda env remove -n "$env" -y 2>/dev/null || true
      elif command -v mamba &> /dev/null; then
        mamba env remove -n "$env" -y 2>/dev/null || true
      fi
    done
    print_success "Conda environments removed"
  fi

  echo -e "\n${GREEN}Cleanup complete!${NC}\n"
}

# Set up trap for cleanup on exit, interrupt, or error
trap cleanup EXIT INT TERM

# Create venv environment using uv
create_venv() {
  local num=$1
  local name="test-venv-$num"
  local dir="$TEST_ENV_DIR/$name"

  echo "Creating venv: $name"
  uv venv --seed "$dir"

  # Install ipykernel and register kernel using uv with the venv
  uv pip install --python "$dir/bin/python" -q ipykernel
  "$dir/bin/python" -m ipykernel install --user --name "$name" --display-name "Test venv #$num" 2>/dev/null

  KERNEL_NAMES+=("$name")
  print_success "Created venv: $name"
}

# Create virtualenv environment using uvx
create_virtualenv() {
  local num=$1
  local name="test-virtualenv-$num"
  local dir="$TEST_ENV_DIR/$name"

  echo "Creating virtualenv: $name"
  uvx virtualenv -q "$dir"

  # Install ipykernel and register kernel using uv with the venv
  uv pip install --python "$dir/bin/python" -q ipykernel
  "$dir/bin/python" -m ipykernel install --user --name "$name" --display-name "Test virtualenv #$num" 2>/dev/null

  KERNEL_NAMES+=("$name")
  print_success "Created virtualenv: $name"
}

# Create conda environment (requires conda/mamba to be installed)
create_conda_env() {
  local num=$1
  local name="test-conda-$num"

  echo "Creating conda environment: $name"

  # Run conda operations in a subshell to isolate environment changes
  (
    if command -v conda &> /dev/null; then
      eval "$(conda shell.bash hook)" 2>/dev/null || true
      conda create -y -q -n "$name" python=3.10 || conda create -y -q -n "$name" python
      conda run -n "$name" python -c "import sys; print(sys.executable)"
    elif command -v mamba &> /dev/null; then
      eval "$(mamba shell.bash hook)" 2>/dev/null || true
      mamba create -y -q -n "$name" python=3.10 || mamba create -y -q -n "$name" python
      mamba run -n "$name" python -c "import sys; print(sys.executable)"
    fi
  ) 2>/dev/null | {
    read -r conda_python

    if [ -n "$conda_python" ]; then
      uv pip install --python "$conda_python" -q ipykernel
      "$conda_python" -m ipykernel install --user --name "$name" --display-name "Test conda #$num" 2>/dev/null
      CONDA_ENVS+=("$name")
      KERNEL_NAMES+=("$name")
      print_success "Created conda environment: $name"
    else
      print_warning "Failed to create conda environment: $name"
    fi
  }
}

# Main execution
main() {
  parse_args "$@"

  # Banner
  echo -e "\n${BOLD}${GREEN}"
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  Test Environment Setup for Kernel Selection      ║"
  echo "╚═══════════════════════════════════════════════════╝"
  echo -e "${NC}"

  print_header "Environment Configuration"
  echo "Creating environments:"
  echo "  • venv:       $NUM_VENV"
  echo "  • virtualenv: $NUM_VIRTUALENV"
  echo "  • conda:      $NUM_CONDA"
  echo ""

  # Create test environment directory if needed
  if [[ $NUM_VENV -gt 0 || $NUM_VIRTUALENV -gt 0 ]]; then
    mkdir -p "$TEST_ENV_DIR"
  fi

  # Create venv environments
  if [[ $NUM_VENV -gt 0 ]]; then
    print_header "Creating venv environments"
    for i in $(seq 1 "$NUM_VENV"); do
      create_venv "$i"
    done
  fi

  # Create virtualenv environments
  if [[ $NUM_VIRTUALENV -gt 0 ]]; then
    print_header "Creating virtualenv environments"
    for i in $(seq 1 "$NUM_VIRTUALENV"); do
      create_virtualenv "$i"
    done
  fi

  # Create conda environments
  if [[ $NUM_CONDA -gt 0 ]]; then
    print_header "Creating conda environments"
    for i in $(seq 1 "$NUM_CONDA"); do
      create_conda_env "$i"
    done
  fi

  # Summary
  echo ""
  print_header "Summary"
  echo "Total environments created: $((NUM_VENV + NUM_VIRTUALENV + NUM_CONDA))"
  if [[ ${#KERNEL_NAMES[@]} -gt 0 ]]; then
    echo "Registered kernels:"
    for kernel in "${KERNEL_NAMES[@]}"; do
      echo "  • $kernel"
    done
  fi

  echo ""
  print_header "Launching JupyterLab"
  echo "Testing tip:"
  echo "  1. Click 'New marimo Notebook' in the launcher"
  echo "  2. Select different environments from the dropdown"
  echo "  3. See 'Default (no venv)' + your test environments"
  echo "  4. Press Ctrl+C here to exit and cleanup"
  echo ""

  # Re-build
  uv pip install -e .
  # Launch JupyterLab using uv
  uv run jupyter lab
}

main "$@"
