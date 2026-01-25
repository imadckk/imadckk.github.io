// Supabase configuration
import { createClient } from 'https://esm.sh/@supabase/supabase-js'

const supabaseUrl = 'https://dorkygsgobhcagtqydjb.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRvcmt5Z3Nnb2JoY2FndHF5ZGpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEwOTc0MzcsImV4cCI6MjA3NjY3MzQzN30.bNCo8Ijj2DIr-c34P7U-lb6QK69D8OzO2sCd6SOwaW0'
const supabase = createClient(supabaseUrl, supabaseKey);

let currentDate = new Date(new Date().toLocaleString("en-US", {timeZone: "Asia/Kuala_Lumpur"}));
let currentLocationId = null;
let locations = [];

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

async function initializeApp() {
    await loadLocations();
    setupEventListeners();
    
    // Show instruction message instead of auto-loading calendar
    showInstructionMessage();
}

async function loadLocations() {
    try {
        console.log('Loading locations from database...');
        
        const { data, error } = await supabase
            .from('locations')
            .select('id, name, description')
            .order('name');

        if (error) {
            console.error('Error loading locations:', error);
            return;
        }

        locations = data || [];
        console.log('Locations loaded:', locations);
        
        // Update location toggle buttons
        updateLocationButtons();
        
    } catch (error) {
        console.error('Error in loadLocations:', error);
    }
}

function updateLocationButtons() {
    const toggleContainer = document.querySelector('.btn-group');
    
    // Clear existing buttons
    toggleContainer.innerHTML = '';

    // Create buttons for each location
    locations.forEach((location, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn location-toggle';
      button.dataset.location = location.id;
      button.textContent = location.name;
    
      // Assign color based on position
      if (index === 0) {
        button.classList.add('btn-red');
      } else if (index === 1) {
        button.classList.add('btn-blue');
      }
    
      button.addEventListener('click', () => selectLocation(location.id));
      toggleContainer.appendChild(button);
    });
        
      
    // If no locations found, show message
    if (locations.length === 0) {
        const message = document.createElement('button');
        message.type = 'button';
        message.className = 'btn btn-outline-secondary';
        message.textContent = 'No locations found';
        message.disabled = true;
        toggleContainer.appendChild(message);
    }
}

function showInstructionMessage() {
    const calendar = document.getElementById('calendar');
    calendar.innerHTML = `
        <div class="text-center py-5">
            <h5 class="text-muted">Select a location to view availability</h5>
            <p class="text-muted small">Click on any location button above to view the calendar</p>
        </div>
    `;
}

function selectLocation(locationId) {
  currentLocationId = locationId;

  document.querySelectorAll('.location-toggle').forEach((btn, index) => {
    const isActive = btn.dataset.location === locationId;
    btn.classList.toggle('active', isActive);

    // Reset all color-related classes first
    btn.classList.remove(
      'btn-outline-primary',
      'btn-outline-danger',
      'btn-red',
      'btn-blue'
    );

    // Apply colors consistently by index (or name)
    if (index === 0) {
      // Location A (Red)
      btn.classList.add(isActive ? 'btn-red' : 'btn-outline-danger');
    } else if (index === 1) {
      // Location B (Blue)
      btn.classList.add(isActive ? 'btn-blue' : 'btn-outline-primary');
    }
  });

  // Update calendar title
  const currentLocation = locations.find((loc) => loc.id === locationId);
  if (currentLocation) {
    document.querySelector('h1').textContent = `${currentLocation.name} Calendar`;
  }

  renderCalendar();
}


function setupEventListeners() {
    // Month navigation
    document.getElementById('prevMonth').addEventListener('click', () => {
        if (!currentLocationId) {
            alert('Please select a location first.');
            return;
        }
        // Create new date in Malaysia timezone
        const newDate = new Date(currentDate);
        newDate.setMonth(newDate.getMonth() - 1);
        // Convert to Malaysia timezone
        currentDate = new Date(newDate.toLocaleString("en-US", {timeZone: "Asia/Kuala_Lumpur"}));
        renderCalendar();
    });

    document.getElementById('nextMonth').addEventListener('click', () => {
        if (!currentLocationId) {
            alert('Please select a location first.');
            return;
        }
        const newDate = new Date(currentDate);
        newDate.setMonth(newDate.getMonth() + 1);
        currentDate = new Date(newDate.toLocaleString("en-US", {timeZone: "Asia/Kuala_Lumpur"}));
        renderCalendar();
    });
}

