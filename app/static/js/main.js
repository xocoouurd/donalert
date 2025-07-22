// Main JavaScript for DonAlert

document.addEventListener('DOMContentLoaded', function() {
    // Initialize any JavaScript functionality here
    
    // Add smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = this.getAttribute('href');
            // Only process if it's actually a hash link and target exists
            if (target && target.startsWith('#')) {
                try {
                    const targetElement = document.querySelector(target);
                    if (targetElement) {
                        e.preventDefault();
                        targetElement.scrollIntoView({
                            behavior: 'smooth'
                        });
                    }
                } catch (error) {
                    // Invalid selector
                }
            }
        });
    });
});