import time
import subprocess
import pyaudio
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
from rev_ai.models import MediaConfig
from rev_ai.streamingclient import RevAiStreamingClient
from six.moves import queue
import json
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# Rev.ai access token
access_token = "02Xw3PNnMTiXAe5VENUQKJj3c5RVMMtap8iD8HhzLl0NzjOItgwr4UKTC96h0DFq6uLXSLqhAL0HUMvemhmbukGe6OnAQ"

# OLED display setup
RST = None
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)
disp.begin()
disp.clear()
disp.display()
width = disp.width
height = disp.height
image = Image.new('1', (width, height))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()

def display_text(text):
    max_chars = 21  # Maximum characters in a line
    lines = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
    line_height = 8  # Height of a line
    max_lines = height // line_height  # Maximum lines that can fit on the display

    for i in range(0, len(lines), max_lines):
        draw.rectangle((0,0,width,height), outline=0, fill=0)  # Clear the display

        for j in range(max_lines):
            if i + j < len(lines):
                y = j * line_height  # Calculate y-coordinate for the current line
                draw.text((0, y), lines[i + j], font=font, fill=255)

        disp.image(image)
        disp.display()
        time.sleep(2)  # Wait for 2 seconds before updating the display

    disp.image(image)
    disp.display()



# Microphone stream class
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


# Rev.ai streaming client setup
rate = 44100
chunk = int(rate / 10)
mc = MediaConfig('audio/x-raw', 'interleaved', rate, 'S16LE', 1)
streamclient = RevAiStreamingClient(access_token, mc)

# Main execution
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
                display_text(transcript)  # Display text on OLED

        # Clear the display after all lines are shown
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
        disp.image(image)
        disp.display()

    except KeyboardInterrupt:
        streamclient.end()
