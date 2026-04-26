#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PROJECT_NAME="A22"
OUT_BASE_DIR="${ROOT_DIR}/dist/submission"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

SKIP_BUILD="false"
SKIP_IMAGES="false"
SKIP_ENGINEERING="false"
SKIP_MODELS="false"
SKIP_RAG_BUILD="false"
REQUIRE_RAG="false"

MODEL_ROOT="${A22_MODEL_ROOT:-/root/autodl-tmp/a22/models}"

RAG_BUILD_STATUS="not_run"
RAG_VERIFY_STATUS="not_run"
MODEL_ARCHIVE_STATUS="not_run"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/release/package_competition_submission.sh [options]

Options:
  --project-name NAME      Package name prefix (default: A22)
  --out-dir DIR            Output base directory (default: ./dist/submission)
  --model-root DIR         Model directory to archive (default: $A22_MODEL_ROOT or /root/autodl-tmp/a22/models)
  --skip-build             Skip docker compose build and export existing local images
  --skip-images            Skip docker image tar export
  --skip-engineering       Skip engineering project archives
  --skip-models            Skip model parameters tar archive
  --skip-rag-build         Skip RAG chunk/index pre-build
  --require-rag            Fail when RAG code/index is not present in orchestrator image
  -h, --help               Show this help

Examples:
  ./scripts/release/package_competition_submission.sh
  ./scripts/release/package_competition_submission.sh --project-name A22_Final --out-dir /root/autodl-tmp/a22/submission
  ./scripts/release/package_competition_submission.sh --model-root /root/autodl-tmp/a22/models --require-rag
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --out-dir)
      OUT_BASE_DIR="$2"
      shift 2
      ;;
    --model-root)
      MODEL_ROOT="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD="true"
      shift
      ;;
    --skip-images)
      SKIP_IMAGES="true"
      shift
      ;;
    --skip-engineering)
      SKIP_ENGINEERING="true"
      shift
      ;;
    --skip-models)
      SKIP_MODELS="true"
      shift
      ;;
    --skip-rag-build)
      SKIP_RAG_BUILD="true"
      shift
      ;;
    --require-rag)
      REQUIRE_RAG="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[error] required command not found: $cmd" >&2
    exit 1
  fi
}

first_available_cmd() {
  local cmd
  for cmd in "$@"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  return 1
}

ensure_repo_layout() {
  local required=(
    "${ROOT_DIR}/compose.yaml"
    "${ROOT_DIR}/compose.remote.models.yaml"
    "${ROOT_DIR}/remote/avatar-service"
    "${ROOT_DIR}/remote/speech-service"
    "${ROOT_DIR}/remote/orchestrator"
    "${ROOT_DIR}/scripts/remote/start_remote_stack_tmux.sh"
  )
  local path
  for path in "${required[@]}"; do
    if [[ ! -e "$path" ]]; then
      echo "[error] required path missing: $path" >&2
      exit 1
    fi
  done
}

write_sha256() {
  local file_path="$1"
  local out_file="$2"
  sha256sum "$file_path" | awk '{print $1}' >"$out_file"
}

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    cp -a "$src" "$dst"
    return 0
  fi
  echo "[warn] optional path not found, skipped: $src"
  return 1
}

build_rag_if_available() {
  if [[ "${SKIP_RAG_BUILD}" == "true" ]]; then
    echo "[info] skip rag build enabled."
    RAG_BUILD_STATUS="skipped_by_flag"
    return 0
  fi

  local rag_chunks="${ROOT_DIR}/remote/orchestrator/scripts/build_rag_chunks.py"
  local rag_index="${ROOT_DIR}/remote/orchestrator/scripts/build_rag_index.py"
  local python_cmd

  if [[ ! -f "$rag_chunks" || ! -f "$rag_index" ]]; then
    echo "[warn] rag scripts not found, skipped rag pre-build."
    RAG_BUILD_STATUS="scripts_not_found"
    if [[ "${REQUIRE_RAG}" == "true" ]]; then
      echo "[error] --require-rag is set, but rag build scripts are missing." >&2
      exit 1
    fi
    return 0
  fi

  if ! python_cmd="$(first_available_cmd python3 python)"; then
    echo "[error] python3/python not found for rag build." >&2
    exit 1
  fi

  echo "[info] building rag chunks/index using ${python_cmd} ..."
  (
    cd "${ROOT_DIR}/remote/orchestrator"
    PYTHONDONTWRITEBYTECODE=1 "${python_cmd}" scripts/build_rag_chunks.py
    PYTHONDONTWRITEBYTECODE=1 "${python_cmd}" scripts/build_rag_index.py
  )
  RAG_BUILD_STATUS="ok"
}

