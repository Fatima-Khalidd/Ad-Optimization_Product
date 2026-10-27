# Ad Spend Optimization — API image (CSC418 lab build).
#
# Single stage on purpose: the exam asks for one custom image that runs, and a builder/runtime
# split would add a layer to explain without adding anything the stack needs.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies are installed from requirements.txt alone, before the source is copied, so an
# edit to app code does not invalidate this layer and re-resolve pandas on every build.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# STORAGE_ROOT defaults to the relative "./storage" (app/core/settings.py), so the process needs a
# writable directory at an absolute path that docker-compose.yml can mount a named volume onto.
ENV ENV=dev \
    STORAGE_ROOT=/app/storage

EXPOSE 8000

# python:3.12-slim ships neither curl nor wget, so the healthcheck has to use the standard library.
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD ["python", "-c", "import sys,urllib.request as u; r=u.urlopen('http://127.0.0.1:8000/api/health', timeout=4); sys.exit(0 if r.status==200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
