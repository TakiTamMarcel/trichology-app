// Debug: sprawdzenie czy plik się ładuje
console.log('🚀 Documentation form JavaScript loaded!');

// Inicjalizacja danych pacjenta
let patientData = null;
const patientDataElement = document.getElementById('patient-data');
if (patientDataElement) {
    try {
        patientData = JSON.parse(patientDataElement.textContent);
        console.log('Załadowano dane pacjenta:', patientData);
    } catch (error) {
        console.error('Błąd podczas parsowania danych pacjenta:', error);
    }
}

// Funkcja do wyciągania daty urodzenia z PESEL
function extractBirthDateFromPESEL(pesel) {
    if (!pesel || pesel.length !== 11) {
        return null;
    }
    
    const year = parseInt(pesel.substring(0, 2));
    const month = parseInt(pesel.substring(2, 4));
    const day = parseInt(pesel.substring(4, 6));
    
    let fullYear;
    if (month >= 1 && month <= 12) {
        // XX wiek (1900-1999)
        fullYear = 1900 + year;
    } else if (month >= 21 && month <= 32) {
        // XXI wiek (2000-2099)
        fullYear = 2000 + year;
    } else if (month >= 41 && month <= 52) {
        // XXII wiek (2100-2199)
        fullYear = 2100 + year;
    } else if (month >= 61 && month <= 72) {
        // XVIII wiek (1800-1899)
        fullYear = 1800 + year;
    } else if (month >= 81 && month <= 92) {
        // XVII wiek (1700-1799)
        fullYear = 1700 + year;
    } else {
        return null;
    }
    
    const realMonth = month > 12 ? month - 20 : month;
    if (realMonth < 1 || realMonth > 12 || day < 1 || day > 31) {
        return null;
    }
    
    const birthDate = new Date(fullYear, realMonth - 1, day);
    return birthDate.toISOString().split('T')[0]; // Format YYYY-MM-DD
}

// Obsługa automatycznego wypełniania daty urodzenia z PESEL
document.addEventListener('DOMContentLoaded', function() {
    const peselField = document.getElementById('pesel');
    const birthDateField = document.getElementById('birth_date');
    
    if (peselField && birthDateField) {
        peselField.addEventListener('input', function() {
            const pesel = this.value.replace(/\D/g, ''); // Usuń wszystkie nie-cyfry
            this.value = pesel; // Aktualizuj pole tylko cyframi
            
            if (pesel.length === 11) {
                const birthDate = extractBirthDateFromPESEL(pesel);
                if (birthDate) {
                    birthDateField.value = birthDate;
                    console.log('Automatycznie wypełniono datę urodzenia:', birthDate);
                }
            }
        });
    }
});

// Obsługa wyboru gęstości włosów
document.querySelectorAll('.density-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('.density-item').forEach(i => i.classList.remove('selected'));
        this.classList.add('selected');
        document.getElementById('hair_density').value = this.dataset.value;
    });
});

// Obsługa wyboru grubości włosów
document.querySelectorAll('.thickness-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('.thickness-item').forEach(i => i.classList.remove('selected'));
        this.classList.add('selected');
        document.getElementById('hair_thickness').value = this.dataset.value;
    });
});

// Obsługa wyboru stanu skóry głowy (wielokrotny wybór)
document.querySelectorAll('.condition-item').forEach(item => {
    item.addEventListener('click', function() {
        this.classList.toggle('selected');
        updateSkinConditionValue();
    });
});

function updateSkinConditionValue() {
    const selectedConditions = Array.from(document.querySelectorAll('.condition-item.selected'))
        .map(item => item.dataset.value);
    // Zapisz jako tablicę JSON, nie jako string z przecinkami
    document.getElementById('skin_condition').value = JSON.stringify(selectedConditions);
    console.log('Zaktualizowano skin_condition:', document.getElementById('skin_condition').value);
}

// Funkcje do dodawania nowych elementów
function addMedication() {
    const container = document.getElementById('medications-container');
    const medicationItem = document.createElement('div');
    medicationItem.className = 'medication-item';
    medicationItem.innerHTML = `
        <div class="grid-2">
            <div>
                <label>Nazwa leku</label>
                <input type="text" name="medication_name[]" placeholder="np. Metformina">
            </div>
            <div>
                <label>Dawka</label>
                <input type="text" name="medication_dose[]" placeholder="np. 500mg">
            </div>
        </div>
        <textarea name="medication_schedule[]" placeholder="Harmonogram przyjmowania" style="margin-top: 10px;"></textarea>
        <button type="button" class="remove-button" onclick="this.parentNode.remove()">Usuń</button>
    `;
    container.appendChild(medicationItem);
    console.log("Dodano nowy element leku");
}

