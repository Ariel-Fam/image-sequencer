"""Run against the built image: docker run --rm -i IMAGE python < this_file."""

import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.getcwd())
from main import extract_frames


class ContainerSmokeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def make_video(self, extension, codec):
        source = self.directory / ("sample" + extension)
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*codec),
                                 12, (96, 64))
        self.assertTrue(writer.isOpened(), f"Encoder unavailable: {codec}")
        try:
            for index in range(8):
                writer.write(np.full((64, 96, 3), index * 25, dtype=np.uint8))
        finally:
            writer.release()
        return source

    def check_archive(self, data, count, extension, shape):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(),
                             [f"frames/{i}{extension}" for i in range(1, count + 1)])
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                decoded = cv2.imdecode(np.frombuffer(archive.read(name), np.uint8),
                                       cv2.IMREAD_COLOR)
                self.assertIsNotNone(decoded)
                self.assertEqual(decoded.shape, shape)

    def test_video_decoding_and_exports(self):
        for suffix, codec in [(".avi", "MJPG"), (".mp4", "mp4v")]:
            source = self.make_video(suffix, codec)
            for image_format, interval, width, count, shape in [
                ("PNG", 1, 0, 8, (64, 96, 3)),
                ("JPG", 3, 48, 3, (32, 48, 3)),
            ]:
                with self.subTest(video=suffix, export=image_format):
                    target = self.directory / "frames.zip"
                    progress = []
                    saved, fps, preview = extract_frames(
                        source, target, every_n=interval, image_format=image_format,
                        max_width=width, progress=lambda *value: progress.append(value))
                    self.assertEqual(saved, count)
                    self.assertAlmostEqual(fps, 12, places=1)
                    self.assertEqual(preview.shape, shape)
                    self.assertTrue(progress)
                    self.check_archive(target.read_bytes(), count,
                                       ".png" if image_format == "PNG" else ".jpg", shape)

    def test_streamlit_extraction_flow(self):
        source = self.make_video(".mp4", "mp4v")
        for image_format, interval, count in [("PNG", 1, 8), ("JPG", 3, 3)]:
            with self.subTest(export=image_format):
                upload = io.BytesIO(source.read_bytes())
                upload.name = "sample.mp4"
                upload.size = len(upload.getvalue())
                # AppTest cannot upload files, so supply the uploaded bytes at
                # that boundary and exercise the real widgets and extraction.
                with patch("streamlit.file_uploader", return_value=upload):
                    app = AppTest.from_file("main.py", default_timeout=20).run()
                    self.assertEqual(len(app.exception), 0)
                    app.selectbox[0].select(image_format)
                    app.number_input[0].set_value(interval)
                    app.button[0].click().run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertEqual(len(app.error), 0)
                    self.assertEqual(len(app.success), 1)
                    result = app.session_state["frame_result"]
                    self.assertEqual(result["count"], count)
                    self.assertEqual(result["filename"], "sample_frames.zip")
                    self.check_archive(result["data"], count,
                                       ".png" if image_format == "PNG" else ".jpg",
                                       (64, 96, 3))

    def test_invalid_video(self):
        source = self.directory / "invalid.mp4"
        source.write_bytes(b"not a video")
        with self.assertRaisesRegex(ValueError, "Cannot open this video"):
            extract_frames(source, self.directory / "frames.zip")


if __name__ == "__main__":
    unittest.main(verbosity=2)
