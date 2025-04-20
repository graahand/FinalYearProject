import torch
from transformers import AutoModelForCausalLM, AutoProcessor
import logging
from PIL import Image
import os

# Configure logging
logger = logging.getLogger(__name__)

# Set PyTorch memory allocation settings to reduce fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

class ModelHandler:
    _instance = None
    _model = None
    _processor = None
    _use_cuda = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.initialize_model()

    def initialize_model(self):
        try:
            if self._model is None:
                # Check if CUDA is available and has enough memory
                self._use_cuda = torch.cuda.is_available()
                
                if self._use_cuda:
                    # Get available GPU memory
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
                    logger.info(f"GPU memory available: {gpu_memory:.2f} GB")
                    
                    # If GPU has less than 4GB, use CPU instead
                    if gpu_memory < 4:
                        logger.warning(f"GPU memory ({gpu_memory:.2f} GB) is too low. Falling back to CPU.")
                        self._use_cuda = False
                
                device = torch.device("cuda" if self._use_cuda else "cpu")
                logger.info(f"Using device: {device}")
                
                # Initialize model with memory optimization
                if self._use_cuda:
                    # For CUDA, use device_map="auto" with memory optimization
                    self._model = AutoModelForCausalLM.from_pretrained(
                        "vikhyatk/moondream2",
                        revision="2025-04-14",
                        trust_remote_code=True,
                        device_map="auto",
                        torch_dtype=torch.float16,  # Use half precision to reduce memory usage
                        low_cpu_mem_usage=True
                    )
                else:
                    # For CPU, use memory optimization
                    self._model = AutoModelForCausalLM.from_pretrained(
                        "vikhyatk/moondream2",
                        revision="2025-04-14",
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )
                    
                logger.info(f"Successfully loaded Moondream2 model on {device}")
        except Exception as e:
            logger.error(f"Error loading Moondream2 model: {e}")
            # If CUDA fails, try CPU as fallback
            if self._use_cuda:
                logger.warning("CUDA initialization failed. Falling back to CPU.")
                self._use_cuda = False
                self.initialize_model()
            else:
                raise

    def generate_short_caption(self, image):
        """Generate a short caption for the image."""
        try:
            if isinstance(image, str):
                image = Image.open(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Clear CUDA cache before processing if using CUDA
            if self._use_cuda:
                torch.cuda.empty_cache()
                
            result = self._model.caption(image, length="short")
            logger.info(f"Generated short caption: {result['caption']}")
            return result["caption"]
        except Exception as e:
            logger.error(f"Error generating short caption: {e}")
            raise

    def generate_normal_caption(self, image):
        """Generate a normal caption for the image."""
        try:
            if isinstance(image, str):
                image = Image.open(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Clear CUDA cache before processing if using CUDA
            if self._use_cuda:
                torch.cuda.empty_cache()
                
            result = self._model.caption(image, length="normal", stream=True)
            caption = "".join(result["caption"])
            logger.info(f"Generated normal caption: {caption}")
            return caption
        except Exception as e:
            logger.error(f"Error generating normal caption: {e}")
            raise

    def process_query(self, image, query="What is in this image?"):
        """Process a query about the image."""
        try:
            if isinstance(image, str):
                image = Image.open(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Clear CUDA cache before processing if using CUDA
            if self._use_cuda:
                torch.cuda.empty_cache()
                
            result = self._model.query(image, query)
            logger.info(f"Generated query response: {result['answer']}")
            return result["answer"]
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise 