FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src/ src/
COPY serve.py main.py ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "serve.py"]
