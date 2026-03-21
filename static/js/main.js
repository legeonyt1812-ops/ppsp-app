// Дополнительные утилиты

function copyToClipboard(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    
    showTooltip('Скопировано в буфер обмена');
}

function showTooltip(message) {
    var tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = message;
    tooltip.style.position = 'fixed';
    tooltip.style.bottom = '20px';
    tooltip.style.right = '20px';
    tooltip.style.background = '#1e3a5f';
    tooltip.style.color = 'white';
    tooltip.style.padding = '10px 20px';
    tooltip.style.borderRadius = '5px';
    tooltip.style.zIndex = '9999';
    document.body.appendChild(tooltip);
    
    setTimeout(function() {
        tooltip.remove();
    }, 2000);
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

function formatDate(date) {
    var d = new Date(date);
    var month = '' + (d.getMonth() + 1);
    var day = '' + d.getDate();
    var year = d.getFullYear();

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}

function formatTime(date) {
    var d = new Date(date);
    var hours = '' + d.getHours();
    var minutes = '' + d.getMinutes();

    if (hours.length < 2) hours = '0' + hours;
    if (minutes.length < 2) minutes = '0' + minutes;

    return [hours, minutes].join(':');
}

function formatDateTime(date) {
    return formatDate(date) + ' ' + formatTime(date);
}

function showLoader(container) {
    var loader = document.createElement('div');
    loader.className = 'loader';
    container.innerHTML = '';
    container.appendChild(loader);
}

function hideLoader(container) {
    container.innerHTML = '';
}

function showModal(id) {
    document.getElementById(id).style.display = 'block';
}

function hideModal(id) {
    document.getElementById(id).style.display = 'none';
}

function ajaxGet(url, callback) {
    fetch(url)
        .then(response => response.json())
        .then(data => callback(null, data))
        .catch(error => callback(error, null));
}

function ajaxPost(url, data, callback) {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(data => callback(null, data))
        .catch(error => callback(error, null));
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Валидация форм
function validatePassport(series, number) {
    var seriesRegex = /^\d{4}$/;
    var numberRegex = /^\d{6}$/;
    return seriesRegex.test(series) && numberRegex.test(number);
}

function validatePhone(phone) {
    var phoneRegex = /^\+?[0-9]{10,15}$/;
    return phoneRegex.test(phone.replace(/[\s\-\(\)]/g, ''));
}

function validateEmail(email) {
    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Экспорт в CSV
function exportToCSV(data, filename) {
    var csv = '';
    
    // Заголовки
    csv += Object.keys(data[0]).join(',') + '\n';
    
    // Данные
    data.forEach(row => {
        csv += Object.values(row).map(value => {
            if (typeof value === 'string' && value.includes(',')) {
                return `"${value}"`;
            }
            return value;
        }).join(',') + '\n';
    });
    
    var blob = new Blob([csv], { type: 'text/csv' });
    var url = window.URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
}

// Печать
function printElement(elementId) {
    var printContents = document.getElementById(elementId).innerHTML;
    var originalContents = document.body.innerHTML;
    
    document.body.innerHTML = printContents;
    window.print();
    document.body.innerHTML = originalContents;
}
