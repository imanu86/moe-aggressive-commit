# POD A — chripell reference — PRE-STAGED (2026-07-13)

- pod_id: 8fvoe4nb5nojd2  name=podA-chripell-ref
- gpu: NVIDIA GeForce RTX 3090 24GB, secure cloud (datacenter eu-cz-1), driver 580.126.20, CUDA 12.8
- ram: 125 GiB guaranteed (host ~959 GiB free at check) — satisfies >=90 GiB whole-pin req
- volume: 150 GiB persistent at /workspace (MooseFS network FS, ~55 MB/s cold read)
- image: runpod/pytorch:1.0.7-cu1281-torch280-ubuntu2404
- CUDA-gate: PASS (torch cuda avail + micro-alloc OK; cuInit healthy, no 999 bug)
- model: /workspace/models/ds4-2bit.gguf size=86720111488 OK, sha256=efc7ed60...616668 OK
- binary: /workspace/bin/ds4-server (base da0b3f6 + 0050 masked-stream, sm_86); source /workspace/ds4-v2-work
- repo: /workspace/reap-loop @ spex-predictive-mask-study-2026-07-12 (apply 0051 here)
- smoke: 1-token PASS (content="Hi", finish=length) — /workspace/logs/smoke/resp.json
- final_state: STOPPED (EXITED), disk retained, dead-man reaper cancelled

## Re-enable
    runpodctl pod start 8fvoe4nb5nojd2
    # then fetch new SSH endpoint (IP+port change on restart):
    curl -s -H "Authorization: Bearer $KEY" https://rest.runpod.io/v1/pods/8fvoe4nb5nojd2 \
      | python -c "import sys,json;d=json.load(sys.stdin);print(d['publicIp'],d['portMappings']['22'])"
    ssh -p <port> root@<ip>

## Rebuild after 0051
    cd /workspace/ds4-v2-work && PATH=/usr/local/cuda/bin:$PATH make -B ds4-server CUDA_ARCH=sm_86

Caveats: /root is wiped on stop (rclone R2 cfg + cf.txt gone by design — model already persisted).
Whole-pin load of 80GB from the network volume is slow on first page-in.
