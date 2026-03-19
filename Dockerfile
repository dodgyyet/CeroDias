FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/cerodias

RUN groupadd -g 1001 cerodias && useradd -u 1001 -g 1001 -s /bin/bash cerodias
RUN chown -R cerodias:cerodias /app /var/cerodias

USER cerodias

EXPOSE 5001

CMD ["python", "run.py"]
