# Audio_Transcription_Lib.py
#########################################
# Transcription Library
# This library is used to perform transcription of audio files.
# Currently, uses faster_whisper for transcription.
#
####################
# Function List
#
# 1. convert_to_wav(video_file_path, offset=0, overwrite=False)
# 2. speech_to_text(audio_file_path, selected_source_lang='en', whisper_model='small.en', vad_filter=False)
#
####################
#
# Import necessary libraries to run solo for testing
import gc
import json
import logging
import multiprocessing
import os
import queue
import sys
import subprocess
import tempfile
import threading
import time
# DEBUG Imports
#from memory_profiler import profile
import pyaudio
from faster_whisper import WhisperModel as OriginalWhisperModel
from typing import Optional, Union, List, Dict, Any
#
# Import Local
from App_Function_Libraries.Utils.Utils import load_comprehensive_config
from App_Function_Libraries.Metrics.metrics_logger import log_counter, log_histogram
#
#######################################################################################################################
# Function Definitions
#

# Convert video .m4a into .wav using ffmpeg
#   ffmpeg -i "example.mp4" -ar 16000 -ac 1 -c:a pcm_s16le "output.wav"
#       https://www.gyan.dev/ffmpeg/builds/
#


whisper_model_instance = None
config = load_comprehensive_config()
processing_choice = config.get('Processing', 'processing_choice', fallback='cpu')
total_thread_count = multiprocessing.cpu_count()


class WhisperModel(OriginalWhisperModel):
    tldw_dir = os.path.dirname(os.path.dirname(__file__))
    default_download_root = os.path.join(tldw_dir, 'models', 'Whisper')

    valid_model_sizes = [
        "tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium",
        "large-v1", "large-v2", "large-v3", "large", "distil-large-v2", "distil-medium.en",
        "distil-small.en", "distil-large-v3",
    ]

    def __init__(
        self,
        model_size_or_path: str,
        device: str = processing_choice,
        device_index: Union[int, List[int]] = 0,
        compute_type: str = "default",
        cpu_threads: int = 0,#total_thread_count, FIXME - I think this should be 0
        num_workers: int = 1,
        download_root: Optional[str] = None,
        local_files_only: bool = False,
        files: Optional[Dict[str, Any]] = None,
        **model_kwargs: Any
    ):
        if download_root is None:
            download_root = self.default_download_root

        os.makedirs(download_root, exist_ok=True)

        # FIXME - validate....
        # Also write an integration test...
        # Check if model_size_or_path is a valid model size
        if model_size_or_path in self.valid_model_sizes:
            # It's a model size, so we'll use the download_root
            model_path = os.path.join(download_root, model_size_or_path)
            if not os.path.isdir(model_path):
                # If it doesn't exist, we'll let the parent class download it
                model_size_or_path = model_size_or_path  # Keep the original model size
            else:
                # If it exists, use the full path
                model_size_or_path = model_path
        else:
            # It's not a valid model size, so assume it's a path
            model_size_or_path = os.path.abspath(model_size_or_path)

        super().__init__(
            model_size_or_path,
            device=device,
            device_index=device_index,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            num_workers=num_workers,
            download_root=download_root,
            local_files_only=local_files_only,
# Maybe? idk, FIXME
#            files=files,
#            **model_kwargs
        )

def get_whisper_model(model_name, device):
    global whisper_model_instance
    if whisper_model_instance is None:
        logging.info(f"Initializing new WhisperModel with size {model_name} on device {device}")
        whisper_model_instance = WhisperModel(model_name, device=device)
    return whisper_model_instance

