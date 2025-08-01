// Photo Editor JavaScript
// Podstawowe funkcje do obsługi zdjęć

function initPhotoEditor() {
    console.log('Photo editor initialized');
}

// Funkcje wykorzystywane w innych miejscach aplikacji
function showPhotoPreview(element) {
    if (element && element.style) {
        element.style.display = 'block';
    }
}

function hidePhotoPreview(element) {
    if (element && element.style) {
        element.style.display = 'none';
    }
}

// Inicjalizacja po załadowaniu DOM
document.addEventListener('DOMContentLoaded', function() {
    initPhotoEditor();
}); 