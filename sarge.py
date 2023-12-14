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

# Function to display text on OLED
# Function to display text on OLED and scroll if needed
def display_on_oled(text):
    global disp, draw, image, width, height, font
    
    # Split the text into lines
    lines = text.split('\n')
    y = 0
    
    # Clear the display to a fresh slate if all lines cannot fit at once
    if len(lines) * 8 > height:
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
    
    for line in lines:
        # Calculate the width and height of the line to display
        width, _ = draw.textsize(line, font=font)
        
        # Ensure the text fits within the OLED display
        if width > disp.width:
            # Scroll text if it's wider than the display
            for i in range(width - disp.width):
                draw.rectangle((0, 0, disp.width, disp.height), outline=0, fill=0)
                draw.text((disp.width - i, y), line, font=font, fill=255)
                disp.image(image)
                disp.display()
                time.sleep(0.10)
        else:
            # Display text within the OLED's bounds
            draw.text((0, y), line, font=font, fill=255)
            y += 8
    
    disp.image(image)
    disp.display()


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
                display_on_oled(transcript)  # Display text on OLED

        # Clear the display after all lines are shown
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
        disp.image(image)
        disp.display()

    except KeyboardInterrupt:
        streamclient.end()
