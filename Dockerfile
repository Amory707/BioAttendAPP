FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 1000 bioattend && \
    mkdir -p /app /app/staticfiles /app/media && \
    chown -R bioattend:bioattend /app

WORKDIR /app

COPY --chown=bioattend:bioattend . .

EXPOSE 80

USER bioattend

CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    gunicorn BioAttend.wsgi:application --bind 0.0.0.0:80 --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - --log-level info
