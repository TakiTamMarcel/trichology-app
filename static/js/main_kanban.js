// Obsługa tablicy Kanban na stronie głównej
document.addEventListener('DOMContentLoaded', function() {
    // Inicjalizacja funkcji
    initMainKanban();
    
    // Obsługa przycisków
    document.getElementById('addTaskBtn').addEventListener('click', showAddTaskModal);
    document.getElementById('addTaskForm').addEventListener('submit', function(event) {
        event.preventDefault();
        addNewTask();
    });
    
    // Obsługa zamykania modalu
    document.querySelector('.main-kanban-modal-close').addEventListener('click', hideAddTaskModal);
    
    // Obsługa checkboxa przypisania do pacjenta
    document.getElementById('assignToPatient').addEventListener('change', function() {
        const patientSelectionContainer = document.getElementById('patientSelectionContainer');
        patientSelectionContainer.style.display = this.checked ? 'block' : 'none';
    });
    
    // Wyszukiwanie pacjentów
    document.getElementById('patientSearch').addEventListener('input', function() {
        searchPatientsForTask(this.value);
    });
    
    // Zamykanie modalu po kliknięciu poza nim
    window.addEventListener('click', function(event) {
        const modal = document.getElementById('addTaskModal');
        if (event.target === modal) {
            hideAddTaskModal();
        }
    });
});

// Inicjalizacja tablicy Kanban
function initMainKanban() {
    // Wczytanie zadań z localStorage
    const savedTasks = localStorage.getItem('mainKanbanTasks');
    
    if (savedTasks) {
        try {
            const tasks = JSON.parse(savedTasks);
            
            // Tworzenie kart zadań
            tasks.forEach(task => {
                createTaskCard(
                    task.id,
                    task.status,
                    task.title,
                    task.description,
                    task.patient
                );
            });
        } catch (error) {
            console.error('Error restoring Kanban tasks:', error);
        }
    }
}

// Przenoszenie zadania między kolumnami
function moveTask(taskId, newStatus) {
    const taskCard = document.getElementById(taskId);
    if (!taskCard) return;
    
    // Pobierz aktualny status
    const currentStatus = taskCard.dataset.status;
    
    // Nie rób nic, jeśli próbujemy przenieść do tej samej kolumny
    if (currentStatus === newStatus) return;
    
    // Usuń z aktualnej kolumny
    taskCard.remove();
    
    // Dodaj do nowej kolumny
    const newColumn = document.getElementById(`${newStatus}-column`);
    newColumn.appendChild(taskCard);
    
    // Aktualizuj status w danych
    taskCard.dataset.status = newStatus;
    
    // Aktualizuj przyciski
    updateTaskMoveButtons(taskCard);
    
    // Zapisz stan tablicy Kanban
    saveMainKanbanState();
}

// Aktualizacja przycisków w zależności od kolumny
function updateTaskMoveButtons(taskCard) {
    const buttonsContainer = taskCard.querySelector('.main-kanban-move-buttons');
    buttonsContainer.innerHTML = '';
    
    const taskId = taskCard.id;
    const status = taskCard.dataset.status;
    
    // Dodaj przycisk usuwania, który będzie dostępny dla każdego statusu
    const deleteButton = document.createElement('button');
    deleteButton.className = 'main-kanban-delete-button';
    deleteButton.innerHTML = '<i class="fas fa-trash"></i> Usuń';
    deleteButton.title = 'Usuń zadanie';
    deleteButton.onclick = function(e) {
        e.stopPropagation(); // Zapobiega wyzwoleniu innych zdarzeń
        deleteTask(taskId);
    };
    buttonsContainer.appendChild(deleteButton);
    
    if (status === 'todo') {
        const progressButton = document.createElement('button');
        progressButton.className = 'main-kanban-move-button';
        progressButton.textContent = '→ W trakcie';
        progressButton.onclick = function(event) {
            event.stopPropagation();
            moveTask(taskId, 'in-progress');
        };
        buttonsContainer.appendChild(progressButton);
    } else if (status === 'in-progress') {
        const doneButton = document.createElement('button');
        doneButton.className = 'main-kanban-move-button';
        doneButton.textContent = '→ Zakończone';
        doneButton.onclick = function(event) {
            event.stopPropagation();
            moveTask(taskId, 'done');
        };
        
        const backButton = document.createElement('button');
        backButton.className = 'main-kanban-move-button';
        backButton.textContent = '← Do zrobienia';
        backButton.onclick = function(event) {
            event.stopPropagation();
            moveTask(taskId, 'todo');
        };
        
        buttonsContainer.appendChild(backButton);
        buttonsContainer.appendChild(doneButton);
    } else if (status === 'done') {
        const restartButton = document.createElement('button');
        restartButton.className = 'main-kanban-move-button';
        restartButton.textContent = '← Do zrobienia';
        restartButton.onclick = function(event) {
            event.stopPropagation();
            moveTask(taskId, 'todo');
        };
        buttonsContainer.appendChild(restartButton);
    }
}

