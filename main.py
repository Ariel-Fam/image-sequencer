"""Video to image sequence — a local Streamlit app.

Install: python -m pip install streamlit opencv-python-headless
Run:     python -m streamlit run video_to_frames.py
Larger uploads: add --server.maxUploadSize 500 to the run command.
"""

import math
import re
import tempfile
import zipfile
from pathlib import Path

import cv2
import streamlit as st


MAX_ZIP_BYTES = 200 * 1024 * 1024


def extract_frames(video_path, zip_path, every_n=1, image_format="PNG",
                   jpeg_quality=90, max_width=0, progress=None):
    """Decode sequentially; save every Nth frame, beginning with frame zero.

    Return the exported count, source FPS, and a small preview image.
    Sampling uses frame numbers, so it also works with variable-rate videos.
    """
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open this video. Try an MP4 encoded with H.264.")
        raw_total = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        total = int(raw_total) if math.isfinite(raw_total) and raw_total > 0 else 0
        fps = capture.get(cv2.CAP_PROP_FPS)
        extension = ".png" if image_format == "PNG" else ".jpg"
        params = ([cv2.IMWRITE_PNG_COMPRESSION, 3] if extension == ".png"
                  else [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        index, saved = 0, 0
        preview = None
        # PNG and JPEG are already compressed; ZIP_STORED avoids wasted CPU.
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % every_n == 0:
                    height, width = frame.shape[:2]
                    if max_width and width > max_width:
                        frame = cv2.resize(
                            frame, (max_width, max(1, round(height * max_width / width))),
                            interpolation=cv2.INTER_AREA,
                        )
                    ok, encoded = cv2.imencode(extension, frame, params)
                    if not ok:
                        raise ValueError(f"Could not encode source frame {index + 1}.")
                    if archive.fp.tell() + encoded.nbytes > MAX_ZIP_BYTES - 2 * 1024 * 1024:
                        raise ValueError(
                            "The ZIP would exceed 200 MB. Choose a larger frame interval, "
                            "a smaller width, or JPG, then extract again. No partial ZIP was saved."
                        )
                    saved += 1
                    archive.writestr(f"frames/{saved}{extension}", encoded.tobytes())
                    if preview is None:
                        h, w = frame.shape[:2]
                        thumb = cv2.resize(frame, (min(w, 640), max(1, round(h * min(w, 640) / w))))
                        preview = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                index += 1
                if progress and (index % 30 == 0 or index == 1):
                    progress(min(index / total, 0.99) if total else 0.0, saved)
            if not saved:
                raise ValueError("No frames could be decoded. The file may be damaged or unsupported.")
        if Path(zip_path).stat().st_size > MAX_ZIP_BYTES:
            raise ValueError("ZIP exceeds 200 MB. Increase the frame interval and try again.")
        return saved, fps, preview
    finally:
        capture.release()


def clear_result():
    st.session_state.pop("frame_result", None)


def main():
    st.set_page_config(page_title="Video to Frames", page_icon="SpacePointer.PNG")
    
    st.image("softwareLogo.png", width=200)
    st.title("Video → Image Sequence")
    st.write("Upload a video, extract its frames, and download them together as a ZIP.")
    video = st.file_uploader(
        "Choose a video", type=["mp4", "mov", "avi", "mkv", "webm", "m4v"],
        on_change=clear_result,
    )
    left, right = st.columns(2)
    with left:
        every_n = st.number_input(
            "Save every Nth frame", min_value=1, max_value=10000, value=1,
            help="1 saves every frame. 5 saves source frames 1, 6, 11, and so on.",
            on_change=clear_result,
        )
        image_format = st.selectbox("Image format", ["PNG", "JPG"], on_change=clear_result)
    with right:
        max_width = st.selectbox(
            "Maximum image width", [0, 1920, 1280, 640],
            format_func=lambda x: "Original size" if x == 0 else f"{x} pixels",
            on_change=clear_result,
        )
        quality = st.slider("JPG quality", 50, 100, 90,
                            disabled=image_format == "PNG", on_change=clear_result)
    st.caption("PNG preserves frame detail; JPG usually makes a smaller ZIP. "
               "Images retain their aspect ratio. ZIP output is limited to 200 MB.")
    if video is not None:
        st.caption(f"Selected: {video.name} · {video.size / 1024**2:.1f} MB")
    if st.button("Extract frames", type="primary", disabled=video is None):
        clear_result()
        bar = st.progress(0, text="Opening video…")
        try:
            with tempfile.TemporaryDirectory(prefix="video_frames_") as directory:
                source = Path(directory) / ("input" + Path(video.name).suffix.lower())
                source.write_bytes(video.getbuffer())
                target = Path(directory) / "frames.zip"
                count, fps, preview = extract_frames(
                    source, target, int(every_n), image_format, quality, max_width,
                    progress=lambda fraction, n: bar.progress(
                        fraction, text=f"Extracting… {n:,} images saved"
                    ),
                )
                stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(video.name).stem).strip("_")[:80] or "video"
                st.session_state.frame_result = {
                    "data": target.read_bytes(), "filename": f"{stem}_frames.zip",
                    "count": count, "fps": fps, "preview": preview,
                }
            bar.progress(1.0, text="Extraction complete")
        except (ValueError, OSError, cv2.error, zipfile.BadZipFile) as error:
            bar.empty()
            st.error(str(error))
    result = st.session_state.get("frame_result")
    if result:
        st.success(f"Ready: {result['count']:,} images · {len(result['data']) / 1024**2:.1f} MB")
        if math.isfinite(result["fps"]) and result["fps"] > 0:
            st.caption(f"Reported source frame rate: {result['fps']:.3f} FPS")
        st.image(result["preview"], caption="First exported frame")
        st.download_button(
            "Download image sequence ZIP", data=result["data"],
            file_name=result["filename"], mime="application/zip", on_click="ignore",
        )
        st.caption("Unzip the download to find 1.png, 2.png, 3.png, etc. "
                   "inside the frames folder (or .jpg for JPG exports).")


if __name__ == "__main__":
    main()
