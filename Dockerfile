FROM python:3.11-slim

WORKDIR /app

# Instala dependências primeiro (melhor cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia só o código-fonte relevante
COPY common/ inputs/ outputs/ scripts/ service/ configs/ ./

# Entrada padrão - vamos sobrescrever no docker run / k8s
CMD ["bash", "-c", "echo 'Container up. Use command override to run pipelines.'"]