# os.system(r'.\Bin\ffmpeg.exe -ss 00:00:00 -i "{video_file_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{out_path}"')
#DEBUG
#@profile
def convert_to_wav(video_file_path, offset=0, overwrite=False):
    log_counter("convert_to_wav_attempt", labels={"file_path": video_file_path})
    start_time = time.time()

    out_path = os.path.splitext(video_file_path)[0] + ".wav"

    if os.path.exists(out_path) and not overwrite:
        print(f"File '{out_path}' already exists. Skipping conversion.")
        logging.info(f"Skipping conversion as file already exists: {out_path}")
        log_counter("convert_to_wav_skipped", labels={"file_path": video_file_path})
        return out_path

    print("Starting conversion process of .m4a to .WAV")
    out_path = os.path.splitext(video_file_path)[0] + ".wav"

    try:
        if os.name == "nt":
            logging.debug("ffmpeg being ran on windows")

            if sys.platform.startswith('win'):
                ffmpeg_cmd = ".\\Bin\\ffmpeg.exe"
                logging.debug(f"ffmpeg_cmd: {ffmpeg_cmd}")
            else:
                ffmpeg_cmd = 'ffmpeg'  # Assume 'ffmpeg' is in PATH for non-Windows systems

            command = [
                ffmpeg_cmd,  # Assuming the working directory is correctly set where .\Bin exists
                "-ss", "00:00:00",  # Start at the beginning of the video
                "-i", video_file_path,
                "-ar", "16000",  # Audio sample rate
                "-ac", "1",  # Number of audio channels
                "-c:a", "pcm_s16le",  # Audio codec
                out_path
            ]
            try:
                # Redirect stdin from null device to prevent ffmpeg from waiting for input
                with open(os.devnull, 'rb') as null_file:
                    result = subprocess.run(command, stdin=null_file, text=True, capture_output=True)
                if result.returncode == 0:
                    logging.info("FFmpeg executed successfully")
                    logging.debug("FFmpeg output: %s", result.stdout)
                else:
                    logging.error("Error in running FFmpeg")
                    logging.error("FFmpeg stderr: %s", result.stderr)
                    raise RuntimeError(f"FFmpeg error: {result.stderr}")
            except Exception as e:
                logging.error("Error occurred - ffmpeg doesn't like windows")
                raise RuntimeError("ffmpeg failed")
        elif os.name == "posix":
            os.system(f'ffmpeg -ss 00:00:00 -i "{video_file_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{out_path}"')
        else:
            raise RuntimeError("Unsupported operating system")
        logging.info("Conversion to WAV completed: %s", out_path)
        log_counter("convert_to_wav_success", labels={"file_path": video_file_path})
    except Exception as e:
        logging.error("speech-to-text: Error transcribing audio: %s", str(e))
        log_counter("convert_to_wav_error", labels={"file_path": video_file_path, "error": str(e)})
        return {"error": str(e)}

    conversion_time = time.time() - start_time
    log_histogram("convert_to_wav_duration", conversion_time, labels={"file_path": video_file_path})

    gc.collect()
    return out_path


