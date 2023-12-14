import pyaudio
from rev_ai.models import MediaConfig
from rev_ai.streamingclient import RevAiStreamingClient
from six.moves import queue
import json
from board import SCL, SDA
import busio
from oled_text import OledText

# Replace 'YOUR_ACCESS_TOKEN' with your actual Rev.ai access token
access_token = "02Xw3PNnMTiXAe5VENUQKJj3c5RVMMtap8iD8HhzLl0NzjOItgwr4UKTC96h0DFq6uLXSLqhAL0HUMvemhmbukGe6OnAQ"

i2c = busio.I2C(SCL, SDA)
oled = OledText(i2c, 128, 64)
oled.auto_show = False
isFull = False

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

def print_toOled(text):
    for i in range(5):  # 5 lines on the OLED display
        start_index = i * 20
        end_index = start_index + 20
        if start_index < len(text):
            line_text = text[start_index:end_index]
        else:
            line_text = ''  # Leave the line empty if there's no more text
        oled.text(line_text, i+1)  # OLED line numbers start from 1

    if isFull:
        time.sleep(2)
        
    oled.show()



# Configurations
rate = 44100
chunk = int(rate / 10)
example_mc = MediaConfig('audio/x-raw', 'interleaved', 44100, 'S16LE', 1)
streamclient = RevAiStreamingClient(access_token, example_mc)

with MicrophoneStream(rate, chunk) as stream:
    try:
        response_gen = streamclient.start(stream.generator())
        for response in response_gen:
            response_json = json.loads(response)
            if response_json['type'] in ('final', 'partial'):
                elements = response_json['elements']
                transcript = ' '.join(elem['value'] for elem in elements if elem['type'] == 'text')
                print_toOled(transcript)

    except KeyboardInterrupt:
        streamclient.end()
        pass
