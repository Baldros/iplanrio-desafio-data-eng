FROM python:3.13-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de requisitos e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto
COPY . .

# Expõe o PYTHONPATH para o diretório pipeline
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/pipeline"

# O comando padrão será definido no docker-compose (worker ou deploy)
CMD ["python", "pipeline/flow.py"]
