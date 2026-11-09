# Build the BPMN editor assets once and bundle them into the application image.
# At runtime, browsers load all BPMN files from the Gertec Academy origin.
FROM node:20-alpine AS bpmn-assets
WORKDIR /build
RUN npm pack bpmn-js@17.11.1 \
    && mkdir -p /bpmn \
    && tar -xzf bpmn-js-17.11.1.tgz -C /bpmn --strip-components=1

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Vendor bpmn-js and its styles locally: no browser request to unpkg.com.
COPY --from=bpmn-assets /bpmn/dist/ /app/static/vendor/bpmn-js/
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
