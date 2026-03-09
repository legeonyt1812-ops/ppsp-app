// Дополнительные функции

function copyToClipboard(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    
    showTooltip('Скопировано!');
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
    var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}

function formatTime(date) {
    var d = new Date(date),
        hours = '' + d.getHours(),
        minutes = '' + d.getMinutes();

    if (hours.length < 2) hours = '0' + hours;
    if (minutes.length < 2) minutes = '0' + minutes;

    return [hours, minutes].join(':');
}