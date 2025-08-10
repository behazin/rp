# FILE: ./services/fetcher-service/Dockerfile

FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /usr/src/app/app

CMD ["python", "app/main.py"]