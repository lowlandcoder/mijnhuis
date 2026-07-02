FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask

# Bouwcontext is de hoofdmap (zie docker-compose.yml).
COPY rooster/app.py /app/app.py

# Draait de bewerkpagina en de API op poort 8090.
CMD ["python", "app.py"]
