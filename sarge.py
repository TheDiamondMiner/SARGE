import pyaudio
from rev_ai.models import MediaConfig
from rev_ai.streamingclient import RevAiStreamingClient
from six.moves import queue
import json
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.virtual import viewport
from luma.core.render import canvas
from PIL import ImageFont
import time

# Replace 'YOUR_ACCESS_TOKEN' with your actual Rev.ai access token
access_token = "02TAiLcp-j1gkC-5waYgDkzPXvv3IYhQ4D7gO2v2CFlQtMoMl4bkPsw7WFWxr3fT_3GoCVLmD-PF4ln4GoRPrBxvF5rNU"

# OLED display setup
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
virtual = viewport(device, width=device.width, height=device.height)

def display_text_on_oled(text):
    with canvas(virtual) as draw:
        font = ImageFont.load_default()
        lines = virtual.text(text, (0, 0), font=font, fill="white")

        # Scroll text if it's longer than the display height
        if lines > device.height:
            for i in range(lines - device.height):
                virtual.set_position((0, -i))
                time.sleep(0.1)  # Adjust scroll speed as needed
        else:
            time.sleep(5)  # Display for 5 seconds if it fits entirely

class MicrophoneStream(object):
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b''.join(data)

# Configurations
rate = 44100
chunk = int(rate / 10)
example_mc = MediaConfig('audio/x-raw', 'interleaved', 44100, 'S16LE', 1)
streamclient = RevAiStreamingClient(access_token, example_mc)

with MicrophoneStream(rate, chunk) as stream:
    try:
        response_gen = streamclient.start(stream.generator())
        full_transcript = ''

        for response in response_gen:
            response_json = json.loads(response)
            if response_json['type'] in ('final', 'partial'):
                elements = response_json['elements']
                transcript = ' '.join(elem['value'] for elem in elements if elem['type'] == 'text')
                full_transcript += transcript
                display_text_on_oled(transcript)  # Display text on OLED

    except KeyboardInterrupt:
        streamclient.end()
