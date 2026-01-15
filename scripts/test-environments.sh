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

# set -ex

# Colors and formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
TEST_ENV_DIR=".test-envs"
CONDA_ENVS_DIR="$TEST_ENV_DIR/conda-envs"
CONDA_PKGS_DIR="$TEST_ENV_DIR/conda-pkgs"

# Export conda environment variables for isolation
export CONDA_ENVS_PATH="$CONDA_ENVS_DIR"
export CONDA_PKGS_DIRS="$CONDA_PKGS_DIR"

KERNEL_NAMES=()
CONDA_ENVS=()

# Environment specs arrays - each entry is "marimo|pkg1,pkg2" or "no-marimo|pkg1,pkg2"
# Format: "<marimo-flag>|<comma-separated-packages>"
VENV_SPECS=()
VIRTUALENV_SPECS=()
CONDA_SPECS=()
LAST_TYPE=""  # Tracks which array was last modified (for --no-marimo and --with)

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
By default, marimo[sandbox] is installed in each environment.

${BOLD}Options:${NC}
  --venv [N]      Create N venv environments (default: 1 if N omitted)
  --virtualenv [N] Create N virtualenv environments (default: 1 if N omitted)
  --conda [N]     Create N conda environments (default: 1 if N omitted)
  --no-marimo     Don't install marimo in the preceding environment
  --with PKG      Install PKG in the preceding environment (can be repeated)
  --sink          Kitchen sink: 7 envs (venv/virtualenv/conda x marimo/no-marimo + venv-numpy)
  --help          Show this help message

${BOLD}Examples:${NC}
  $0                                    # Create 1 conda environment (default)
  $0 --venv 2 --conda                   # Create 2 venv and 1 conda (all with marimo)
  $0 --venv --no-marimo                 # Create 1 venv without marimo
  $0 --venv 2 --venv --no-marimo --conda --conda --no-marimo
                                        # Create 5 envs: 2 venv (marimo), 1 venv (no marimo),
                                        #                1 conda (marimo), 1 conda (no marimo)

${BOLD}Naming:${NC}
  • Basic: venv-1, conda-2, virtualenv-3
  • With packages: venv-numpy-4, conda-numpy-matplotlib-5
  • Without marimo: venv-no-marimo-6, conda-numpy-no-marimo-7

