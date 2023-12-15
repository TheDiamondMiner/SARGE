import pyaudio
import csv
import json
from six.moves import queue
import busio
from rev_ai.models import MediaConfig
from rev_ai.streamingclient import RevAiStreamingClient
from board import SCL, SDA
from oled_text import OledText

access_token = ""

i2c = busio.I2C(SCL, SDA)
oled = OledText(i2c, 128, 64)
oled.auto_show = False
isFull = False

file_path = 'auth.csv'

def ReadCSVFile(path):
    with open(path, 'r') as file:
        data_line = file.readline().strip()
    return data_line.split(',')

def GetAccessTokenFromCSV():
    csvData = ReadCSVFile(file_path)
    authTokens = csvData[1:]
    lastIndex = int(csvData[0])
    
    if lastIndex < 3:
        currentIndex = lastIndex + 1
    else: #incase of 4 we want to reset back to -1
        lastIndex = -1
        
    access_token = authTokens[currentIndex]
    UpdateLastReadIndex(file_path,currentIndex)
    
def UpdateLastReadIndex(path, new_last_read_index):
    with open(path, 'r') as file:
        lines = file.readlines()

    lines[0] = str(new_last_read_index) + ',' + ','.join(lines[0].split(',')[1:])

    with open(path, 'w') as file:
        file.writelines(lines)

GetAccessTokenFromCSV()

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
    words = text.split(' ')
    lines = ['' for _ in range(5)]  # Initialize 5 lines for the OLED display
    line_index = 0

    for word in words:
        # Check if the word will fit on the current line
        if len(lines[line_index] + word) <= 20:
            lines[line_index] += word + ' '
        else:
            if line_index < 4:  
                line_index += 1
                lines[line_index] += word + ' '  # Add the word to the new line
            else:
                # If there's no more room, stop adding words
                break
            
    for i in range(5):
        oled.text(lines[i], i+1)

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
