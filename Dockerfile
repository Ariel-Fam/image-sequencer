FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Cache dependencies separately from application changes. Headless OpenCV
# provides video decoding without a desktop GUI or additional X11 packages.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && python -m pip check

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

COPY main.py softwareLogo.png SpacePointer.PNG ./
COPY .streamlit .streamlit

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3); assert response.read() == b'ok'"

CMD ["python", "-m", "streamlit", "run", "main.py"]
