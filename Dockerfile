FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/cerodias

EXPOSE 5001

CMD ["python", "run.py"]
