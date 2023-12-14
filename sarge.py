import pyaudio
import json
import time
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from rev_ai.models import MediaConfig
from rev_ai.streamingclient import RevAiStreamingClient
from six.moves import queue

access_token = "02TAiLcp-j1gkC-5waYgDkzPXvv3IYhQ4D7gO2v2CFlQtMoMl4bkPsw7WFWxr3fT_3GoCVLmD-PF4ln4GoRPrBxvF5rNU"

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

def display_text_oled(text):
    lines = text.split('\n')
    y = 0
    for line in lines:
        oled.fill(0)
        with Image.new("1", (WIDTH, HEIGHT)) as img:
            draw = ImageDraw.Draw(img)
            draw.text((0, y), line, font=font, fill=255)
            oled.image(img)
            oled.show()
            time.sleep(2)
            y += 10

def censor_print(text):
    profane_words = ["fuck", "motherfucker", "bitch", "bitchass","bitchassnigga","nigga"] #Bad Words, Please ignore.
    words = text.split()

    for i in range(len(words)):
        if words[i].lower() in profane_words:
            words[i] = '*'

    censored_text = ' '.join(words)
    display_text_oled(censored_text)

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
            if response_json['type'] in ('final'):
                elements = response_json['elements']
                transcript = ' '.join(elem['value'] for elem in elements if elem['type'] == 'text')
                full_transcript += transcript

        censor_print(full_transcript)

    except KeyboardInterrupt:
        streamclient.end()
        pass
