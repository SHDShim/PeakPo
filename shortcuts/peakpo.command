#!/usr/bin/env bash
# PeakPo launcher for macOS
# Works with pip installs and Conda installs without editing.

set -u

run_peakpo() {
  if command -v peakpo >/dev/null 2>&1; then
    peakpo
    return $?
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -m peakpo
    return $?
  fi
  if command -v python >/dev/null 2>&1; then
    python -m peakpo
    return $?
  fi
  return 127
}

try_conda_then_run() {
  local conda_sh=""
  if command -v conda >/dev/null 2>&1; then
    local conda_base
    conda_base="$(conda info --base 2>/dev/null || true)"
    if [ -n "${conda_base}" ] && [ -f "${conda_base}/etc/profile.d/conda.sh" ]; then
      conda_sh="${conda_base}/etc/profile.d/conda.sh"
    fi
  fi
  if [ -z "${conda_sh}" ]; then
    for p in \
      "$HOME/miniconda3/etc/profile.d/conda.sh" \
      "$HOME/anaconda3/etc/profile.d/conda.sh" \
      "/opt/miniconda3/etc/profile.d/conda.sh" \
      "/opt/anaconda3/etc/profile.d/conda.sh"; do
      if [ -f "$p" ]; then
        conda_sh="$p"
        break
      fi
    done
  fi
  if [ -z "${conda_sh}" ]; then
    return 127
  fi
  # shellcheck disable=SC1090
  source "${conda_sh}"
  if [ -n "${PEAKPO_CONDA_ENV:-}" ]; then
    conda activate "${PEAKPO_CONDA_ENV}" || return 127
  fi
  run_peakpo
}

run_peakpo
status=$?
if [ $status -eq 0 ]; then
  exit 0
fi

try_conda_then_run
status=$?
if [ $status -eq 0 ]; then
  exit 0
fi

echo "PeakPo launch failed."
echo "Tried: peakpo, python -m peakpo, and conda fallback."
echo "If needed, set PEAKPO_CONDA_ENV to your environment name."
read -r -p "Press Enter to close..."
exit $status
