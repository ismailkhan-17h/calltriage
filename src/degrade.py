import glob, os
from pydub import AudioSegment

SNRS = [20, 10, 5]  # dB, lower = noisier


def degrade(speech_path, noise_path, snr_db, out_path):
    speech = AudioSegment.from_file(speech_path).set_channels(1).set_frame_rate(8000)
    noise = AudioSegment.from_file(noise_path).set_channels(1).set_frame_rate(8000)
    noise = noise * (len(speech) // len(noise) + 1)      # loop to length
    noise = noise[:len(speech)]
    noise = noise.apply_gain(speech.dBFS - noise.dBFS - snr_db)
    speech.overlay(noise).export(out_path, format="wav")


if __name__ == "__main__":
    os.makedirs("data/noisy", exist_ok=True)
    noise_file = sorted(glob.glob("data/noise/*.*"))[0]
    for f in sorted(glob.glob("data/raw/*.*")):
        name = os.path.splitext(os.path.basename(f))[0]
        for snr in SNRS:
            out = f"data/noisy/{name}__snr{snr}.wav"
            degrade(f, noise_file, snr, out)
            print("made", out)