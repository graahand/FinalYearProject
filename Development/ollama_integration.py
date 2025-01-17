import os
import time
from ollama import chat, ChatResponse

# Path to the transcribed text file
TRANSCRIBED_TEXT_FILE = "transcribed_text.txt"

def process_with_llama(prompt):
    """
    Uses the Ollama Llama model to process the given prompt.
    """
    try:
        # Query the Llama model
        response: ChatResponse = chat(model="llama3.1", messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response.message.content
    except Exception as e:
        return f"Error querying Llama: {str(e)}"

def process_transcribed_text():
    """
    Continuously monitors the transcribed text file and processes new queries with Llama.
    """
    last_processed_text = None

    while True:
        # Check if the transcribed text file exists and has content
        if os.path.exists(TRANSCRIBED_TEXT_FILE) and os.path.getsize(TRANSCRIBED_TEXT_FILE) > 0:
            with open(TRANSCRIBED_TEXT_FILE, "r") as file:
                transcribed_text = file.read().strip()
            
            # Only process if the text is new
            if transcribed_text != last_processed_text:
                print(f"New transcribed text detected: {transcribed_text}")
                last_processed_text = transcribed_text

                # Generate Llama response
                print("Processing with Llama...")
                llama_response = process_with_llama(transcribed_text)
                print("Llama Response:")
                print(llama_response)
        
        time.sleep(1)

if __name__ == "__main__":
    print("Waiting for transcribed text...")
    process_transcribed_text()
