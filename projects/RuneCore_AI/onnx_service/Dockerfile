FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# Install CPU-only onnxruntime for the container image.
# For actual DirectML/NPU access, use run_native.ps1 on the Windows host.
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" requests pydantic \
    onnxruntime>=1.18.0 \
    "optimum[onnxruntime]>=1.19.0" \
    transformers>=4.40.0 \
    huggingface-hub>=0.22.0 \
    numpy>=1.26

COPY . /app

ENV ONNX_MODEL_DIR=/models
ENV ONNX_DEVICE=cpu
ENV PORT=5006

EXPOSE 5006
VOLUME ["/models"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5006/health || exit 1

CMD ["uvicorn", "onnx_app:app", "--host", "0.0.0.0", "--port", "5006"]
