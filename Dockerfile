FROM python:3.14-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html admin.html ./

RUN useradd --create-home appuser
USER appuser

ENV PORT=8000
EXPOSE 8000
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1
