import time
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

def display_console_text(text):
    line_height = 8  # Height of a line
    max_lines = height // line_height  # Maximum lines that can fit on the display

    words = text.split()
    lines = ['']
    line_index = 0

    for word in words:
        # Check if adding the word exceeds the display width
        if draw.textsize(lines[line_index] + " " + word, font=font)[0] <= width:
            lines[line_index] += word + " "
        else:
            lines.append(word + " ")
            line_index += 1

    # Display the text on the OLED
    for idx, line in enumerate(lines):
        # Scroll up if the number of lines exceeds the display's capacity
        if idx >= max_lines:
            for i in range(1, max_lines):
                draw.text((0, (i - 1) * line_height), lines[idx - max_lines + i], font=font, fill=255)
        else:
            draw.text((0, idx * line_height), line, font=font, fill=255)

    disp.image(image)
    disp.display()
    time.sleep(2)  # Adjust the display duration as needed

# Rev.ai access token
access_token = "02Xw3PNnMTiXAe5VENUQKJj3c5RVMMtap8iD8HhzLl0NzjOItgwr4UKTC96h0DFq6uLXSLqhAL0HUMvemhmbukGe6OnAQ"

# Microphone stream class
class MicrophoneStream(object):
    # ... (rest of your existing code)

# Rev.ai streaming client setup and main execution
# ... (rest of your existing code)

    try:
        response_gen = streamclient.start(stream.generator())
        full_transcript = ''

        for response in response_gen:
            response_json = json.loads(response)
            if response_json['type'] in ('final', 'partial'):
                elements = response_json['elements']
                transcript = ' '.join(elem['value'] for elem in elements if elem['type'] == 'text')
                full_transcript += transcript
                display_console_text(transcript)  # Display text on OLED

        # Clear the display after all lines are shown
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
        disp.image(image)
        disp.display()

    except KeyboardInterrupt:
        streamclient.end()
