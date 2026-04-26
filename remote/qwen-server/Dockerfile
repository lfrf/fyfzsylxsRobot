FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface \
    VLLM_CONFIG_ROOT=/cache/vllm \
    VLLM_DISABLE_USAGE_STATS=1

RUN python -m pip install --upgrade pip setuptools wheel

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["python", "-m", "vllm.entrypoints.openai.api_server", "--host", "0.0.0.0", "--port", "8000", "--model", "/models/Qwen2.5-7B-Instruct", "--served-model-name", "Qwen2.5-7B-Instruct", "--dtype", "auto", "--gpu-memory-utilization", "0.50", "--max-model-len", "4096", "--max-num-seqs", "2", "--trust-remote-code"]
