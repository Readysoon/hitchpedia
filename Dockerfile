FROM python:3.12-slim

WORKDIR /app

# onnxruntime (fastembed) braucht libgomp
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Embedding-Modell zur Build-Zeit vorladen -> kein Download beim ersten Request
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='nomic-ai/nomic-embed-text-v1.5')"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
