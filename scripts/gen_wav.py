import wave, struct, math

with wave.open('/tmp/test.wav', 'w') as f:
    f.setnchannels(2)
    f.setsampwidth(2)
    f.setframerate(48000)
    for i in range(48000): # 1 second of 440Hz tone
        val = int(12000 * math.sin(2 * math.pi * 440 * i / 48000))
        f.writeframes(struct.pack('<hh', val, val))
print('Generated /tmp/test.wav (48kHz stereo 16-bit, 1s tone)')