function addSupplement() {
    const container = document.getElementById('supplements-container');
    const supplementItem = document.createElement('div');
    supplementItem.className = 'supplement-item';
    supplementItem.innerHTML = `
        <div class="grid-2">
            <div>
                <label>Nazwa suplementu</label>
                <input type="text" name="supplement_name[]" placeholder="np. Witamina D">
            </div>
            <div>
                <label>Dawka</label>
                <input type="text" name="supplement_dose[]" placeholder="np. 2000 IU">
            </div>
        </div>
        <textarea name="supplement_schedule[]" placeholder="Harmonogram przyjmowania" style="margin-top: 10px;"></textarea>
        <button type="button" class="remove-button" onclick="this.parentNode.remove()">Usuń</button>
    `;
    container.appendChild(supplementItem);
    console.log("Dodano nowy element suplementu");
}

function addTreatment() {
    const container = document.getElementById('treatments-container');
    const count = container.children.length + 1;
    const newItem = document.createElement('div');
    newItem.className = 'treatment-item';
    newItem.innerHTML = `
        <div class="grid-2">
            <div>
                <label for="treatment_type_${count}">Rodzaj leczenia</label>
                <input type="text" id="treatment_type_${count}" name="treatment_type[]" placeholder="np. Minoksydyl">
            </div>
            <div>
                <label for="treatment_duration_${count}">Czas trwania</label>
                <input type="text" id="treatment_duration_${count}" name="treatment_duration[]" placeholder="np. 3 miesiące">
            </div>
        </div>
        <textarea name="treatment_details[]" placeholder="Dodatkowe informacje o leczeniu" style="margin-top: 10px;"></textarea>
        <button type="button" class="remove-button" onclick="removeItem(this)">Usuń</button>
    `;
    container.appendChild(newItem);
}

function addCareProduct() {
    const container = document.getElementById('care-products-container');
    const count = container.children.length + 1;
    const newItem = document.createElement('div');
    newItem.className = 'care-product-item';
    newItem.innerHTML = `
        <div class="grid-2">
            <div>
                <label for="care_product_type_${count}">Typ produktu</label>
                <select id="care_product_type_${count}" name="care_product_type[]" onchange="updateProductOptions(this)">
                    <option value="">Wybierz typ...</option>
                    <option value="shampoo">Szampon</option>
                    <option value="peeling">Peeling</option>
                    <option value="serum">Wcierka</option>
                    <option value="medication">Lek</option>
                    <option value="supplement">Suplement</option>
                </select>
            </div>
            <div>
                <label for="care_product_name_${count}">Nazwa produktu</label>
                <input type="text" id="care_product_name_${count}" name="care_product_name[]" placeholder="np. Nizoral" onchange="updateScheduleOptions()" oninput="updateScheduleOptions()">
            </div>
        </div>
        <div class="grid-2" style="margin-top: 10px;">
            <div id="dose_container_${count}">
                <label for="care_product_dose_${count}">Dawka</label>
                <input type="text" id="care_product_dose_${count}" name="care_product_dose[]" placeholder="np. 2 razy w tygodniu" onchange="updateScheduleOptions()" oninput="updateScheduleOptions()">
            </div>
            <div>
                <label for="care_product_frequency_${count}">Częstotliwość</label>
                <select id="care_product_frequency_${count}" name="care_product_frequency[]" onchange="updateScheduleOptions()">
                    <option value="daily">Codziennie</option>
                    <option value="twice_daily">2 razy dziennie</option>
                    <option value="weekly">Raz w tygodniu</option>
                    <option value="biweekly">Co 2 tygodnie</option>
                    <option value="monthly">Co miesiąc</option>
                </select>
            </div>
        </div>
        <button type="button" class="remove-button" onclick="removeItem(this)">Usuń</button>
    `;
    container.appendChild(newItem);
}

function addCareProcedure() {
    const container = document.getElementById('care-procedures-container');
    const count = container.children.length + 1;
    const newItem = document.createElement('div');
    newItem.className = 'care-procedure-item';
    newItem.innerHTML = `
        <div class="grid-2">
            <div>
                <label for="care_procedure_type_${count}">Typ zabiegu</label>
                <select id="care_procedure_type_${count}" name="care_procedure_type[]">
                    <option value="">Wybierz zabieg...</option>
                    <option value="mesotherapy">Mezoterapia</option>
                    <option value="infusion">Infuzja</option>
                    <option value="peeling">Peeling</option>
                    <option value="carboxy">Carboxy</option>
                </select>
            </div>
            <div>
                <label for="care_procedure_frequency_${count}">Częstotliwość</label>
                <select id="care_procedure_frequency_${count}" name="care_procedure_frequency[]">
                    <option value="weekly">Raz w tygodniu</option>
                    <option value="biweekly">Co 2 tygodnie</option>
                    <option value="monthly">Raz w miesiącu</option>
                </select>
            </div>
        </div>
        <textarea id="care_procedure_details_${count}" name="care_procedure_details[]" placeholder="Szczegóły zabiegu (np. rodzaj mezoterapii)" style="margin-top: 10px;"></textarea>
        <button type="button" class="remove-button" onclick="removeItem(this)">Usuń</button>
    `;
    container.appendChild(newItem);
}