verify_rag_in_orchestrator_image() {
  local orchestrator_image="a22/orchestrator:latest"
  local has_rag_source="false"

  if [[ -d "${ROOT_DIR}/remote/orchestrator/services/rag" || -d "${ROOT_DIR}/remote/orchestrator/knowledge_base" ]]; then
    has_rag_source="true"
  fi

  if [[ "${has_rag_source}" != "true" && "${REQUIRE_RAG}" != "true" ]]; then
    RAG_VERIFY_STATUS="skipped_no_rag_source"
    echo "[info] rag source not found in working tree; skip image rag verification."
    return 0
  fi

  local check_output
  set +e
  check_output="$(
    docker run --rm "${orchestrator_image}" \
      python -c "from pathlib import Path; print('rag_code', Path('/app/services/rag').exists()); print('rag_index', Path('/app/knowledge_base/indexes/chunks.jsonl').exists())" \
      2>&1
  )"
  local rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    echo "[warn] rag image verification command failed:"
    echo "${check_output}"
    RAG_VERIFY_STATUS="verify_command_failed"
    if [[ "${REQUIRE_RAG}" == "true" ]]; then
      echo "[error] --require-rag is set and rag image verification failed." >&2
      exit 1
    fi
    return 0
  fi

  echo "${check_output}" > "${META_DIR}/rag_image_check.txt"
  if grep -q "rag_code True" <<<"${check_output}" && grep -q "rag_index True" <<<"${check_output}"; then
    echo "[info] rag verification passed in orchestrator image."
    RAG_VERIFY_STATUS="ok"
    return 0
  fi

  echo "[warn] rag verification output:"
  echo "${check_output}"
  RAG_VERIFY_STATUS="missing_in_image"
  if [[ "${REQUIRE_RAG}" == "true" ]]; then
    echo "[error] --require-rag is set, but rag code/index not found in orchestrator image." >&2
    exit 1
  fi
}

write_runtime_readme() {
  local readme_path="$1"
  cat > "${readme_path}" <<EOF
Runtime package for ${PROJECT_NAME}

Files:
- compose.yaml
- compose.remote.models.yaml
- .env.remote.models.example (if present)

Quick start:
1) Load docker images tar
   docker load -i ../01_docker_images/${PROJECT_NAME}_remote_stack_images.tar

2) Prepare env
   cp .env.remote.models.example .env.remote.models
   # edit .env.remote.models and set A22_MODEL_ROOT to your model directory

3) Start services
   docker compose --env-file .env.remote.models -f compose.yaml -f compose.remote.models.yaml up -d

4) Health checks
   curl -s http://127.0.0.1:19000/health | python -m json.tool
   curl -s http://127.0.0.1:19300/health | python -m json.tool

Model parameters archive:
- If 04_model_parameters/${PROJECT_NAME}_model_parameters.tar is included,
  extract it to your host model root and point A22_MODEL_ROOT to that path.
EOF
}

PACKAGE_ROOT="${OUT_BASE_DIR}/${PROJECT_NAME}_competition_submission_${TIMESTAMP}"
IMAGES_DIR="${PACKAGE_ROOT}/01_docker_images"
RUNTIME_DIR="${PACKAGE_ROOT}/02_runtime"
ENGINEERING_DIR="${PACKAGE_ROOT}/03_engineering_projects"
MODELS_DIR="${PACKAGE_ROOT}/04_model_parameters"
META_DIR="${PACKAGE_ROOT}/99_manifest"
TMP_STAGE_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_STAGE_DIR}"
}
trap cleanup EXIT

require_cmd tar
require_cmd sha256sum
ensure_repo_layout

mkdir -p "${PACKAGE_ROOT}" "${META_DIR}" "${RUNTIME_DIR}"
if [[ "${SKIP_IMAGES}" != "true" ]]; then
  mkdir -p "${IMAGES_DIR}"
fi
if [[ "${SKIP_ENGINEERING}" != "true" ]]; then
  mkdir -p "${ENGINEERING_DIR}"
fi
if [[ "${SKIP_MODELS}" != "true" ]]; then
  mkdir -p "${MODELS_DIR}"
fi

cd "${ROOT_DIR}"

