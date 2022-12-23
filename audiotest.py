"""PyAudio Example: Play a WAVE file."""

import pyaudio
import wave
import sys

CHUNK = 1024

if len(sys.argv) < 2:
    print("Plays a wave file.\n\nUsage: %s filename.wav" % sys.argv[0])
    sys.exit(-1)


class AudioPlayer:
    DEFAULT_CHUNKSIZE = 1024

    def __init__(self, wav_filename, pyaudio_instance = pyaudio.PyAudio(), chunksize = DEFAULT_CHUNKSIZE):
        self._source_filename = wav_filename
        self._pyaudio = pyaudio_instance
        self._sampwidth = None
        self._nchannels = None
        self._framerate = None
        self._chunks = []
        self._chunksize = chunksize
    
    def open(self):
        self._read_file()
    
    def _read_file(self):
        wf = wave.open(self._source_filename, 'rb')
        self._sampwidth = wf.getsampwidth()
        self._nchannels = wf.getnchannels()
        self._framerate = wf.getframerate()
        data = wf.readframes(self._chunksize)
        while len(data):
            self._chunks.append(data)
            data = wf.readframes(self._chunksize)
    
    def play(self):
        p = self._pyaudio
        stream = p.open(format=p.get_format_from_width(self._sampwidth),
            channels=self._nchannels,
            rate=self._framerate,
            output=True)
        for chunk in self._chunks:
            stream.write(chunk)
        stream.stop_stream()
        stream.close()
    
    def close(self):
        self._pyaudio.terminate()


audio = AudioPlayer(sys.argv[1])
audio.open()
audio.play()
audio.close()