function removeItem(button) {
    const item = button.closest('.shampoo-item');
    if (item) {
        item.remove();
    }
}

function updateProductOptions(selectElement) {
    const productType = selectElement.value;
    const productNameInput = selectElement.closest('.grid-2').nextElementSibling.querySelector('input[name="care_product_name[]"]');
    const doseContainerId = `dose_container_${selectElement.id.split('_').pop()}`;
    const doseContainer = document.getElementById(doseContainerId);
    const doseInput = doseContainer ? doseContainer.querySelector('input[name="care_product_dose[]"]') : null;
    
    console.log(`Product Type: ${productType}`);
    console.log(`Dose Container ID: ${doseContainerId}`);
    console.log(`Dose Container:`, doseContainer);
    console.log(`Dose Input:`, doseInput);
    
    // Wyczyść poprzednie opcje
    if (productNameInput) {
        productNameInput.value = '';
    }
    
    // Pokaż/ukryj pole dawki w zależności od typu produktu
    if (doseContainer) {
        if (productType === 'medication' || productType === 'supplement') {
            doseContainer.style.display = 'block';
            if (doseInput) {
                doseInput.value = ''; // Wyczyść wartość dawki
            }
        } else {
            doseContainer.style.display = 'none';
            if (doseInput) {
                doseInput.value = ''; // Wyczyść wartość dawki
            }
        }
    }
    
    // Pobierz odpowiednie produkty z formularza
    let products = [];
    switch(productType) {
        case 'shampoo':
            products = Array.from(document.querySelectorAll('input[name="shampoo_brand"]')).map(input => input.value).filter(Boolean);
            break;
        case 'peeling':
            products = Array.from(document.querySelectorAll('input[name="peeling_type"]')).map(input => input.value).filter(Boolean);
            break;
        case 'medication':
            products = Array.from(document.querySelectorAll('input[name="medication_name[]"]')).map(input => input.value).filter(Boolean);
            break;
        case 'supplement':
            products = Array.from(document.querySelectorAll('input[name="supplement_name[]"]')).map(input => input.value).filter(Boolean);
            break;
    }
}

function collectScheduleData() {
    const schedule = {
        monday: { morning: [], evening: [], notes: "" },
        tuesday: { morning: [], evening: [], notes: "" },
        wednesday: { morning: [], evening: [], notes: "" },
        thursday: { morning: [], evening: [], notes: "" },
        friday: { morning: [], evening: [], notes: "" },
        saturday: { morning: [], evening: [], notes: "" },
        sunday: { morning: [], evening: [], notes: "" }
    };
    
    // Mapowanie z polskich nazw dni na klucze
    const dayMap = {
        "Poniedziałek": "monday",
        "Wtorek": "tuesday",
        "Środa": "wednesday",
        "Czwartek": "thursday",
        "Piątek": "friday",
        "Sobota": "saturday",
        "Niedziela": "sunday"
    };
    
    // Pobierz wszystkie wiersze harmonogramu
    const rows = document.querySelectorAll('.schedule-table tbody tr');
    
    // Dla każdego wiersza, zbierz dane produktów z komórek poranka i wieczora
    rows.forEach(row => {
        // Pobierz dzień tygodnia (pierwszy element wiersza)
        const dayName = row.cells[0].textContent;
        const dayKey = dayMap[dayName];
        
        if (!dayKey) {
            console.warn(`Nie znaleziono klucza dla dnia: ${dayName}`);
            return;
        }
        
        // Pobierz notatki dla tego dnia
        const notes = row.querySelector(`textarea[name="schedule_${dayKey}_notes"]`).value;
        schedule[dayKey].notes = notes;
        
        // Poranek (morning) - indeks komórki 1
        const morningSlot = row.cells[1].querySelector('.schedule-slot');
        if (morningSlot) {
            const products = morningSlot.querySelectorAll('.scheduled-product');
            products.forEach(product => {
                schedule[dayKey].morning.push({
                    type: product.dataset.productType,
                    name: product.dataset.productName,
                    dose: product.dataset.productDose,
                    frequency: product.dataset.productFrequency
                });
            });
        }
        
        // Wieczór (evening) - indeks komórki 2
        const eveningSlot = row.cells[2].querySelector('.schedule-slot');
        if (eveningSlot) {
            const products = eveningSlot.querySelectorAll('.scheduled-product');
            products.forEach(product => {
                schedule[dayKey].evening.push({
                    type: product.dataset.productType,
                    name: product.dataset.productName,
                    dose: product.dataset.productDose,
                    frequency: product.dataset.productFrequency
                });
            });
        }
    });
    
    console.log('Zebrane dane harmonogramu:', schedule);
    return schedule;
}