echo "[info] packaging runtime files..."
cp -a "${ROOT_DIR}/compose.yaml" "${RUNTIME_DIR}/"
cp -a "${ROOT_DIR}/compose.remote.models.yaml" "${RUNTIME_DIR}/"
copy_if_exists "${ROOT_DIR}/.env.remote.models.example" "${RUNTIME_DIR}/" || true
write_runtime_readme "${RUNTIME_DIR}/README_RUN_DOCKER.md"

if [[ "${SKIP_IMAGES}" != "true" ]]; then
  require_cmd docker

  SERVICES=(
    "qwen-server"
    "speech-service"
    "vision-service"
    "avatar-service"
    "orchestrator"
  )
  IMAGES=(
    "a22/qwen-server:latest"
    "a22/speech-service:latest"
    "a22/vision-service:latest"
    "a22/avatar-service:latest"
    "a22/orchestrator:latest"
  )

  if [[ "${SKIP_BUILD}" != "true" ]]; then
    build_rag_if_available
    echo "[info] building remote model stack images..."
    docker compose -f compose.yaml -f compose.remote.models.yaml build "${SERVICES[@]}"
  else
    echo "[info] skip build enabled, exporting existing local images..."
    RAG_BUILD_STATUS="skipped_by_skip_build"
  fi

  local_image=""
  for local_image in "${IMAGES[@]}"; do
    if ! docker image inspect "$local_image" >/dev/null 2>&1; then
      echo "[error] image not found locally: $local_image" >&2
      echo "[hint] run without --skip-build, or build the image first." >&2
      exit 1
    fi
  done

  verify_rag_in_orchestrator_image

  IMAGE_TAR="${IMAGES_DIR}/${PROJECT_NAME}_remote_stack_images.tar"
  echo "[info] exporting images to ${IMAGE_TAR} ..."
  docker save "${IMAGES[@]}" -o "${IMAGE_TAR}"
  write_sha256 "${IMAGE_TAR}" "${IMAGE_TAR}.sha256"

  {
    echo "docker_images:"
    printf '  - %s\n' "${IMAGES[@]}"
  } > "${META_DIR}/docker_images_list.txt"
fi

if [[ "${SKIP_ENGINEERING}" != "true" ]]; then
  echo "[info] packaging engineering projects..."

  AVATAR_STAGE="${TMP_STAGE_DIR}/avatar_engineering"
  SPEECH_STAGE="${TMP_STAGE_DIR}/speech_engineering"
  mkdir -p "${AVATAR_STAGE}" "${SPEECH_STAGE}"

  mkdir -p "${AVATAR_STAGE}/remote" "${AVATAR_STAGE}/scripts" "${AVATAR_STAGE}/shared"
  mkdir -p "${AVATAR_STAGE}/remote/orchestrator/services" "${AVATAR_STAGE}/remote/orchestrator"
  cp -a "${ROOT_DIR}/remote/avatar-service" "${AVATAR_STAGE}/remote/avatar-service"
  copy_if_exists "${ROOT_DIR}/remote/orchestrator/services/rag" "${AVATAR_STAGE}/remote/orchestrator/services/" || true
  copy_if_exists "${ROOT_DIR}/remote/orchestrator/knowledge_base" "${AVATAR_STAGE}/remote/orchestrator/" || true
  cp -a "${ROOT_DIR}/scripts/remote/"*.sh "${AVATAR_STAGE}/scripts/"
  cp -a "${ROOT_DIR}/shared/contracts" "${AVATAR_STAGE}/shared/contracts"
  cp -a "${ROOT_DIR}/compose.remote.models.yaml" "${AVATAR_STAGE}/"
  copy_if_exists "${ROOT_DIR}/.env.remote.models.example" "${AVATAR_STAGE}/" || true

  cat > "${AVATAR_STAGE}/README_SUBMISSION.txt" <<'EOF'
Package purpose:
- Executable digital human facial behavior driving model project files.

Main entry:
- remote/avatar-service

Recommended startup helper scripts:
- scripts/restart_avatar_service_soulx_full.sh
- scripts/start_remote_stack_tmux.sh

