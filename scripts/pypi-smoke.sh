#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

tmp_dir=""

cleanup() {
  if [[ -n "${tmp_dir}" && -d "${tmp_dir}" ]]; then
    rm -rf "${tmp_dir}"
  fi
}
trap cleanup EXIT

rm -rf dist/ build/
python -m build

tmp_dir="$(mktemp -d)"
venv_dir="${tmp_dir}/venv"
kubeconfig_path="${tmp_dir}/kubeconfig"
kubectl_path="${tmp_dir}/kubectl"

python -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install dist/*.whl

printf 'apiVersion: v1\nkind: Config\n' > "${kubeconfig_path}"

cat > "${kubectl_path}" <<'KUBECTL_EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.29.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "--client" && "$3" == "--short" ]]; then
  echo "Client Version: v1.29.0"
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.28.0"}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == namespace/* && "$3" == "-o" && "$4" == "name" ]]; then
  echo "$2"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$3" == "get" && "$4" == deployment/* && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/${4#deployment/}"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$3" == "auth" && "$4" == "can-i" && ("$5" == "patch" || "$5" == "get") && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

if [[ "$*" == *"--dry-run=server"* && "$*" == *"patch deployment/"* ]]; then
  deployment=""
  for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    if [[ "$arg" == deployment/* ]]; then
      deployment="${arg#deployment/}"
      break
    fi
  done
  if [[ -n "$deployment" ]]; then
    echo "deployment.apps/${deployment}"
  else
    echo "deployment.apps/dep1"
  fi
  exit 0
fi

echo "fake kubectl: unhandled args: $*" >&2
exit 0
KUBECTL_EOF
chmod +x "${kubectl_path}"

export KUBECONFIG="${kubeconfig_path}"
export KUBECTL="${kubectl_path}"

"${venv_dir}/bin/mk" --help
"${venv_dir}/bin/mk" doctor
"${venv_dir}/bin/mk" observe --duration 30s --source synthetic --out report/_observe_quick
"${venv_dir}/bin/mk" closed-loop run --scenario drift --dry-run --out report/_dryrun

set +e
MODEKEEPER_KILL_SWITCH=1 "${venv_dir}/bin/mk" closed-loop run --scenario drift --apply --out report/_apply_blocked
apply_rc=$?
set -e
printf 'apply rc: %s\n' "${apply_rc}"
