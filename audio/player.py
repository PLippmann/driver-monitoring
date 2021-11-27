import sounddevice as sd
import soundfile as sf

data, fs = sf.read('arrow.wav')
sd.play(data, fs)
sd.wait()
print("Playback complete")
