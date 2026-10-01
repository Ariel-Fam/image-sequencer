# Video to Image Sequence

Upload a video in the Streamlit app, extract PNG or JPG frames, and download
them as a ZIP. Uploads and exported ZIP files are each limited to 500 MB.

## Run with Docker Compose

Install and start Docker Desktop (or Docker Engine with the Compose plugin),
then run from this directory:

```sh
docker compose up --build -d --wait
```

Open <http://localhost:8501>. The image is named `image-sequencer:latest`.
Compose builds for the machine's architecture and runs the app as a non-root
user. The image's health check probes Streamlit every 30 seconds.

```sh
docker compose logs -f
docker compose down
```

Run `docker compose up --build -d --wait` again after changing the app.

## Build and run without Compose

```sh
docker build -t image-sequencer:latest .
docker run -d --init --name image-sequencer \
  -p 127.0.0.1:8501:8501 image-sequencer:latest
docker inspect --format '{{.State.Health.Status}}' image-sequencer
docker logs -f image-sequencer
```

To stop and remove this container:

```sh
docker stop image-sequencer
docker rm image-sequencer
```

Use another host port if 8501 is occupied, for example
`-p 127.0.0.1:8502:8501`, then open <http://localhost:8502>.

The container needs no bind mounts. Video uploads and intermediate files use
temporary storage and are removed after processing; ZIP downloads live in the
browser session's server memory. Allow enough Docker memory and disk space for
the videos you process. Restarting the container clears active sessions.

## Verify the image

```sh
docker run --rm -i image-sequencer:latest python < tests/smoke_test.py
```

This generates short MP4 and AVI videos inside the image, checks PNG and JPG
ZIP exports, sampling, resizing, and invalid input, then exercises the Streamlit
extraction flow with supplied upload bytes. The tests stay outside the image.

## Run locally without Docker

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run main.py
```
