// Toggle Dark/Light Mode
const toggleThemeBtn = document.getElementById('toggle-theme');
const themeIcon = toggleThemeBtn.querySelector('i');

toggleThemeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    
    if (document.body.classList.contains('dark-mode')) {
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
    } else {
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
    }
});

// Calculate circle progress and handle UI interactions
document.addEventListener('DOMContentLoaded', function() {
    // Handle missing images
    const images = document.querySelectorAll('img');
    images.forEach(img => {
        img.onerror = function() {
            // If it's a logo
            if (this.alt === 'logo') {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzRDQUY1MCIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjIwIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgYWxpZ25tZW50LWJhc2VsaW5lPSJtaWRkbGUiPkltYWdlPC90ZXh0Pjwvc3ZnPg==';
            } 
            // If it's a profile/avatar image
            else if (this.alt.includes('profile') || this.alt.includes('Profile') || this.alt.includes('avatar')) {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI1MCIgZmlsbD0iIzIxOTZGMyIvPjxjaXJjbGUgY3g9IjUwIiBjeT0iMzUiIHI9IjE1IiBmaWxsPSJ3aGl0ZSIvPjxwYXRoIGQ9Ik0yNSw4NSBRNTAsNjAgNzUsODUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMTAiIGZpbGw9InRyYW5zcGFyZW50Ii8+PC9zdmc+';
            }
            // Any other image
            else {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSIjNjY2IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBhbGlnbm1lbnQtYmFzZWxpbmU9Im1pZGRsZSI+SW1hZ2U8L3RleHQ+PC9zdmc+';
            }
        };
    });

    // Update progress circles
    const updateProgressCircles = () => {
        const circles = document.querySelectorAll('.progress-circular .progress');
        
        circles.forEach(circle => {
            const radius = circle.getAttribute('r');
            const circumference = 2 * Math.PI * radius;
            
            circle.style.strokeDasharray = circumference;
            
            const parent = circle.closest('.progress-container');
            const valueText = parent.querySelector('.progress-value').textContent;
            const value = parseInt(valueText.replace('+', '').replace('%', '')) || 100;
            
            const offset = circumference - (value / 100) * circumference;
            circle.style.strokeDashoffset = offset;
        });
    };
    
    updateProgressCircles();

    // Toggle dark mode
    const toggleThemeBtn = document.getElementById('toggle-theme');
    if (toggleThemeBtn) {
        toggleThemeBtn.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
            
            // Change icon
            const icon = this.querySelector('i');
            if (icon.classList.contains('fa-moon')) {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            } else {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        });
    }
});