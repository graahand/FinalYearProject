from RealtimeSTT import AudioToTextRecorder
import threading
import time
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

class SpeechRecognizer:
    def __init__(self, recording_time=15):
        # Set environment variables for CPU-only mode
        os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Disable CUDA
        os.environ['USE_CUDA'] = '0'  # Force CPU mode
        
        try:
            # Initialize the recorder with CPU-only mode and minimal settings
            self.recorder = AudioToTextRecorder(
                model='tiny',  # Use tiny model for faster CPU processing
                language='en',
                device='cpu'
            )
            self.recording_time = recording_time
            self.transcribed_text = ""
            self.is_recording = False
            self._recording_thread = None
            self._stop_event = threading.Event()
            logger.info("Speech recognizer initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing speech recognizer: {str(e)}")
            raise
        
    def start_recording(self, callback=None):
        """
        Start recording audio and convert to text.
        Stops after self.recording_time seconds.
        
        Args:
            callback: Function to call when recording is complete
        """
        if self.is_recording:
            return False
            
        try:
            self.is_recording = True
            self.transcribed_text = ""
            self._stop_event.clear()
            
            def process_text(text):
                if text and not text.isspace():  # Only update if text is meaningful
                    self.transcribed_text = text
                    logger.debug(f"Transcribed text: {text}")
            
            def record_with_timeout():
                try:
                    # Start recording
                    self.recorder.text(process_text)
                    
                    # Wait for either timeout or stop event
                    timeout_time = time.time() + self.recording_time
                    while time.time() < timeout_time and not self._stop_event.is_set():
                        time.sleep(0.1)  # Short sleep to prevent CPU hogging
                    
                    # Stop recording
                    self.stop_recording()
                    
                    # Call the callback function if provided
                    if callback and callable(callback):
                        callback(self.transcribed_text)
                except Exception as e:
                    logger.error(f"Error in recording thread: {str(e)}")
                    self.is_recording = False
                    if callback and callable(callback):
                        callback("")
                finally:
                    self.is_recording = False
            
            # Start recording in a separate thread
            self._recording_thread = threading.Thread(target=record_with_timeout, daemon=True)
            self._recording_thread.start()
            return True
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            self.is_recording = False
            return False
        
    def stop_recording(self):
        """Manually stop the recording before the timeout."""
        if not self.is_recording:
            return False
            
        try:
            self._stop_event.set()  # Signal the recording thread to stop
            self.recorder.stop()
            self.is_recording = False
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=1.0)  # Wait for thread to finish
            return True
        except Exception as e:
            logger.error(f"Error stopping recording: {str(e)}")
            return False
        finally:
            self.is_recording = False
        
    def get_text(self):
        """Get the current transcribed text."""
        return self.transcribed_text 