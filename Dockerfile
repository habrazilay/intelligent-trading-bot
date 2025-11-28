FROM python:3.11-slim

WORKDIR /app

# Copia projeto
COPY . /app

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Variáveis de ambiente (overridable via Azure)
ENV PYTHONUNBUFFERED=1

# Entry point genérico – vamos sobrescrever o comando no job
CMD ["bash", "-c", "echo 'Container up. Use command override to run pipelines.'"]