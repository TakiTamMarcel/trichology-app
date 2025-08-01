// Main JavaScript file for the Trichology App

// Wait for DOM to be loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Handle navbar active state
    const currentUrl = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        if (currentUrl === linkPath || (linkPath !== '/' && currentUrl.startsWith(linkPath))) {
            link.classList.add('active');
        }
    });
    
    // Add any other common initialization code here
}); 