async function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const monthYear = document.getElementById('currentMonth');
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    monthYear.textContent = currentDate.toLocaleString('default', { 
        month: 'long', 
        year: 'numeric' 
    });

    // Show loading state
    calendar.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Loading calendar...</p>
        </div>
    `;

    // Load date settings for the current month and selected location
    const dateSettings = await loadDateSettingsForMonth(year, month + 1);

    // Now render the actual calendar
    calendar.innerHTML = '';

    // Create day headers - 7 columns for 7 days of the week
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    dayNames.forEach(day => {
        const dayHeader = document.createElement('div');
        dayHeader.className = 'calendar-day fw-bold text-center';
        dayHeader.textContent = day;
        calendar.appendChild(dayHeader);
    });

    // Get first day of month and calculate starting position
    const firstDay = new Date(year, month, 1);
    const startingDay = firstDay.getDay(); // 0 = Sunday, 1 = Monday, etc.
    
    // Add empty cells for days before the first day of month
    // This ensures dates align properly with day headers
    for (let i = 0; i < startingDay; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day other-month';
        calendar.appendChild(emptyDay);
    }

    // Create days of the month
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    for (let day = 1; day <= daysInMonth; day++) {
        const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day';
        dayElement.textContent = day;

        // Determine day status (READ-ONLY - no click events)
        const isActive = getDayStatus(dateString, dateSettings);
        updateDayElementAppearance(dayElement, isActive, dateString);

        calendar.appendChild(dayElement);
    }

    // Add CSS grid layout to ensure proper 7-column structure
    //calendar.style.display = 'grid';
    //calendar.style.gridTemplateColumns = 'repeat(7, 1fr)';
    //calendar.style.gap = '2px';
}

function updateDayElementAppearance(dayElement, isActive, dateString) {
    // Remove existing status classes
    dayElement.classList.remove('active-day', 'inactive-day');
    
    const currentLocation = locations.find(loc => loc.id === currentLocationId);
    const locationName = currentLocation ? currentLocation.name : 'Location';
    
    if (isActive) {
        dayElement.classList.add('active-day');
        dayElement.title = `${dateString} - ${locationName} is available`;
    } else {
        dayElement.classList.add('inactive-day');
        dayElement.title = `${dateString} - ${locationName} is unavailable`;
    }
}

async function loadDateSettingsForMonth(year, month) {
    if (!currentLocationId) return [];

    const startDate = `${year}-${String(month).padStart(2, '0')}-01`;
    const endDate = `${year}-${String(month).padStart(2, '0')}-${new Date(year, month, 0).getDate()}`;

    try {
        const { data, error } = await supabase
            .from('date_settings')
            .select('*')
            .eq('location_id', currentLocationId)
            .gte('date', startDate)
            .lte('date', endDate);

        if (error) {
            console.error('Error loading date settings:', error);
            return [];
        }

        return data || [];
    } catch (error) {
        console.error('Error in loadDateSettingsForMonth:', error);
        return [];
    }
}


function getDayStatus(dateString, dateSettings) {
    if (!currentLocationId) return true;

    // Get today's date in Malaysia timezone
    const now = new Date();
    const todayMalaysia = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Kuala_Lumpur"}));
    
    // Format consistently
    const todayFormatted = todayMalaysia.getFullYear() + '-' + 
                          String(todayMalaysia.getMonth() + 1).padStart(2, '0') + '-' + 
                          String(todayMalaysia.getDate()).padStart(2, '0');

    // Parse input date IN MALAYSIA TIMEZONE
    const inputDate = new Date(dateString + 'T00:00:00Z'); // Use UTC
    const dayOfWeek = inputDate.getUTCDay(); // Now consistent
    
    // Calculate cutoff (today + 2 calendar days)
    const cutoffDate = new Date(todayMalaysia);
    cutoffDate.setDate(cutoffDate.getDate() + 2);
    const cutoffFormatted = cutoffDate.getFullYear() + '-' + 
                           String(cutoffDate.getMonth() + 1).padStart(2, '0') + '-' + 
                           String(cutoffDate.getDate()).padStart(2, '0');

    console.log('Date check:', {
        checking: dateString,
        today: todayFormatted,
        cutoff: cutoffFormatted,
        isBeforeCutoff: dateString < cutoffFormatted,
        isSunday: dayOfWeek === 0,
        todayIsSunday: todayMalaysia.getDay() === 0
    });

    // RULE 1: Must be at least 2 FULL days in advance
    if (dateString < cutoffFormatted) {
        return false;
    }

    // RULE 2: No Sundays ever
    if (dayOfWeek === 0) {
        return false;
    }

    // RULE 3: Check Supabase overrides
    const setting = dateSettings.find(s => s.date === dateString);
    if (setting) {
        return setting.is_active;
    }

    return true;
}
