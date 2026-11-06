FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python - <<'PYCODE'
import pathlib, urllib.request
font_dir = pathlib.Path("/app/static/fonts")
font_dir.mkdir(parents=True, exist_ok=True)
base = "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/"
for source, target in [("GreatVibes-Regular.ttf", "GreatVibes-Regular.ttf"), ("OFL.txt", "GreatVibes-OFL.txt")]:
    urllib.request.urlretrieve(base + source, font_dir / target)
PYCODE
RUN mkdir -p static/uploads
EXPOSE 8000
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
