document.addEventListener("DOMContentLoaded", function() {
    console.log("JavaScript loaded successfully!");

    // Get elements
    const browseBtn = document.getElementById("browse-files-btn");
    const fileInput = document.getElementById("file-input");
    const uploadBtn = document.getElementById("upload-btn");
    const cameraBtn = document.getElementById("camera-btn");
    const resetBtn = document.getElementById("reset-btn");
    const dropZone = document.getElementById("drop-zone");
    const queryInput = document.getElementById("query-input");
    const resultsContainer = document.getElementById("detection-results");
    const speechToTextBtn = document.getElementById("speech-to-text-btn");

    // Debug which elements are found
    const elements = {
        browseBtn,
        fileInput,
        uploadBtn,
        cameraBtn,
        resetBtn,
        dropZone,
        queryInput,
        resultsContainer,
        speechToTextBtn
    };

    console.log("Found elements:", Object.fromEntries(
        Object.entries(elements).map(([key, value]) => [key, !!value])
    ));

    // Browse button click handler
    if (browseBtn && fileInput) {
        browseBtn.addEventListener("click", () => fileInput.click());
    }

    // File input change handler
    if (fileInput) {
        fileInput.addEventListener("change", function(e) {
            if (this.files.length > 0) {
                const file = this.files[0];
                if (file.type.startsWith('image/')) {
                    uploadBtn.disabled = false;
                    dropZone.querySelector('.upload-placeholder').innerHTML = `
                        <i class="fas fa-file-image fa-3x"></i>
                        <p>Selected: ${file.name}</p>
                    `;
                } else {
                    alert('Please select an image file.');
                    this.value = '';
                }
            }
        });
    }

    // Upload button click handler
    if (uploadBtn) {
        uploadBtn.addEventListener("click", function(e) {
            e.preventDefault();
            if (fileInput.files.length > 0) {
                processImage(fileInput.files[0]);
            }
        });
    }

    // Reset button click handler
    if (resetBtn) {
        resetBtn.addEventListener("click", function(e) {
            e.preventDefault();
            console.log("Reset button clicked");
            // Reset file input and query input
            if (fileInput) {
                fileInput.value = '';
            }
            if (queryInput) {
                queryInput.value = '';
            }
            
            // Reset upload button
            if (uploadBtn) {
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
            }
            
            // Reset drop zone
            if (dropZone) {
                dropZone.querySelector('.upload-placeholder').innerHTML = `
                    <i class="fas fa-cloud-upload-alt fa-3x"></i>
                    <p>Drop your image here</p>
                    <p class="upload-or">or</p>
                    <button class="btn" id="browse-files-btn">Browse Files</button>
                `;
                
                // Re-attach event listener to the browse button
                const newBrowseBtn = dropZone.querySelector('#browse-files-btn');
                if (newBrowseBtn) {
                    newBrowseBtn.addEventListener("click", () => fileInput.click());
                }
            }
            
            // Clear results container
            if (resultsContainer) {
                resultsContainer.innerHTML = '';
            }
        });
    }

    // Drop zone handlers
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight(e) {
            dropZone.classList.add('highlight');
        }

        function unhighlight(e) {
            dropZone.classList.remove('highlight');
        }

        dropZone.addEventListener('drop', handleDrop, false);
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        
        if (file && file.type.startsWith('image/')) {
            fileInput.files = dt.files;
            uploadBtn.disabled = false;
            dropZone.querySelector('.upload-placeholder').innerHTML = `
                <i class="fas fa-file-image fa-3x"></i>
                <p>Selected: ${file.name}</p>
            `;
        } else {
            alert('Please drop an image file.');
        }
    }

    function processImage(file) {
        // Show loading state
        resultsContainer.innerHTML = `
            <div class="loading">
                <i class="fas fa-spinner fa-spin fa-3x"></i>
                <p>Processing image...</p>
            </div>
        `;
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

        const formData = new FormData();
        formData.append('image', file);
        
        if (queryInput && queryInput.value.trim()) {
            formData.append('query_text', queryInput.value.trim());
        }

        // Get CSRF token
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        fetch('/blog/process-image/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                // User is not authenticated
                window.location.href = '/blog/login/?next=/blog/';
                throw new Error('You need to login to use this feature');
            }
            
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            if (data.status === 'processing') {
                // Start polling for results
                pollForResults(data.job_id);
            }
        })
        .catch(error => {
            resultsContainer.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>${error.message}</p>
                </div>
            `;
            
            // Reset upload button
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
        });
    }

    function pollForResults(jobId) {
        // Set a maximum poll count to avoid infinite polling
        let pollCount = 0;
        const maxPolls = 120; // Maximum number of polling attempts (4 minutes total)
        
        // Show loading indicator
        resultsContainer.innerHTML = `
            <div class="loading-message">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Processing your image... This may take up to 2 minutes.</p>
            </div>
        `;
        
        const pollInterval = setInterval(() => {
            pollCount++;
            
            // Check if we've reached the maximum number of polls
            if (pollCount > maxPolls) {
                clearInterval(pollInterval);
                resultsContainer.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-circle"></i>
                        <p>Processing is taking longer than expected. Please try again later.</p>
                        <button id="retry-btn" class="btn primary" style="margin-top: 15px;">
                            <i class="fas fa-redo"></i> Try Again
                        </button>
                    </div>
                `;
                
                // Add event listener to the retry button
                document.getElementById('retry-btn').addEventListener('click', () => {
                    window.location.reload();
                });
                
                // Reset upload button
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
                return;
            }
            
            fetch(`/blog/check-job/${jobId}/`)
            .then(response => {
                if (!response.ok) {
                    if (response.status === 500) {
                        throw new Error('Server error. Please try again.');
                    } else if (response.status === 404) {
                        throw new Error('Job not found. It may have expired.');
                    } else {
                        throw new Error('Network response was not ok: ' + response.status);
                    }
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    displayResults(data);
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    throw new Error(data.error || 'Processing failed');
                }
                // If still processing, continue polling
            })
            .catch(error => {
                clearInterval(pollInterval);
                resultsContainer.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-circle"></i>
                        <p>${error.message}</p>
                    </div>
                `;
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
            });
        }, 2000); // Poll every 2 seconds
    }

    function displayResults(data) {
        resultsContainer.innerHTML = `
            <img src="${data.image_url}" alt="Analyzed image" class="result-image">
            
            <div class="caption-section">
                <h3>Short Caption</h3>
                <div class="caption-content">
                    ${data.short_caption || 'No caption generated'}
                </div>
            </div>

            ${data.query_result ? `
                <div class="caption-section">
                    <h3>Query Result</h3>
                    <div class="caption-content">
                        ${data.query_result}
                    </div>
                </div>
            ` : ''}
            
            <div class="upload-another-container">
                <button id="upload-another-btn" class="btn blue">Upload Again</button>
            </div>
        `;

        // Add event listener to the "Upload Again" button
        document.getElementById('upload-another-btn').addEventListener('click', function() {
            console.log("Upload Again button clicked");
            // Reset file input and query input
            if (fileInput) {
                fileInput.value = '';
            }
            if (queryInput) {
                queryInput.value = '';
            }
            
            // Reset upload button
            if (uploadBtn) {
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
            }
            
            // Reset drop zone
            if (dropZone) {
                dropZone.querySelector('.upload-placeholder').innerHTML = `
                    <i class="fas fa-cloud-upload-alt fa-3x"></i>
                    <p>Drop your image here</p>
                    <p class="upload-or">or</p>
                    <button class="btn" id="browse-files-btn">Browse Files</button>
                `;
                
                // Re-attach event listener to the browse button
                const newBrowseBtn = dropZone.querySelector('#browse-files-btn');
                if (newBrowseBtn) {
                    newBrowseBtn.addEventListener("click", () => fileInput.click());
                }
            }
            
            // Clear results container
            if (resultsContainer) {
                resultsContainer.innerHTML = '';
            }
            
            // Scroll to upload area
            dropZone.scrollIntoView({ behavior: 'smooth' });
        });

        // Reset upload button
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<span class="btn-icon">⇪</span> Upload';
        
        // Scroll to results
        resultsContainer.scrollIntoView({ behavior: 'smooth' });
    }

    // Camera functionality
    if (cameraBtn) {
        cameraBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const cameraContainer = document.createElement('div');
            cameraContainer.className = 'camera-container';
            cameraContainer.innerHTML = `
                <div class="camera-content">
                    <video autoplay class="camera-preview"></video>
                    <div class="camera-controls">
                        <button class="btn capture-btn">
                            <i class="fas fa-camera"></i> Capture
                        </button>
                        <button class="btn close-btn">
                            <i class="fas fa-times"></i> Close
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(cameraContainer);
            
            const video = cameraContainer.querySelector('video');
            const captureBtn = cameraContainer.querySelector('.capture-btn');
            const closeBtn = cameraContainer.querySelector('.close-btn');

            navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => {
                    video.srcObject = stream;
                    
                    captureBtn.addEventListener('click', () => {
                        const canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        canvas.getContext('2d').drawImage(video, 0, 0);
                        
                        canvas.toBlob(blob => {
                            const file = new File([blob], 'camera-capture.jpg', { type: 'image/jpeg' });
                            stream.getTracks().forEach(track => track.stop());
                            cameraContainer.remove();
                            
                            // Update file input and trigger upload
                            const dataTransfer = new DataTransfer();
                            dataTransfer.items.add(file);
                            fileInput.files = dataTransfer.files;
                            uploadBtn.disabled = false;
                            processImage(file);
                        }, 'image/jpeg');
                    });
                    
                    closeBtn.addEventListener('click', () => {
                        stream.getTracks().forEach(track => track.stop());
                        cameraContainer.remove();
                    });
                })
                .catch(err => {
                    alert('Camera error: ' + err.message);
                    cameraContainer.remove();
                });
        });
    }

    // Speech to text functionality
    if (speechToTextBtn) {
        let isRecording = false;
        let statusCheckInterval;

        speechToTextBtn.addEventListener("click", function() {
            if (isRecording) {
                stopSpeechRecording();
            } else {
                startSpeechRecording();
            }
        });

        function startSpeechRecording() {
            // Get CSRF token
            const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            // Update UI to show recording state
            speechToTextBtn.innerHTML = '<i class="fas fa-microphone-slash"></i>';
            speechToTextBtn.classList.add('recording');
            speechToTextBtn.title = 'Stop recording';
            isRecording = true;

            // Show a countdown timer
            const originalPlaceholder = queryInput.placeholder;
            let secondsLeft = 15;
            queryInput.placeholder = `Listening... (${secondsLeft}s)`;
            
            const countdownInterval = setInterval(() => {
                secondsLeft--;
                if (secondsLeft > 0) {
                    queryInput.placeholder = `Listening... (${secondsLeft}s)`;
                } else {
                    clearInterval(countdownInterval);
                }
            }, 1000);

            // Start the speech recognition
            fetch('/blog/speech-to-text/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ action: 'start' })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Speech recognition started:', data);
                
                // Start checking for results
                statusCheckInterval = setInterval(() => {
                    fetch('/blog/speech-to-text/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrftoken
                        },
                        body: JSON.stringify({ action: 'status' })
                    })
                    .then(response => response.json())
                    .then(statusData => {
                        if (statusData.text) {
                            queryInput.value = statusData.text;
                        }
                        
                        // If recording completed
                        if (statusData.status !== 'recording') {
                            clearInterval(statusCheckInterval);
                            resetSpeechUI(originalPlaceholder);
                            clearInterval(countdownInterval);
                        }
                    })
                    .catch(error => {
                        console.error('Error checking speech status:', error);
                        clearInterval(statusCheckInterval);
                        resetSpeechUI(originalPlaceholder);
                        clearInterval(countdownInterval);
                    });
                }, 1000);
                
                // Auto stop after 15 seconds
                setTimeout(() => {
                    if (isRecording) {
                        stopSpeechRecording();
                        clearInterval(countdownInterval);
                        resetSpeechUI(originalPlaceholder);
                    }
                }, 15000);
            })
            .catch(error => {
                console.error('Error starting speech recognition:', error);
                resetSpeechUI(originalPlaceholder);
                clearInterval(countdownInterval);
            });
        }

        function stopSpeechRecording() {
            if (!isRecording) return;
            
            // Get CSRF token
            const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            // Stop the speech recognition
            fetch('/blog/speech-to-text/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ action: 'stop' })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Speech recognition stopped:', data);
                if (data.text) {
                    queryInput.value = data.text;
                }
                resetSpeechUI();
            })
            .catch(error => {
                console.error('Error stopping speech recognition:', error);
                resetSpeechUI();
            });
        }

        function resetSpeechUI(originalPlaceholder) {
            speechToTextBtn.innerHTML = '<i class="fas fa-microphone"></i>';
            speechToTextBtn.classList.remove('recording');
            speechToTextBtn.title = 'Speak your question (15s)';
            isRecording = false;
            clearInterval(statusCheckInterval);
            
            if (originalPlaceholder) {
                queryInput.placeholder = originalPlaceholder;
            }
        }
    }
});