${BOLD}Behavior:${NC}
  • If no arguments: Creates 1 conda environment with marimo
  • If arguments provided: Only creates what's specified (no defaults)
  • --no-marimo applies to the immediately preceding --venv/--virtualenv/--conda

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
  # If no arguments provided, default to 1 conda with marimo
  if [[ $# -eq 0 ]]; then
    CONDA_SPECS+=("marimo|")
    LAST_TYPE="conda"
    return
  fi

  while [[ $# -gt 0 ]]; do
    case $1 in
      --venv)
        # Check if next arg is a number
        if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
          for ((i=0; i<$2; i++)); do VENV_SPECS+=("marimo|"); done
          shift 2
        else
          VENV_SPECS+=("marimo|")
          shift
        fi
        LAST_TYPE="venv"
        ;;
      --virtualenv)
        if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
          for ((i=0; i<$2; i++)); do VIRTUALENV_SPECS+=("marimo|"); done
          shift 2
        else
          VIRTUALENV_SPECS+=("marimo|")
          shift
        fi
        LAST_TYPE="virtualenv"
        ;;
      --conda)
        if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
          for ((i=0; i<$2; i++)); do CONDA_SPECS+=("marimo|"); done
          shift 2
        else
          CONDA_SPECS+=("marimo|")
          shift
        fi
        LAST_TYPE="conda"
        ;;
      --no-marimo)
        # Modify the last entry in the most recently modified array
        case "$LAST_TYPE" in
          venv)
            if [[ ${#VENV_SPECS[@]} -gt 0 ]]; then
              local current="${VENV_SPECS[-1]}"
              VENV_SPECS[-1]="no-marimo|${current#*|}"
            fi
            ;;
          virtualenv)
            if [[ ${#VIRTUALENV_SPECS[@]} -gt 0 ]]; then
              local current="${VIRTUALENV_SPECS[-1]}"
              VIRTUALENV_SPECS[-1]="no-marimo|${current#*|}"
            fi
            ;;
          conda)
            if [[ ${#CONDA_SPECS[@]} -gt 0 ]]; then
              local current="${CONDA_SPECS[-1]}"
              CONDA_SPECS[-1]="no-marimo|${current#*|}"
            fi
            ;;
          *)
            print_error "--no-marimo must follow --venv, --virtualenv, or --conda"
            exit 1
            ;;
        esac
        shift
        ;;
      --with)
        # Add package(s) to the last entry in the most recently modified array
        if [[ -z "${2:-}" || "${2:-}" == --* ]]; then
          print_error "--with requires a package name"
          exit 1
        fi
        case "$LAST_TYPE" in
          venv)
            if [[ ${#VENV_SPECS[@]} -gt 0 ]]; then
              local current="${VENV_SPECS[-1]}"
              local flag="${current%%|*}"
              local pkgs="${current#*|}"
              if [[ -n "$pkgs" ]]; then
                VENV_SPECS[-1]="$flag|$pkgs,$2"
              else
                VENV_SPECS[-1]="$flag|$2"
              fi
            fi
            ;;
          virtualenv)
            if [[ ${#VIRTUALENV_SPECS[@]} -gt 0 ]]; then
              local current="${VIRTUALENV_SPECS[-1]}"
              local flag="${current%%|*}"
              local pkgs="${current#*|}"
              if [[ -n "$pkgs" ]]; then
                VIRTUALENV_SPECS[-1]="$flag|$pkgs,$2"
              else
                VIRTUALENV_SPECS[-1]="$flag|$2"
              fi
            fi
            ;;
          conda)
            if [[ ${#CONDA_SPECS[@]} -gt 0 ]]; then
              local current="${CONDA_SPECS[-1]}"
              local flag="${current%%|*}"
              local pkgs="${current#*|}"
              if [[ -n "$pkgs" ]]; then
                CONDA_SPECS[-1]="$flag|$pkgs,$2"
              else
                CONDA_SPECS[-1]="$flag|$2"
              fi
            fi
            ;;
          *)
            print_error "--with must follow --venv, --virtualenv, or --conda"
            exit 1
            ;;
        esac
        shift 2
        ;;
      --sink)
        # Kitchen sink: comprehensive test suite
        # Creates 7 envs: venv, venv-no-marimo, venv-numpy, virtualenv, virtualenv-no-marimo, conda, conda-no-marimo
        shift
        set -- --venv --venv --no-marimo --venv --with numpy --virtualenv --virtualenv --no-marimo --conda --conda --no-marimo "$@"
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

  # Remove conda environments (handles both prefix-based and named environments)
  if [[ ${#CONDA_ENVS[@]} -gt 0 ]]; then
    echo "Removing conda environments: ${CONDA_ENVS[*]}"
    for env in "${CONDA_ENVS[@]}"; do
      if [[ "$env" == /* ]]; then
        # Prefix-based environment (from micromamba) - already in TEST_ENV_DIR, will be cleaned by rm -rf
        echo "  Prefix env $env will be removed with $TEST_ENV_DIR"
      else
        # Named environment (from mamba/conda)
        if command -v mamba &> /dev/null; then
          mamba env remove -n "$env" -y 2>/dev/null || true
        elif command -v conda &> /dev/null; then
          conda env remove -n "$env" -y 2>/dev/null || true
        fi
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
  local spec=$2  # "marimo|pkg1,pkg2" or "no-marimo|pkg1,pkg2"

  # Parse spec
  local install_marimo="${spec%%|*}"
  local extra_pkgs="${spec#*|}"

  # Build name: venv-[pkg1-pkg2-][no-marimo-]N
  local name="venv"
  local display_name="venv"
  if [[ -n "$extra_pkgs" ]]; then
    local pkg_slug="${extra_pkgs//,/-}"
    name="$name-$pkg_slug"
    display_name="$display_name ($extra_pkgs)"
  fi
  if [[ "$install_marimo" == "no-marimo" ]]; then
    name="$name-no-marimo"
    display_name="$display_name (no marimo)"
  fi
  name="$name-$num"
  display_name="$display_name #$num"
  local dir="$TEST_ENV_DIR/$name"

  echo "Creating venv: $name"
  uv venv --seed "$dir"

  # Install ipykernel
  uv pip install --python "$dir/bin/python" -q ipykernel

  # Install marimo[sandbox] unless --no-marimo
  if [[ "$install_marimo" == "marimo" ]]; then
    uv pip install --python "$dir/bin/python" -q "marimo[sandbox]"
  fi

  # Install extra packages if specified
  if [[ -n "$extra_pkgs" ]]; then
    IFS=',' read -ra PKGS <<< "$extra_pkgs"
    for pkg in "${PKGS[@]}"; do
      uv pip install --python "$dir/bin/python" -q "$pkg"
    done
  fi

  # Register kernel with error handling
  local kernel_output
  if ! kernel_output=$("$dir/bin/python" -m ipykernel install --user --name "$name" --display-name "$display_name" 2>&1); then
    print_error "Failed to register kernel for $name"
    echo "$kernel_output"
    return 1
  fi

  KERNEL_NAMES+=("$name")
  print_success "Created venv: $name"
}

# Create virtualenv environment using uvx
create_virtualenv() {
  local num=$1
  local spec=$2  # "marimo|pkg1,pkg2" or "no-marimo|pkg1,pkg2"

  # Parse spec
  local install_marimo="${spec%%|*}"
  local extra_pkgs="${spec#*|}"

  # Build name: virtualenv-[pkg1-pkg2-][no-marimo-]N
  local name="virtualenv"
  local display_name="virtualenv"
  if [[ -n "$extra_pkgs" ]]; then
    local pkg_slug="${extra_pkgs//,/-}"
    name="$name-$pkg_slug"
    display_name="$display_name ($extra_pkgs)"
  fi
  if [[ "$install_marimo" == "no-marimo" ]]; then
    name="$name-no-marimo"
    display_name="$display_name (no marimo)"
  fi
  name="$name-$num"
  display_name="$display_name #$num"
  local dir="$TEST_ENV_DIR/$name"

  echo "Creating virtualenv: $name"
  uvx virtualenv -q "$dir"

  # Install ipykernel
  uv pip install --python "$dir/bin/python" -q ipykernel

  # Install marimo[sandbox] unless --no-marimo
  if [[ "$install_marimo" == "marimo" ]]; then
    uv pip install --python "$dir/bin/python" -q "marimo[sandbox]"
  fi

  # Install extra packages if specified
  if [[ -n "$extra_pkgs" ]]; then
    IFS=',' read -ra PKGS <<< "$extra_pkgs"
    for pkg in "${PKGS[@]}"; do
      uv pip install --python "$dir/bin/python" -q "$pkg"
    done
  fi

  # Register kernel with error handling
  local kernel_output
  if ! kernel_output=$("$dir/bin/python" -m ipykernel install --user --name "$name" --display-name "$display_name" 2>&1); then
    print_error "Failed to register kernel for $name"
    echo "$kernel_output"
    return 1
  fi

  KERNEL_NAMES+=("$name")
  print_success "Created virtualenv: $name"
}

# Create conda environment using uvx micromamba
create_conda_env() {
  local num=$1
  local spec=$2  # "marimo|pkg1,pkg2" or "no-marimo|pkg1,pkg2"

  # Parse spec
  local install_marimo="${spec%%|*}"
  local extra_pkgs="${spec#*|}"

  # Build name: conda-[pkg1-pkg2-][no-marimo-]N
  local name="conda"
  local display_name="conda"
  if [[ -n "$extra_pkgs" ]]; then
    local pkg_slug="${extra_pkgs//,/-}"
    name="$name-$pkg_slug"
    display_name="$display_name ($extra_pkgs)"
  fi
  if [[ "$install_marimo" == "no-marimo" ]]; then
    name="$name-no-marimo"
    display_name="$display_name (no marimo)"
  fi
  name="$name-$num"
  display_name="$display_name #$num"
  local env_prefix="$CONDA_ENVS_DIR/$name"

  echo "Creating conda environment: $name"

  # Helper function to install extra packages
  install_extra_pkgs() {
    local python_path=$1
    if [[ -n "$extra_pkgs" ]]; then
      IFS=',' read -ra PKGS <<< "$extra_pkgs"
      for pkg in "${PKGS[@]}"; do
        uv pip install --python "$python_path" -q "$pkg"
      done
    fi
  }

  # Use uvx micromamba (preferred - works everywhere including Nix)
  if command -v uvx &> /dev/null; then
    echo "Trying uvx micromamba..."
    if micromamba create -y -q -p "$env_prefix" -c conda-forge python=3.10 2>&1; then
      local conda_python="$env_prefix/bin/python"
      if [ -f "$conda_python" ]; then
        # Install ipykernel via micromamba
        if ! micromamba install -y -q -p "$env_prefix" -c conda-forge ipykernel 2>&1; then
          print_error "Failed to install ipykernel for $name"
          return 1
        fi

        # Install marimo[sandbox] unless --no-marimo (use uv pip for consistency)
        if [[ "$install_marimo" == "marimo" ]]; then
          uv pip install --python "$conda_python" -q "marimo[sandbox]"
        fi

        # Install extra packages
        install_extra_pkgs "$conda_python"

        # Register kernel
        local kernel_output
        if ! kernel_output=$("$conda_python" -m ipykernel install --user --name "$name" --display-name "$display_name" 2>&1); then
          print_error "Failed to register kernel for $name"
          echo "$kernel_output"
          return 1
        fi

        CONDA_ENVS+=("$env_prefix")
        KERNEL_NAMES+=("$name")
        print_success "Created conda environment: $name (via micromamba)"
        return 0
      fi
    fi
  fi
  print_error "Failed to create conda environment: $name (no working micromamba found)"
  return 1
}

# Main execution
main() {
  parse_args "$@"

  local total_envs=$((${#VENV_SPECS[@]} + ${#VIRTUALENV_SPECS[@]} + ${#CONDA_SPECS[@]}))

  # Banner
  echo -e "\n${BOLD}${GREEN}"
  echo "╔═══════════════════════════════════════════════════╗"
  echo "║  Test Environment Setup for Kernel Selection      ║"
  echo "╚═══════════════════════════════════════════════════╝"
  echo -e "${NC}"

  print_header "Environment Configuration"
  echo "Creating environments:"
  echo "  • venv:       ${#VENV_SPECS[@]}"
  echo "  • virtualenv: ${#VIRTUALENV_SPECS[@]}"
  echo "  • conda:      ${#CONDA_SPECS[@]}"
  echo ""

  # Create test environment directory if needed
  if [[ ${#VENV_SPECS[@]} -gt 0 || ${#VIRTUALENV_SPECS[@]} -gt 0 ]]; then
    mkdir -p "$TEST_ENV_DIR"
  fi

  # Create conda directories if needed
  if [[ ${#CONDA_SPECS[@]} -gt 0 ]]; then
    mkdir -p "$CONDA_ENVS_DIR"
    mkdir -p "$CONDA_PKGS_DIR"
  fi

  # Global counter for unique naming across all env types
  local env_num=1

  # Create venv environments
  if [[ ${#VENV_SPECS[@]} -gt 0 ]]; then
    print_header "Creating venv environments"
    for spec in "${VENV_SPECS[@]}"; do
      create_venv "$env_num" "$spec"
      ((env_num++))
    done
  fi

  # Create virtualenv environments
  if [[ ${#VIRTUALENV_SPECS[@]} -gt 0 ]]; then
    print_header "Creating virtualenv environments"
    for spec in "${VIRTUALENV_SPECS[@]}"; do
      create_virtualenv "$env_num" "$spec"
      ((env_num++))
    done
  fi

  # Create conda environments
  if [[ ${#CONDA_SPECS[@]} -gt 0 ]]; then
    print_header "Creating conda environments"
    for spec in "${CONDA_SPECS[@]}"; do
      create_conda_env "$env_num" "$spec"
      ((env_num++))
    done
  fi

  # Summary
  echo ""
  print_header "Summary"
  echo "Total environments created: $total_envs"
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