# Transcribe .wav into .segments.json
#DEBUG
#@profile
# FIXME - I feel like the `vad_filter` shoudl be enabled by default....
def speech_to_text(audio_file_path, selected_source_lang='en', whisper_model='medium.en', vad_filter=False, diarize=False):
    log_counter("speech_to_text_attempt", labels={"file_path": audio_file_path, "model": whisper_model})
    time_start = time.time()

    if audio_file_path is None:
        log_counter("speech_to_text_error", labels={"error": "No audio file provided"})
        raise ValueError("speech-to-text: No audio file provided")
    logging.info("speech-to-text: Audio file path: %s", audio_file_path)

    try:
        _, file_ending = os.path.splitext(audio_file_path)
        out_file = audio_file_path.replace(file_ending, "-whisper_model-"+whisper_model+".segments.json")
        prettified_out_file = audio_file_path.replace(file_ending, "-whisper_model-"+whisper_model+".segments_pretty.json")
        if os.path.exists(out_file):
            logging.info("speech-to-text: Segments file already exists: %s", out_file)
            with open(out_file) as f:
                global segments
                segments = json.load(f)
            return segments

        logging.info('speech-to-text: Starting transcription...')
        # FIXME - revisit this
        options = dict(language=selected_source_lang, beam_size=10, best_of=10, vad_filter=vad_filter)
        transcribe_options = dict(task="transcribe", **options)
        # use function and config at top of file
        logging.debug("speech-to-text: Using whisper model: %s", whisper_model)
        whisper_model_instance = get_whisper_model(whisper_model, processing_choice)
        # faster_whisper transcription right here - FIXME -test batching - ha
        segments_raw, info = whisper_model_instance.transcribe(audio_file_path, **transcribe_options)

        segments = []
        for segment_chunk in segments_raw:
            chunk = {
                "Time_Start": segment_chunk.start,
                "Time_End": segment_chunk.end,
                "Text": segment_chunk.text
            }
            logging.debug("Segment: %s", chunk)
            segments.append(chunk)
            # Print to verify its working
            logging.info(f"{segment_chunk.start:.2f}s - {segment_chunk.end:.2f}s | {segment_chunk.text}")

            # Log it as well.
            logging.debug(
                f"Transcribed Segment: {segment_chunk.start:.2f}s - {segment_chunk.end:.2f}s | {segment_chunk.text}")

        if segments:
            segments[0]["Text"] = f"This text was transcribed using whisper model: {whisper_model}\n\n" + segments[0]["Text"]

        if not segments:
            log_counter("speech_to_text_error", labels={"error": "No transcription produced"})
            raise RuntimeError("No transcription produced. The audio file may be invalid or empty.")

        transcription_time = time.time() - time_start
        logging.info("speech-to-text: Transcription completed in %.2f seconds", transcription_time)
        log_histogram("speech_to_text_duration", transcription_time, labels={"file_path": audio_file_path, "model": whisper_model})
        log_counter("speech_to_text_success", labels={"file_path": audio_file_path, "model": whisper_model})
        # Save the segments to a JSON file - prettified and non-prettified
        # FIXME refactor so this is an optional flag to save either the prettified json file or the normal one
        save_json = True
        if save_json:
            logging.info("speech-to-text: Saving segments to JSON file")
            output_data = {'segments': segments}
            logging.info("speech-to-text: Saving prettified JSON to %s", prettified_out_file)
            with open(prettified_out_file, 'w') as f:
                json.dump(output_data, f, indent=2)

            logging.info("speech-to-text: Saving JSON to %s", out_file)
            with open(out_file, 'w') as f:
                json.dump(output_data, f)

        logging.debug(f"speech-to-text: returning {segments[:500]}")
        gc.collect()
        return segments

    except Exception as e:
        logging.error("speech-to-text: Error transcribing audio: %s", str(e))
        log_counter("speech_to_text_error", labels={"file_path": audio_file_path, "model": whisper_model, "error": str(e)})
        raise RuntimeError("speech-to-text: Error transcribing audio")


def record_audio(duration, sample_rate=16000, chunk_size=1024):
    log_counter("record_audio_attempt", labels={"duration": duration})
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=chunk_size)

    print("Recording...")
    frames = []
    stop_recording = threading.Event()
    audio_queue = queue.Queue()

    def audio_callback():
        for _ in range(0, int(sample_rate / chunk_size * duration)):
            if stop_recording.is_set():
                break
            data = stream.read(chunk_size)
            audio_queue.put(data)

    audio_thread = threading.Thread(target=audio_callback)
    audio_thread.start()

    return p, stream, audio_queue, stop_recording, audio_thread


def stop_recording(p, stream, audio_queue, stop_recording_event, audio_thread):
    log_counter("stop_recording_attempt")
    start_time = time.time()
    stop_recording_event.set()
    audio_thread.join()

    frames = []
    while not audio_queue.empty():
        frames.append(audio_queue.get())

    print("Recording finished.")

    stream.stop_stream()
    stream.close()
    p.terminate()

    stop_time = time.time() - start_time
    log_histogram("stop_recording_duration", stop_time)
    log_counter("stop_recording_success")
    return b''.join(frames)

def save_audio_temp(audio_data, sample_rate=16000):
    log_counter("save_audio_temp_attempt")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        import wave
        wf = wave.open(temp_file.name, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)
        wf.close()
        log_counter("save_audio_temp_success")
        return temp_file.name

#
#
#######################################################################################################################