async function savePatient(event) {
    event.preventDefault();
    
    console.log('=== Rozpoczynam zapisywanie pacjenta ===');
    
    const form = document.getElementById('patientForm');
    if (!form) {
        console.error('Nie znaleziono formularza!');
        return;
    }
    
    console.log('Formularz znaleziony, zbieram dane...');
    
    const formData = new FormData(form);
    
    // Debugowanie pobierania pól tablicowych
    console.log('=== Debugowanie pól tablicowych przed konwersją ===');
    const medicationNameFields = form.querySelectorAll('input[name="medication_name[]"]');
    console.log(`Znaleziono ${medicationNameFields.length} pól medication_name[]`);
    medicationNameFields.forEach((field, index) => {
        console.log(`medication_name[${index}]: ${field.value}`);
    });
    
    const supplementNameFields = form.querySelectorAll('input[name="supplement_name[]"]');
    console.log(`Znaleziono ${supplementNameFields.length} pól supplement_name[]`);
    supplementNameFields.forEach((field, index) => {
        console.log(`supplement_name[${index}]: ${field.value}`);
    });
    
    // Zbieram wszystkie wartości z formularza do obiektu data
    const data = {};
    
    // Przetwarzanie pól checkboxów
    const checkboxGroupFields = ['styling', 'problem_description', 'problem_periodicity', 'previous_procedures'];
    
    checkboxGroupFields.forEach(fieldName => {
        const checkedBoxes = document.querySelectorAll(`input[name="${fieldName}"]:checked`);
        data[fieldName] = Array.from(checkedBoxes).map(cb => cb.value);
        console.log(`Zebrane dane dla ${fieldName}:`, data[fieldName]);
    });
    
    // Upewnij się, że skin_condition jest poprawną tablicą JSON
    if (document.getElementById('skin_condition')) {
        try {
            const skinConditionValue = document.getElementById('skin_condition').value;
            
            // Poprawka dla skin_condition
            let parsedValue;
            try {
                parsedValue = JSON.parse(skinConditionValue);
            } catch (e) {
                console.warn('Błąd parsowania skin_condition, używamy wartości surowej:', skinConditionValue);
                parsedValue = skinConditionValue;
            }
            
            // Jeśli to nie jest tablica, zamień na tablicę
            if (!Array.isArray(parsedValue)) {
                parsedValue = [parsedValue].filter(Boolean);
            }
            
            data.skin_condition = parsedValue;
            console.log('Przygotowane skin_condition:', data.skin_condition);
        } catch (error) {
            console.error('Błąd podczas przetwarzania skin_condition:', error);
            data.skin_condition = [];
        }
    }
    
    // Dodaj peeling_type i peeling_frequency
    data.peeling_type = document.getElementById('peeling_type').value;
    data.peeling_frequency = document.getElementById('peeling_frequency').value;
    console.log('Peeling type:', data.peeling_type);
    console.log('Peeling frequency:', data.peeling_frequency);

    // Dodaj dane o farbowaniu włosów
    data.coloring_type = document.getElementById('coloring_type')?.value || '';
    data.coloring_frequency = document.getElementById('coloring_frequency')?.value || '';
    console.log('Coloring type:', data.coloring_type);
    console.log('Coloring frequency:', data.coloring_frequency);

    // Upewnij się, że dane o leczeniu i zabiegach są poprawnie zebrane
    const treatmentTypes = [];
    const treatmentDurations = [];
    const treatmentDetails = [];

    document.querySelectorAll('input[name="treatment_type[]"]').forEach(input => {
        treatmentTypes.push(input.value);
    });
    document.querySelectorAll('input[name="treatment_duration[]"]').forEach(input => {
        treatmentDurations.push(input.value);
    });
    document.querySelectorAll('textarea[name="treatment_details[]"]').forEach(textarea => {
        treatmentDetails.push(textarea.value);
    });

    data.treatment_type = treatmentTypes;
    data.treatment_duration = treatmentDurations;
    data.treatment_details = treatmentDetails;
    console.log('Treatment types:', data.treatment_type);
    console.log('Treatment durations:', data.treatment_duration);

    // Zbierz dane o zabiegach
    const careProcedureTypes = [];
    const careProcedureFrequencies = [];
    const careProcedureDetails = [];

    document.querySelectorAll('select[name="care_procedure_type[]"]').forEach(select => {
        careProcedureTypes.push(select.value);
    });
    document.querySelectorAll('select[name="care_procedure_frequency[]"]').forEach(select => {
        careProcedureFrequencies.push(select.value);
    });
    document.querySelectorAll('textarea[name="care_procedure_details[]"]').forEach(textarea => {
        careProcedureDetails.push(textarea.value);
    });

    data.care_procedure_type = careProcedureTypes;
    data.care_procedure_frequency = careProcedureFrequencies;
    data.care_procedure_details = careProcedureDetails;
    console.log('Care procedure types:', data.care_procedure_type);
    console.log('Care procedure frequencies:', data.care_procedure_frequency);

    // Dodaj zebrane dane leków i suplementów
    data.medication_name = Array.from(form.querySelectorAll('input[name="medication_name[]"]')).map(input => input.value);
    data.medication_dose = Array.from(form.querySelectorAll('input[name="medication_dose[]"]')).map(input => input.value);
    data.medication_schedule = Array.from(form.querySelectorAll('textarea[name="medication_schedule[]"]')).map(textarea => textarea.value);

    data.supplement_name = Array.from(form.querySelectorAll('input[name="supplement_name[]"]')).map(input => input.value);
    data.supplement_dose = Array.from(form.querySelectorAll('input[name="supplement_dose[]"]')).map(input => input.value);
    data.supplement_schedule = Array.from(form.querySelectorAll('textarea[name="supplement_schedule[]"]')).map(textarea => textarea.value);

    // Dodaj zebrane dane szamponów
    data.shampoo_type = Array.from(form.querySelectorAll('select[name="shampoo_type[]"]')).map(select => select.value);
    data.shampoo_brand = Array.from(form.querySelectorAll('input[name="shampoo_brand[]"]')).map(input => input.value);
    data.shampoo_details = Array.from(form.querySelectorAll('textarea[name="shampoo_details[]"]')).map(textarea => textarea.value);
    
    // Zbierz dane harmonogramu tygodniowego
    data.schedule = collectScheduleData();
    
    // Sprawdzenie wymaganych pól
    const requiredFields = ['first_name', 'last_name', 'pesel'];
    const missingFields = requiredFields.filter(field => !data[field]);
    if (missingFields.length > 0) {
        console.error('Brakujące wymagane pola:', missingFields);
        alert('Proszę wypełnić wszystkie wymagane pola: ' + missingFields.join(', '));
        return;
    }
    
    console.log('Dane formularza po konwersji:', data);
    
    try {
        console.log('Wysyłam żądanie do /api/save-patient...');
        console.log('Body żądania:', JSON.stringify(data, null, 2));
        
        // Check specifically for peeling_type and peeling_frequency
        console.log('DEBUG - peeling_type:', data.peeling_type, typeof data.peeling_type);
        console.log('DEBUG - peeling_frequency:', data.peeling_frequency, typeof data.peeling_frequency);
        
        // Check for any null or undefined values
        const nullFields = [];
        for (const [key, value] of Object.entries(data)) {
            if (value === null || value === undefined) {
                nullFields.push(key);
                console.warn(`Field ${key} has null/undefined value`);
            }
        }
        if (nullFields.length > 0) {
            console.warn('Found null/undefined fields:', nullFields);
        }
        
        const response = await fetch('/api/save-patient', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        console.log('Status odpowiedzi:', response.status);
        console.log('Status text:', response.statusText);
        
        // Try to get the detailed error message
        try {
            const result = await response.json();
            console.log('Wynik zapisu:', result);
            
            if (result.success) {
                console.log('Zapis udany, przekierowuję do:', `/patient/${data.pesel}`);
                window.location.href = `/patient/${data.pesel}`;
            } else {
                console.error('Błąd podczas zapisu:', result.error);
                alert('Wystąpił błąd podczas zapisywania danych pacjenta: ' + result.error);
            }
        } catch (jsonError) {
            console.error('Błąd podczas parsowania odpowiedzi JSON:', jsonError);
            const text = await response.text();
            console.error('Surowa odpowiedź:', text);
            alert('Wystąpił błąd podczas zapisywania danych pacjenta (błąd parsowania odpowiedzi)');
        }
    } catch (error) {
        console.error('Błąd podczas zapisywania:', error);
        console.error('Szczegóły błędu:', error.stack);
        alert('Wystąpił błąd podczas zapisywania danych pacjenta');
    }
}

function drop(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('dragover');
    
    const data = JSON.parse(ev.dataTransfer.getData("text"));
    const slot = ev.currentTarget;
    
    // Sprawdź czy produkt już istnieje w tym slocie
    const existingProducts = slot.querySelectorAll('.scheduled-product');
    const productExists = Array.from(existingProducts).some(el => 
        el.dataset.productName === data.name && 
        el.dataset.productDose === data.dose
    );

    if (productExists) {
        return; // Jeśli produkt już istnieje w tym slocie, nie dodawaj go ponownie
    }
    
    // Create scheduled product element
    const productElement = document.createElement('div');
    productElement.className = 'scheduled-product';
    productElement.dataset.productType = data.type;
    productElement.dataset.productName = data.name;
    productElement.dataset.productDose = data.dose;
    productElement.dataset.productFrequency = data.frequency;
    
    const displayText = data.dose ? `${data.name} (${data.dose})` : data.name;
    productElement.innerHTML = `
        ${displayText}
        <span class="remove-product" onclick="removeScheduledProduct(this)">×</span>
    `;
    
    productElement.draggable = true;
    productElement.addEventListener('dragstart', dragScheduledProduct);
    
    slot.appendChild(productElement);

    // Jeśli produkt jest przesuwany z innego slotu (nie z puli dostępnych produktów)
    if (data.sourceId.startsWith('scheduled-')) {
        // Jeśli nie jest wciśnięty Shift, usuń oryginalny element
        if (!ev.shiftKey) {
            const sourceElement = document.getElementById(data.sourceId);
            if (sourceElement) {
                sourceElement.remove();
            }
        }
    } else {
        // Jeśli produkt jest z puli dostępnych produktów, usuń go tylko jeśli jest wciśnięty Shift
        if (ev.shiftKey) {
            const sourceElement = document.getElementById(data.sourceId);
            if (sourceElement && sourceElement.classList.contains('product-item')) {
                sourceElement.remove();
            }
        }
    }
}

function renderScheduleData() {
    console.log('Renderowanie danych harmonogramu tygodniowego...');
    
    // Sprawdź szczegóły patientData
    console.log('patientData:', patientData);
    
    // Sprawdź, czy dane harmonogramu są dostępne
    if (typeof patientData === 'undefined' || !patientData.schedule) {
        console.log('Brak danych harmonogramu do renderowania lub patientData.schedule jest undefined/null');
        console.log('Typ patientData:', typeof patientData);
        if (patientData) {
            console.log('Klucze patientData:', Object.keys(patientData));
        }
        return;
    }
    
    console.log('Dane harmonogramu do renderowania:', patientData.schedule);
    
    // Mapowanie polskich nazw dni tygodnia na angielskie klucze
    const dayMapping = {
        'monday': 'Poniedziałek',
        'tuesday': 'Wtorek',
        'wednesday': 'Środa',
        'thursday': 'Czwartek',
        'friday': 'Piątek',
        'saturday': 'Sobota',
        'sunday': 'Niedziela'
    };
    
    // Ustaw notatki dla każdego dnia
    for (const day in patientData.schedule) {
        const dayData = patientData.schedule[day];
        const textarea = document.querySelector(`textarea[name="schedule_${day}_notes"]`);
        if (textarea && dayData.notes) {
            textarea.value = dayData.notes;
        }
        
        // Znajdź wiersz dla danego dnia
        const dayName = dayMapping[day];
        const row = Array.from(document.querySelectorAll('.schedule-table tbody tr')).find(
            tr => tr.cells[0].textContent === dayName
        );
        
        if (!row) continue;
        
        // Dodaj produkty poranne
        if (dayData.morning && dayData.morning.length > 0) {
            const morningSlot = row.cells[1].querySelector('.schedule-slot');
            if (morningSlot) {
                dayData.morning.forEach(product => {
                    const displayText = product.dose ? `${product.name} (${product.dose})` : product.name;
                    
                    const productElement = document.createElement('div');
                    productElement.className = 'scheduled-product';
                    productElement.dataset.productType = product.type;
                    productElement.dataset.productName = product.name;
                    productElement.dataset.productDose = product.dose || '';
                    productElement.dataset.productFrequency = product.frequency || '';
                    
                    productElement.innerHTML = `
                        ${displayText}
                        <span class="remove-product" onclick="removeScheduledProduct(this)">×</span>
                    `;
                    
                    productElement.draggable = true;
                    productElement.addEventListener('dragstart', dragScheduledProduct);
                    
                    morningSlot.appendChild(productElement);
                });
            }
        }
        
        // Dodaj produkty wieczorne
        if (dayData.evening && dayData.evening.length > 0) {
            const eveningSlot = row.cells[2].querySelector('.schedule-slot');
            if (eveningSlot) {
                dayData.evening.forEach(product => {
                    const displayText = product.dose ? `${product.name} (${product.dose})` : product.name;
                    
                    const productElement = document.createElement('div');
                    productElement.className = 'scheduled-product';
                    productElement.dataset.productType = product.type;
                    productElement.dataset.productName = product.name;
                    productElement.dataset.productDose = product.dose || '';
                    productElement.dataset.productFrequency = product.frequency || '';
                    
                    productElement.innerHTML = `
                        ${displayText}
                        <span class="remove-product" onclick="removeScheduledProduct(this)">×</span>
                    `;
                    
                    productElement.draggable = true;
                    productElement.addEventListener('dragstart', dragScheduledProduct);
                    
                    eveningSlot.appendChild(productElement);
                });
            }
        }
    }
    
    console.log('Renderowanie harmonogramu zakończone');
}

// Dodawanie event listenerów i inicjalizacja formularza
document.addEventListener('DOMContentLoaded', function() {
    // Inicjalizacja przycisków dodawania
    document.getElementById('add-medication').addEventListener('click', addMedication);
    document.getElementById('add-supplement').addEventListener('click', addSupplement);
    document.getElementById('add-treatment')?.addEventListener('click', addTreatment);
    
    console.log('=== Inicjalizacja formularza rozpoczęta ===');
    
    // Inicjalizacja wyboru stanu skóry głowy na podstawie istniejących danych
    const skinConditionField = document.getElementById('skin_condition');
    if (skinConditionField && skinConditionField.value) {
        try {
            console.log('Wartość skin_condition:', skinConditionField.value);
            
            // Spróbuj odczytać wartość jako JSON
            let selectedValues = [];
            
            // Czyścimy i odczytujemy wartość
            const cleanValue = skinConditionField.value.replace(/\\/g, '')
                .replace(/"\[/g, '[')
                .replace(/\]"/g, ']');
                
            console.log('Oczyszczona wartość skin_condition:', cleanValue);
            
            // Sprawdź czy wartość jest już tablicą
            try {
                if (cleanValue.startsWith('[')) {
                    selectedValues = JSON.parse(cleanValue);
                } else {
                    // Jeśli nie jest tablicą, spróbuj ją przekształcić
                    selectedValues = cleanValue.split(',').map(v => v.trim());
                }
            } catch (jsonError) {
                console.error('Błąd podczas parsowania JSON dla skin_condition:', jsonError);
                // Fallback - użyj surowej wartości jeśli parsowanie się nie powiedzie
                selectedValues = [cleanValue];
            }
            
            // Poprawka - jeśli selectedValues to tablica tablic lub zawiera znaki specjalne
            if (selectedValues.length === 1 && typeof selectedValues[0] === 'string' && selectedValues[0].includes('[')) {
                try {
                    // Jeszcze raz próbujemy sparsować
                    selectedValues = JSON.parse(selectedValues[0]);
                } catch(e) {
                    console.error('Drugi błąd parsowania skin_condition:', e);
                }
            }
            
            console.log('Odczytane wartości skin_condition:', selectedValues);
            
            // Zaznacz odpowiednie elementy w interfejsie
            if (Array.isArray(selectedValues)) {
                selectedValues.forEach(value => {
                    const item = document.querySelector(`.condition-item[data-value="${value}"]`);
                    if (item) {
                        item.classList.add('selected');
                    } else {
                        console.warn(`Nie znaleziono elementu dla wartości ${value}`);
                    }
                });
            }
            
            // Aktualizacja wartości w polu hidden po inicjalizacji
            updateSkinConditionValue();
            
        } catch (error) {
            console.error('Błąd podczas inicjalizacji skin_condition:', error);
        }
    }
    
    // Inicjalizacja checkboxów - wszystkich typów
    const checkboxGroupFields = ['styling', 'problem_description', 'problem_periodicity', 'previous_procedures'];
    
    checkboxGroupFields.forEach(fieldName => {
        console.log(`Inicjalizacja pola checkbox ${fieldName}`);
        
        // Sprawdź czy dane są dostępne w obiekcie patientData
        if (patientData && patientData[fieldName]) {
            try {
                let values = patientData[fieldName];
                
                // Jeśli wartość to string, spróbuj sparsować jako JSON
                if (typeof values === 'string') {
                    try {
                        values = JSON.parse(values);
                    } catch (jsonErr) {
                        // Jeśli nie udało się sparsować jako JSON, traktuj jako pojedynczą wartość
                        values = [values];
                    }
                }
                
                console.log(`Wartości dla ${fieldName}:`, values);
                
                // Zaznacz odpowiednie checkboxy
                if (Array.isArray(values)) {
                    values.forEach(value => {
                        const checkbox = document.querySelector(`input[name="${fieldName}"][value="${value}"]`);
                        if (checkbox) {
                            checkbox.checked = true;
                            console.log(`Zaznaczono checkbox ${fieldName}=${value}`);
                        } else {
                            console.warn(`Nie znaleziono checkboxa dla ${fieldName}=${value}`);
                        }
                    });
                }
            } catch (error) {
                console.error(`Błąd podczas inicjalizacji checkboxów ${fieldName}:`, error);
            }
        } else {
            console.log(`Brak danych dla pola ${fieldName} w patientData`);
        }
    });
    
    // Upewnij się, że pola select mają prawidłowo zaznaczone opcje
    const selectFields = ['peeling_type', 'peeling_frequency', 'coloring_type', 'coloring_frequency'];
    selectFields.forEach(fieldId => {
        const selectElement = document.getElementById(fieldId);
        
        if (selectElement && patientData && patientData[fieldId]) {
            const value = patientData[fieldId];
            
            // Znajdź opcję z tą wartością
            const option = Array.from(selectElement.options).find(opt => opt.value === value);
            
            if (option) {
                option.selected = true;
                console.log(`Ustawiono wartość ${value} dla selecta ${fieldId}`);
            } else {
                console.warn(`Nie znaleziono opcji z wartością ${value} dla pola ${fieldId}`);
            }
        }
    });
    
    // Renderuj dane harmonogramu tygodniowego (jeśli istnieją)
    if (typeof patientData !== 'undefined' && patientData) {
        renderScheduleData();
    }
    
    console.log('=== Inicjalizacja formularza zakończona ===');
    
    // Obsługa pokazywania/ukrywania pól tekstowych dla używek
    document.querySelectorAll('input[name="habits"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const habitsDetails = document.getElementById('habits_details');
            const anyHabitChecked = document.querySelectorAll('input[name="habits"]:checked').length > 0;
            if (habitsDetails) {
                habitsDetails.style.display = anyHabitChecked ? 'block' : 'none';
            }
        });
    });

    // Obsługa pokazywania/ukrywania pól tekstowych dla aktywności fizycznej
    document.querySelectorAll('input[name="physical_activity"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const activityDetails = document.getElementById('activity_details');
            const anyActivityChecked = document.querySelectorAll('input[name="physical_activity"]:checked').length > 0;
            if (activityDetails) {
                activityDetails.style.display = anyActivityChecked ? 'block' : 'none';
            }
        });
    });
    
    // Sprawdź początkowy stan checkboxów przy ładowaniu strony
    const habitsChecked = document.querySelectorAll('input[name="habits"]:checked').length > 0;
    const habitsDetails = document.getElementById('habits_details');
    if (habitsDetails) {
        habitsDetails.style.display = habitsChecked ? 'block' : 'none';
    }
    
    const activityChecked = document.querySelectorAll('input[name="physical_activity"]:checked').length > 0;
    const activityDetails = document.getElementById('activity_details');
    if (activityDetails) {
        activityDetails.style.display = activityChecked ? 'block' : 'none';
    }

    // Obsługa checkboxów "Inne"
    document.querySelectorAll('input[type="checkbox"][value="other"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const otherTextarea = document.getElementById(this.id + '_other');
            if (otherTextarea) {
                otherTextarea.style.display = this.checked ? 'block' : 'none';
            }
        });
    });

    // Obsługa wysłania formularza
    const patientForm = document.getElementById('patientForm');
    if (patientForm) {
        patientForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Zatrzymaj domyślne wysłanie formularza
            
            const requiredFields = this.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error');
                } else {
                    field.classList.remove('error');
                }
            });

            if (!isValid) {
                alert('Proszę wypełnić wszystkie wymagane pola przed zapisaniem dokumentacji.');
                return;
            }

            // Zbierz dane z formularza
            const formData = new FormData(this);
            const data = {};
            
            // Konwertuj FormData na obiekt
            for (let [key, value] of formData.entries()) {
                if (data[key]) {
                    // Jeśli pole już istnieje, utwórz tablicę
                    if (!Array.isArray(data[key])) {
                        data[key] = [data[key]];
                    }
                    data[key].push(value);
                } else {
                    data[key] = value;
                }
            }
            
            // Przetwórz dane leków i suplementów
            const medications = [];
            const medicationNames = this.querySelectorAll('input[name="medication_name[]"]');
            const medicationDoses = this.querySelectorAll('input[name="medication_dose[]"]');
            const medicationSchedules = this.querySelectorAll('textarea[name="medication_schedule[]"]');
            
            for (let i = 0; i < medicationNames.length; i++) {
                if (medicationNames[i].value.trim()) {
                    medications.push({
                        name: medicationNames[i].value.trim(),
                        dose: medicationDoses[i] ? medicationDoses[i].value.trim() : '',
                        schedule: medicationSchedules[i] ? medicationSchedules[i].value.trim() : ''
                    });
                }
            }
            if (medications.length > 0) {
                data.medication_list = medications;
            }
            
            const supplements = [];
            const supplementNames = this.querySelectorAll('input[name="supplement_name[]"]');
            const supplementDoses = this.querySelectorAll('input[name="supplement_dose[]"]');
            const supplementSchedules = this.querySelectorAll('textarea[name="supplement_schedule[]"]');
            
            for (let i = 0; i < supplementNames.length; i++) {
                if (supplementNames[i].value.trim()) {
                    supplements.push({
                        name: supplementNames[i].value.trim(),
                        dose: supplementDoses[i] ? supplementDoses[i].value.trim() : '',
                        schedule: supplementSchedules[i] ? supplementSchedules[i].value.trim() : ''
                    });
                }
            }
            if (supplements.length > 0) {
                data.supplements_list = supplements;
            }

            // Dodaj dane z checkboxów - grupuj po nazwach
            const checkboxGroups = {};
            this.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
                const name = checkbox.name;
                if (!checkboxGroups[name]) {
                    checkboxGroups[name] = [];
                }
                checkboxGroups[name].push(checkbox.value);
            });
            
            // Dodaj grupy checkboxów do danych
            Object.keys(checkboxGroups).forEach(name => {
                data[name] = checkboxGroups[name];
            });

            this.querySelectorAll('input[type="radio"]:checked').forEach(radio => {
                data[radio.name] = radio.value;
            });

            // Dodaj dane z range inputów
            this.querySelectorAll('input[type="range"]').forEach(range => {
                data[range.name] = range.value;
            });

            // Wyślij dane do API
            fetch('/api/save-patient', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    alert('Dokumentacja została zapisana pomyślnie!');
                    // Przekieruj do strony pacjenta
                    if (data.pesel) {
                        window.location.href = `/patient/${data.pesel}`;
                    } else {
                        window.location.href = '/';
                    }
                } else {
                    alert('Błąd podczas zapisywania: ' + (result.error || 'Nieznany błąd'));
                }
            })
            .catch(error => {
                console.error('Błąd:', error);
                alert('Wystąpił błąd podczas zapisywania dokumentacji.');
            });
        });
    }
}); 