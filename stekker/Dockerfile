FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir astral paho-mqtt

# Bouwcontext is de hoofdmap (zie docker-compose.yml).
COPY stekker.py /app/stekker.py

# Blijft draaien en bepaalt elke minuut de gewenste stand.
CMD ["python", "stekker.py", "--loop"]
