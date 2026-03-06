import os
import subprocess
import time
import modal
import modal.experimental

import shutil
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_NAME     = "Qwen/Qwen3.5-35B-A3B-FP8"
MODEL_REVISION = "main"
REGION = "us-east"

GPU = "H100:1"

SGLANG_PORT = 30000

# Volumes: one for model weights, one for DeepGEMM JIT kernel cache
model_volume  = modal.Volume.from_name("qwen35-moe-weights",  create_if_missing=True)
kernel_volume = modal.Volume.from_name("qwen35-moe-kernels",  create_if_missing=True)

MODEL_DIR  = "/models"
KERNEL_DIR = "/kernels"

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------
# Start from the official SGLang Docker image (includes CUDA, FlashInfer, etc.)
# and layer on huggingface_hub for fast weight downloads.

# Find the SGLang image's Python (not Modal's injected one)
SGLANG_PYTHON = shutil.which("python3", path="/usr/bin:/usr/local/bin:/opt/conda/bin")
# Fallback search order — adjust if your image puts Python elsewhere
if SGLANG_PYTHON is None or "modal" in SGLANG_PYTHON.lower():
    for candidate in ["/opt/conda/bin/python3", "/usr/bin/python3"]:
        if os.path.exists(candidate):
            SGLANG_PYTHON = candidate
            break

def _wait_for_server(timeout: int = 300):
    """Poll until SGLang's /health endpoint responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{SGLANG_PORT}/health", timeout=5
            )
            print("SGLang server is healthy.")
            return
        except Exception:
            time.sleep(3)
    raise TimeoutError("SGLang server did not start in time.")


def _download_model():
    """Pre-bake model weights into the image at build time."""
    from huggingface_hub import snapshot_download
    snapshot_download(
        MODEL_NAME,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
    )

sglang_image = (
    modal.Image.from_registry(
        "lmsysorg/sglang:latest",
        add_python="3.11",
    )
    .pip_install("huggingface_hub[hf_transfer]")
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "DEEPGEMM_CACHE_DIR": KERNEL_DIR,
        "SGL_ENABLE_JIT_DEEPGEMM": "0",
    })
    .run_function(
        _download_model,
        gpu=GPU,
        volumes={MODEL_DIR: model_volume},
    )
)


# ---------------------------------------------------------------------------
# Modal app
# ---------------------------------------------------------------------------

app = modal.App("inference")


def _wait_for_server(timeout: int = 600):
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{SGLANG_PORT}/health", timeout=5
            )
            print("SGLang server is healthy.")
            return
        except Exception:
            time.sleep(3)
    raise TimeoutError("SGLang server did not start in time.")


@app.cls(
    image=sglang_image,
    gpu=GPU,
    volumes={
        MODEL_DIR:  model_volume,
        KERNEL_DIR: kernel_volume,
    },
    secrets=[modal.Secret.from_name("reach-secrets")],
    # Low-latency routing service (lower overhead than standard web_endpoint)
    # Pin to us-east so GPU containers and the proxy are co-located.
    region=REGION,
    # Keep 0 warm replicas for dev; set to 1+ in production to eliminate cold starts.
    min_containers=0,
    scaledown_window=300,
    startup_timeout=900
)

@modal.experimental.http_server(port=SGLANG_PORT, proxy_regions=[REGION])
@modal.concurrent(target_inputs=1)   # tune based on your latency/throughput target
class SGLangServer:

    @modal.enter()
    def start(self):
        print(subprocess.check_output(["find", "/", "-name", "sglang", "-type", "d"], text=True))
        # --- SGLang launch args for Qwen3.5-35B-A3B-FP8 ---
        #
        # Notable choices vs. the Qwen3-8B example:
        #
        # --quantization fp8
        #   Explicitly tell SGLang the weights are already FP8 (matches the HF repo tags).
        #
        # --context-length 32768
        #   Native context is 262K but KV-cache for 262K across 2× H100s would exhaust
        #   GPU RAM at batch size > 1. 32K is a practical default; raise if needed.
        #
        # No speculative decoding:
        #   Qwen3.5-35B-A3B uses a hybrid Gated DeltaNet + MoE architecture.
        #   There is no published EAGLE-3 draft model for it yet, so we skip
        #   --speculative-algo. Add it later when one becomes available.
        #
        # --chunked-prefill-size 512
        #   Breaks long prefills into chunks so decode latency stays low
        #   while long prompts are being processed.
        #
        # --cuda-graph-max-bs 8
        #   Only capture CUDA graphs for small batch sizes typical in
        #   latency-first serving. Reduces GPU memory overhead.

        cmd = [
            "/usr/bin/python3", "-m", "sglang.launch_server",
            "--model-path",         MODEL_DIR,
            "--host",               "0.0.0.0",
            "--port",               str(SGLANG_PORT),
            "--tp",                 "1",
            "--quantization",       "fp8",
            "--context-length",     "16384",
            "--chunked-prefill-size", "512",
            "--cuda-graph-max-bs",  "8",
            "--api-key", os.environ.get("INFERENCE"),
            "--disable-cuda-graph-padding",  # reduces warmup work
            "--enable-mixed-chunk"         # better for MoE throughput
        ]
        print("Starting SGLang:", " ".join(cmd))
        self._server = subprocess.Popen(cmd)
        _wait_for_server()

    @modal.exit()
    def stop(self):
        self._server.terminate()
        self._server.wait(timeout=30)