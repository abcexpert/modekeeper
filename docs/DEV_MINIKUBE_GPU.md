# Minikube GPU Local Evaluation (Public)

Public local evaluation guide for running ModeKeeper on a customer-managed local Kubernetes environment with GPU support.

Scope:
- local/dev evaluation only
- verify-first and dry-run oriented flows
- no vendor-operated runtime assumptions

## 1) Prerequisites

- Docker can access your GPU.
- `minikube` and `kubectl` are installed.
- NVIDIA Container Toolkit is configured for Docker.

Quick GPU check in Docker:

```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi -L
```

Expected result: visible GPU entries (for example `GPU 0: ...`).

## 2) Create Minikube profile

```bash
minikube delete -p mk-gpu || true
minikube start -p mk-gpu --driver=docker --container-runtime=docker --gpus=all --kubernetes-version=v1.29.2
```

Enable NVIDIA device plugin:

```bash
minikube addons enable nvidia-device-plugin -p mk-gpu
minikube addons list -p mk-gpu | rg nvidia-device-plugin
```

## 3) Check node GPU capacity

```bash
kubectl --context mk-gpu get nodes -o wide
kubectl --context mk-gpu get node mk-gpu -o jsonpath='{.status.capacity.nvidia\.com/gpu}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}'
kubectl --context mk-gpu get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
```

If values are empty, wait 20-60 seconds and retry.

## 4) GPU smoke pod

Apply a minimal CUDA smoke pod:

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

kubectl --context mk-gpu apply -f /tmp/gpu-smoke.yaml
kubectl --context mk-gpu wait pod/gpu-smoke --for=jsonpath='{.status.phase}'=Succeeded --timeout=300s
kubectl --context mk-gpu logs pod/gpu-smoke
```

Expected result: successful `nvidia-smi` output from inside the pod.

Cleanup:

```bash
kubectl --context mk-gpu delete pod gpu-smoke --ignore-not-found
```

## 5) Optional ModeKeeper dry-run check

Use a dry-run closed-loop run to validate local pipeline behavior without mutating cluster state:

```bash
mk closed-loop run --scenario drift --dry-run --out report/_cl_minikube_gpu
```

## 6) Troubleshooting

If GPU pods remain `Pending`:

```bash
kubectl --context mk-gpu describe pod gpu-smoke
kubectl --context mk-gpu get events --sort-by=.lastTimestamp | tail -n 40
kubectl --context mk-gpu -n kube-system get pods -o wide
kubectl --context mk-gpu -n kube-system logs -l name=nvidia-device-plugin-ds --tail=200
```

Common causes:
- NVIDIA device plugin not ready yet.
- Docker runtime does not expose GPU.
- Node does not report `nvidia.com/gpu` in allocatable resources.
