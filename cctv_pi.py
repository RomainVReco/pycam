import io
import logging
import socketserver
import threading
import numpy as np
import time
import os
import json
import importlib.resources as pkg_resources
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput, FileOutput
from picamera2.encoders import JpegEncoder
from datetime import datetime
from http import server
from threading import Condition
from mail_class import GenerateMail


PAGE = """\
<html>
<head>
<title>CCTV_PI</title>
</head>
<body>
<h1>Camera 1 - Salon </h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""

with open("config_server.json") as config:
    config_data = json.load(config)

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def server():
    try:
        address = (config_data["ip_address"], config_data["port"])
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        picam2.stop_recording()


def handling_mail_thread(mail, file_name):
    mail.prepare_mail(file_name)
    #mail.send_mail()
    mail.remove_message()

def handle_end_recording(circ, mse):
    circ.stop()
    end_date = datetime.now()
    end_recording = end_date.strftime("%m_%d_%Y_%H:%M:%S")
    print("Stop recording", mse, end_recording)
    return False

VIDEO_SIZE_LIMIT = 10000000/2
lsize = (640, 480)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (1280, 720), "format": "RGB888"},
                                                 lores={"size": lsize, "format": "YUV420"})
picam2.configure(video_config)
picam2.start_preview()
encoder = H264Encoder(1000000, True)
circ = CircularOutput()
encoder.output = [circ]
picam2.encoders = encoder
picam2.start()
picam2.start_encoder()

output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

mail = GenerateMail()
mail.prepare_singleton()

w, h = lsize
prev = None
encoding = False
ltime = 0
t = threading.Thread(target=server)
t.setDaemon(True)
t.start()
video_name = None
PATH = config_data["file_path"]

while True:
    cur = picam2.capture_buffer("lores")
    cur = cur[:w * h].reshape(h, w)
    if prev is not None:
        mse = np.square(np.subtract(cur, prev)).mean()
        if mse > 30:
            if not encoding:
                date_now = datetime.now()
                str_date = date_now.strftime("%m_%d_%Y_%HH%MM%SS")
                filename = str_date
                screenshot_name = PATH+filename+".jpeg"
                picam2.capture_file(screenshot_name)
                email_thread_screenshot = threading.Thread(target=handling_mail_thread, args=(mail, screenshot_name))
                email_thread_screenshot.start()
                video_name = PATH+filename+".h264"
                print("video_name", video_name)
                circ.fileoutput = video_name
                circ.start()
                encoding = True
                print("New Motion", mse, str_date)
            ltime = time.time()
        else:
            if encoding:
                if time.time() - ltime > 5.0 or (video_name and os.stat(video_name).st_size>VIDEO_SIZE_LIMIT):
                    print("condition de fin de video ok")
                    encoding = False
                    #encoding = handle_end_recording(circ, mse)
                    #email_thread_video = threading.Thread(target=handling_mail_thread, args=(mail, video_name))
                    #email_thread_video.start()
    prev = cur

picam2.stop_encoder()