from RealtimeSTT import AudioToTextRecorder
import torch

# File to store the transcribed text
TRANSCRIBED_TEXT_FILE = "transcribed_text.txt"

def process_text(text):
    print(f"Recognized Text: {text}")
    # Save the transcribed text to a file
    with open(TRANSCRIBED_TEXT_FILE, "w") as file:
        file.write(text)

if __name__ == '__main__':
    try:
        # Check available models
        print("Available models: base, small, medium, large, large-v2")
        
        # Check if CUDA is available
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_device = torch.cuda.get_device_name(0)
            print(f"CUDA is available. Using device: {cuda_device}")
            print(f"Memory Usage: {torch.cuda.memory_allocated(0)/1024**2:.2f} MB / {torch.cuda.memory_reserved(0)/1024**2:.2f} MB")
        else:
            print("CUDA is not available. Falling back to CPU.")

        print("Initializing recorder...")
        
        # Initialize the recorder with GPU support if available, else CPU
        device = "cuda" if cuda_available else "cpu"
        recorder = AudioToTextRecorder(device=device, model="base.en")
        print(f"Recorder initialized on {device}. Waiting for input...")

        # Start real-time transcription
        print("Speak now...")
        while True:
            recorder.text(process_text)
    
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully...")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        try:
            if 'recorder' in locals() and recorder:
                recorder.stop()
                print("Recorder stopped.")
        except Exception as cleanup_error:
            print(f"Error during cleanup: {cleanup_error}")
