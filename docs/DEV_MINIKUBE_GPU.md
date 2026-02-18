# DEV: Minikube GPU (WSL2 + Docker, profile `mk-gpu`)

Этот гайд фиксирует проверенный локальный сетап GPU для разработки:
- WSL2
- Docker
- Minikube profile: `mk-gpu`
- driver: `docker`
- container runtime: `docker`
- `--gpus=all`
- Kubernetes: `v1.29.2`
- addon: `nvidia-device-plugin`

## 1) Prerequisites

- Docker в WSL2 работает и видит GPU.
- `minikube`, `kubectl` и `./bin/kubectl-mk-gpu` доступны из репозитория.
- NVIDIA Container Toolkit уже настроен для Docker в WSL2.

Быстрая проверка GPU в Docker:

```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi -L
```

Ожидается список GPU (например `GPU 0: ...`).

## 2) Recreate minikube profile

Пересоздай профиль `mk-gpu` полностью:

```bash
minikube delete -p mk-gpu || true
minikube start -p mk-gpu --driver=docker --container-runtime=docker --gpus=all --kubernetes-version=v1.29.2
```

Включи и проверь addon `nvidia-device-plugin`:

```bash
minikube addons enable nvidia-device-plugin -p mk-gpu
minikube addons list -p mk-gpu | rg nvidia-device-plugin
```

## 3) Check cluster via wrapper

Используй wrapper, чтобы не ошибиться с контекстом:

```bash
./bin/kubectl-mk-gpu get nodes -o wide
```

Важно: `kubectl -A get ...` невалидно; правильно `kubectl get -A ...`.

Проверь GPU `capacity` и `allocatable` (jsonpath с корректными escape):

```bash
./bin/kubectl-mk-gpu get node mk-gpu -o jsonpath='{.status.capacity.nvidia\.com/gpu}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}'
./bin/kubectl-mk-gpu get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
```

Если значения пустые, подожди 20-60 секунд и повтори.

## 4) GPU smoke pod (CUDA 11.8)

Создай smoke pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-smoke
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: cuda
      image: nvidia/cuda:11.8.0-base-ubuntu22.04
      command: ["bash","-lc","nvidia-smi -L && nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
```

Применение, ожидание и логи:

```bash
cat > /tmp/gpu-smoke.yaml <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: gpu-smoke
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: cuda
      image: nvidia/cuda:11.8.0-base-ubuntu22.04
      command: ["bash","-lc","nvidia-smi -L && nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
YAML

./bin/kubectl-mk-gpu apply -f /tmp/gpu-smoke.yaml
./bin/kubectl-mk-gpu wait pod/gpu-smoke --for=jsonpath='{.status.phase}'=Succeeded --timeout=300s
./bin/kubectl-mk-gpu logs pod/gpu-smoke
```

Ожидается успешный вывод `nvidia-smi` внутри pod.

## 5) Troubleshooting (describe/events)

Если pod не стартует или застрял в `Pending`, смотри:

```bash
./bin/kubectl-mk-gpu describe pod gpu-smoke
./bin/kubectl-mk-gpu get events --sort-by=.lastTimestamp | tail -n 40
./bin/kubectl-mk-gpu -n kube-system get pods -o wide
./bin/kubectl-mk-gpu -n kube-system logs -l name=nvidia-device-plugin-ds --tail=200
```

Типовые причины:
- Addon `nvidia-device-plugin` не включён или ещё не Ready.
- Docker в WSL2 не видит GPU (`docker ... nvidia-smi -L` не проходит).
- Нода не экспортирует `nvidia.com/gpu` в `allocatable`.

После проверки можно удалить smoke pod:

```bash
./bin/kubectl-mk-gpu delete pod gpu-smoke --ignore-not-found
```

## 6) Mock trainer Deployment for ModeKeeper drift demo

Apply canonical mock trainer manifest:

```bash
./bin/kubectl-mk-gpu apply -f demo/k8s/trainer.yaml
```

Wait for rollout:

```bash
./bin/kubectl-mk-gpu -n default rollout status deploy/trainer --timeout=180s
```

Show template annotations:

```bash
./bin/kubectl-mk-gpu -n default get deploy trainer -o jsonpath='{.spec.template.metadata.annotations}{"\n"}'
```

Set drift (4/16) and run closed-loop:

```bash
./bin/kubectl-mk-gpu -n default patch deployment/trainer --type merge -p '{"spec":{"template":{"metadata":{"annotations":{"modekeeper/knob.grad_accum_steps":"4","modekeeper/knob.microbatch_size":"16"}}}}}'
KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk closed-loop run --scenario drift --out report/_cl_k8s_drift
```

Set no-drift (8/32) and run closed-loop:

```bash
./bin/kubectl-mk-gpu -n default patch deployment/trainer --type merge -p '{"spec":{"template":{"metadata":{"annotations":{"modekeeper/knob.grad_accum_steps":"8","modekeeper/knob.microbatch_size":"32"}}}}}'
KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk closed-loop run --scenario drift --out report/_cl_k8s_nodrift
```

Cleanup (optional):

```bash
./bin/kubectl-mk-gpu -n default delete deploy trainer --ignore-not-found
```

## 7) Paid apply (dev license)

По умолчанию (без override) dev-лицензия **не** проходит проверку — это ожидаемо.
Для локального демо используем явный override списка публичных ключей.

Mint dev license (создаст `./license_dev.json` и `./license_dev_public_keys.json`):

```bash
./bin/mk-mint-dev-license
```

Verify (с override публичных ключей):

```bash
MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH=./license_dev_public_keys.json KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk license verify --license ./license_dev.json --out report/_license_dev_verify
```

Apply (closed-loop, paid apply):

```bash
MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH=./license_dev_public_keys.json MODEKEEPER_LICENSE_PATH=./license_dev.json KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk closed-loop run --scenario drift --apply --out report/_cl_k8s_apply_paid
```

Rotation note:
- `license_dev_public_keys.json` uses keyring format `{ "kid": "pubkey_b64_raw32", ... }`.
- unknown `kid` is always `license_invalid`.