// Tworzenie karty zadania
function createTaskCard(id, status, title, description, patient) {
    const card = document.createElement('div');
    card.id = id;
    card.className = 'main-kanban-card';
    card.dataset.status = status;
    card.dataset.title = title;
    card.dataset.description = description;
    
    if (patient) {
        card.dataset.patientPesel = patient.pesel;
        card.dataset.patientName = `${patient.firstName} ${patient.lastName}`;
    }
    
    // Utwórz treść karty
    let cardHtml = `
        <div class="main-kanban-card-title">
            ${title}
        </div>
        <div class="main-kanban-card-info">
            <p>${description}</p>
        </div>`;
    
    // Dodaj informację o pacjencie, jeśli jest przypisany
    if (patient) {
        cardHtml += `
        <div class="main-kanban-patient-info">
            <a href="/patient/${patient.pesel}" onclick="event.stopPropagation()">
                Pacjent: ${patient.firstName} ${patient.lastName} (${patient.pesel})
            </a>
        </div>`;
    }
    
    cardHtml += `<div class="main-kanban-move-buttons"></div>`;
    
    card.innerHTML = cardHtml;
    
    // Dodaj kartę do odpowiedniej kolumny
    const column = document.getElementById(`${status}-column`);
    if (column) {
        column.appendChild(card);
        
        // Aktualizuj przyciski
        updateTaskMoveButtons(card);
    }
    
    return card;
}

// Funkcje dla modalu dodawania zadań
function showAddTaskModal() {
    document.getElementById('addTaskModal').style.display = 'block';
    
    // Resetuj formularz
    document.getElementById('addTaskForm').reset();
    document.getElementById('patientSelectionContainer').style.display = 'none';
    document.getElementById('patientsList').innerHTML = '';
}

function hideAddTaskModal() {
    document.getElementById('addTaskModal').style.display = 'none';
}

// Wyszukiwanie pacjentów dla zadania
function searchPatientsForTask(query) {
    fetch('/api/search-patients', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayPatientsForTask(data.patients);
        } else {
            console.error('Error:', data.error);
        }
    })
    .catch(error => console.error('Error:', error));
}

// Wyświetlanie listy pacjentów
function displayPatientsForTask(patients) {
    const patientsList = document.getElementById('patientsList');
    patientsList.innerHTML = '';
    
    if (patients.length === 0) {
        patientsList.innerHTML = '<p>Brak pacjentów do wyświetlenia</p>';
        return;
    }
    
    patients.forEach(patient => {
        const patientItem = document.createElement('div');
        patientItem.style.padding = '8px';
        patientItem.style.marginBottom = '5px';
        patientItem.style.backgroundColor = '#f8f8f8';
        patientItem.style.borderRadius = '4px';
        patientItem.style.cursor = 'pointer';
        
        patientItem.innerHTML = `
            <input type="radio" name="patientSelection" id="patient-${patient.pesel}" 
                   value="${patient.pesel}" data-first-name="${patient.first_name}" data-last-name="${patient.last_name}">
            <label for="patient-${patient.pesel}">
                ${patient.last_name} ${patient.first_name} (${patient.pesel})
            </label>
        `;
        
        patientsList.appendChild(patientItem);
    });
}

// Dodawanie nowego zadania
function addNewTask() {
    const title = document.getElementById('taskTitle').value;
    const description = document.getElementById('taskDescription').value;
    const assignToPatient = document.getElementById('assignToPatient').checked;
    
    if (!title) {
        alert('Podaj tytuł zadania');
        return;
    }
    
    // Generuj unikalne ID dla nowego zadania
    const taskId = 'task-' + Date.now();
    
    // Sprawdź, czy zadanie jest przypisane do pacjenta
    let patient = null;
    if (assignToPatient) {
        const selectedPatient = document.querySelector('input[name="patientSelection"]:checked');
        if (selectedPatient) {
            patient = {
                pesel: selectedPatient.value,
                firstName: selectedPatient.dataset.firstName,
                lastName: selectedPatient.dataset.lastName
            };
        } else {
            alert('Wybierz pacjenta z listy');
            return;
        }
    }
    
    // Utwórz nową kartę zadania
    createTaskCard(taskId, 'todo', title, description, patient);
    
    // Zapisz stan tablicy Kanban
    saveMainKanbanState();
    
    // Zamknij modal
    hideAddTaskModal();
}

// Zapisywanie stanu tablicy Kanban
function saveMainKanbanState() {
    const allCards = document.querySelectorAll('.main-kanban-card');
    const tasksState = Array.from(allCards).map(card => {
        const task = {
            id: card.id,
            status: card.dataset.status,
            title: card.dataset.title,
            description: card.dataset.description
        };
        
        if (card.dataset.patientPesel) {
            task.patient = {
                pesel: card.dataset.patientPesel,
                firstName: card.dataset.patientName.split(' ')[0],
                lastName: card.dataset.patientName.split(' ')[1]
            };
        }
        
        return task;
    });
    
    localStorage.setItem('mainKanbanTasks', JSON.stringify(tasksState));
}

// Funkcja do usuwania zadania
function deleteTask(taskId) {
    if (confirm('Czy na pewno chcesz usunąć to zadanie?')) {
        const taskCard = document.getElementById(taskId);
        if (taskCard) {
            // Usuń kartę z DOM
            taskCard.remove();
            
            // Zaktualizuj stan tablicy Kanban w localStorage
            saveMainKanbanState();
        }
    }
} 