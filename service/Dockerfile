FROM python:3.12-slim

# The base image ships an old pip; torch pulls in setuptools. Keep both current.
RUN pip install --no-cache-dir --upgrade pip==26.3 setuptools==84.2.1

# CPU-only PyTorch keeps the image small; the models are fast enough on CPU.
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY core.py depth.py layers.py server.py ./

# Model weights are downloaded on first use into /cache; mount a volume there.
ENV HF_HOME=/cache
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status', timeout=4)"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