Model paths are externalized by environment variables (not bundled in this engineering archive).
EOF

  mkdir -p "${SPEECH_STAGE}/remote" "${SPEECH_STAGE}/scripts" "${SPEECH_STAGE}/shared"
  cp -a "${ROOT_DIR}/remote/speech-service" "${SPEECH_STAGE}/remote/speech-service"
  cp -a "${ROOT_DIR}/scripts/remote/"*.sh "${SPEECH_STAGE}/scripts/"
  cp -a "${ROOT_DIR}/shared/contracts" "${SPEECH_STAGE}/shared/contracts"
  cp -a "${ROOT_DIR}/compose.remote.models.yaml" "${SPEECH_STAGE}/"
  copy_if_exists "${ROOT_DIR}/.env.remote.models.example" "${SPEECH_STAGE}/" || true

  cat > "${SPEECH_STAGE}/README_SUBMISSION.txt" <<'EOF'
Package purpose:
- Executable speech recognition model project files.

Main entry:
- remote/speech-service

Recommended startup helper scripts:
- scripts/start_remote_stack_tmux.sh

Model paths are externalized by environment variables (not bundled in this engineering archive).
EOF

  AVATAR_TAR="${ENGINEERING_DIR}/${PROJECT_NAME}_avatar_engineering.tar.gz"
  SPEECH_TAR="${ENGINEERING_DIR}/${PROJECT_NAME}_speech_asr_engineering.tar.gz"

  tar -czf "${AVATAR_TAR}" -C "${AVATAR_STAGE}" .
  tar -czf "${SPEECH_TAR}" -C "${SPEECH_STAGE}" .
  write_sha256 "${AVATAR_TAR}" "${AVATAR_TAR}.sha256"
  write_sha256 "${SPEECH_TAR}" "${SPEECH_TAR}.sha256"
fi

if [[ "${SKIP_MODELS}" != "true" ]]; then
  if [[ -d "${MODEL_ROOT}" ]]; then
    MODEL_TAR="${MODELS_DIR}/${PROJECT_NAME}_model_parameters.tar"
    echo "[info] packaging model directory: ${MODEL_ROOT}"
    tar -cf "${MODEL_TAR}" -C "${MODEL_ROOT}" .
    write_sha256 "${MODEL_TAR}" "${MODEL_TAR}.sha256"
    MODEL_ARCHIVE_STATUS="ok"
  else
    echo "[warn] model root not found, skip model archive: ${MODEL_ROOT}"
    MODEL_ARCHIVE_STATUS="model_root_not_found"
  fi
else
  MODEL_ARCHIVE_STATUS="skipped_by_flag"
fi

GIT_COMMIT="unknown"
GIT_BRANCH="unknown"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_COMMIT="$(git rev-parse HEAD || true)"
  GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD || true)"
fi

cat > "${META_DIR}/submission_manifest.txt" <<EOF
project_name=${PROJECT_NAME}
generated_at=$(date -Iseconds)
host=$(hostname)
git_branch=${GIT_BRANCH}
git_commit=${GIT_COMMIT}
package_root=${PACKAGE_ROOT}
skip_build=${SKIP_BUILD}
skip_images=${SKIP_IMAGES}
skip_engineering=${SKIP_ENGINEERING}
skip_models=${SKIP_MODELS}
skip_rag_build=${SKIP_RAG_BUILD}
require_rag=${REQUIRE_RAG}
model_root=${MODEL_ROOT}
rag_build_status=${RAG_BUILD_STATUS}
rag_verify_status=${RAG_VERIFY_STATUS}
model_archive_status=${MODEL_ARCHIVE_STATUS}
EOF

cat > "${PACKAGE_ROOT}/README_SUBMISSION.txt" <<EOF
Competition submission package generated by:
  scripts/release/package_competition_submission.sh

Contents:
  01_docker_images/
    - ${PROJECT_NAME}_remote_stack_images.tar (if not skipped)
  02_runtime/
    - compose.yaml
    - compose.remote.models.yaml
    - .env.remote.models.example (if present)
    - README_RUN_DOCKER.md
  03_engineering_projects/
    - ${PROJECT_NAME}_avatar_engineering.tar.gz (if not skipped)
    - ${PROJECT_NAME}_speech_asr_engineering.tar.gz (if not skipped)
  04_model_parameters/
    - ${PROJECT_NAME}_model_parameters.tar (if model root exists and not skipped)
  99_manifest/
    - submission_manifest.txt
    - docker_images_list.txt (if images exported)
    - rag_image_check.txt (if rag check executed)

Validation:
  sha256sum -c 01_docker_images/*.sha256 2>/dev/null || true
  sha256sum -c 03_engineering_projects/*.sha256 2>/dev/null || true
  sha256sum -c 04_model_parameters/*.sha256 2>/dev/null || true
EOF

echo "[ok] competition submission package is ready:"
echo "  ${PACKAGE_ROOT}"
