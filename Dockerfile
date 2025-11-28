FROM python:3.11-slim

WORKDIR /app

# Instala dependências primeiro (melhor cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code, preserving directories
COPY common/ common/
COPY inputs/ inputs/
COPY outputs/ outputs/
COPY scripts/ scripts/
COPY service/ service/
COPY configs/ configs/

# Entrada padrão - vamos sobrescrever no docker run / k8s
CMD ["bash", "-c", "echo 'Container up. Use command override to run pipelines.'"]
