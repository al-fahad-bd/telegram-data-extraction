// Truecaller BD Extractor - Modern Web Desktop Controller
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const tgStatusPill = document.getElementById('tgStatusPill');
  const tgStatusDot = document.getElementById('tgStatusDot');
  const tgStatusLabel = document.getElementById('tgStatusLabel');

  const startNumberInput = document.getElementById('startNumber');
  const presetOperatorSelect = document.getElementById('presetOperator');
  const batchCountInput = document.getElementById('batchCount');
  const minDelayInput = document.getElementById('minDelay');
  const maxDelayInput = document.getElementById('maxDelay');

  const singleNumberInput = document.getElementById('singleNumber');
  const btnSingleLookup = document.getElementById('btnSingleLookup');

  const btnStart = document.getElementById('btnStart');
  const btnPause = document.getElementById('btnPause');
  const btnStop = document.getElementById('btnStop');

  const radarPing = document.getElementById('radarPing');
  const scannerStatusText = document.getElementById('scannerStatusText');
  const spinnerChar = document.getElementById('spinnerChar');
  const currentTargetNum = document.getElementById('currentTargetNum');
  const progressFraction = document.getElementById('progressFraction');
  const progressPercentage = document.getElementById('progressPercentage');
  const progressBarFill = document.getElementById('progressBarFill');
  const countdownVal = document.getElementById('countdownVal');

  const metricTotal = document.getElementById('metricTotal');
  const metricFound = document.getElementById('metricFound');
  const metricNotFound = document.getElementById('metricNotFound');
  const metricRate = document.getElementById('metricRate');

  const tableBody = document.getElementById('tableBody');
  const emptyStateRow = document.getElementById('emptyStateRow');
  const tableCountBadge = document.getElementById('tableCountBadge');
  const tableSearch = document.getElementById('tableSearch');
  const btnExportCsv = document.getElementById('btnExportCsv');
  const btnClearTable = document.getElementById('btnClearTable');

  const consoleBody = document.getElementById('consoleBody');
  const btnClearLogs = document.getElementById('btnClearLogs');

  const countrySelect = document.getElementById('countrySelect');
  const inputFlag = document.getElementById('inputFlag');
  const configSubtleBadge = document.getElementById('configSubtleBadge');

  // Country Presets
  const COUNTRY_PRESETS = {
    'BD': { name: 'Bangladesh', code: '+880', flag: '🇧🇩', sample: '+8801795664120' },
    'US': { name: 'United States / Canada', code: '+1', flag: '🇺🇸', sample: '+12025550120' },
    'GB': { name: 'United Kingdom', code: '+44', flag: '🇬🇧', sample: '+447911123450' },
    'IN': { name: 'India', code: '+91', flag: '🇮🇳', sample: '+919876543210' },
    'PK': { name: 'Pakistan', code: '+92', flag: '🇵🇰', sample: '+923001234567' },
    'AE': { name: 'United Arab Emirates', code: '+971', flag: '🇦🇪', sample: '+971501234567' },
    'SA': { name: 'Saudi Arabia', code: '+966', flag: '🇸🇦', sample: '+966501234567' },
    'QA': { name: 'Qatar', code: '+974', flag: '🇶🇦', sample: '+97433123456' },
    'KW': { name: 'Kuwait', code: '+965', flag: '🇰🇼', sample: '+96590123456' },
    'MY': { name: 'Malaysia', code: '+60', flag: '🇲🇾', sample: '+60123456789' },
    'SG': { name: 'Singapore', code: '+65', flag: '🇸🇬', sample: '+6581234567' },
    'AU': { name: 'Australia', code: '+61', flag: '🇦🇺', sample: '+61412345678' },
    'DE': { name: 'Germany', code: '+49', flag: '🇩🇪', sample: '+4915123456789' },
    'FR': { name: 'France', code: '+33', flag: '🇫🇷', sample: '+33612345678' },
    'IT': { name: 'Italy', code: '+39', flag: '🇮🇹', sample: '+393123456789' },
    'ES': { name: 'Spain', code: '+34', flag: '🇪🇸', sample: '+34612345678' },
    'TR': { name: 'Turkey', code: '+90', flag: '🇹🇷', sample: '+905321234567' },
    'BR': { name: 'Brazil', code: '+55', flag: '🇧🇷', sample: '+5511912345678' },
    'ID': { name: 'Indonesia', code: '+62', flag: '🇮🇩', sample: '+628123456789' },
    'PH': { name: 'Philippines', code: '+63', flag: '🇵🇭', sample: '+639171234567' },
    'NG': { name: 'Nigeria', code: '+234', flag: '🇳🇬', sample: '+2348031234567' },
    'ZA': { name: 'South Africa', code: '+27', flag: '🇿🇦', sample: '+27821234567' },
    'EG': { name: 'Egypt', code: '+20', flag: '🇪🇬', sample: '+201001234567' },
  };

  function getFlagForNumber(phone) {
    const digits = phone.replace(/\D/g, '');
    for (const [key, item] of Object.entries(COUNTRY_PRESETS)) {
      const cDigits = item.code.replace(/\D/g, '');
      if (digits.startsWith(cDigits)) {
        return item.flag;
      }
    }
    return '🌐';
  }

  // Operator Presets
  const OPERATOR_PRESETS = {
    'Grameenphone (017)': '+8801700000000',
    'Grameenphone (013)': '+8801300000000',
    'Robi (018)': '+8801800000000',
    'Banglalink (019)': '+8801900000000',
    'Banglalink (014)': '+8801400000000',
    'Airtel (016)': '+8801600000000',
    'Teletalk (015)': '+8801500000000',
  };

  if (countrySelect) {
    countrySelect.addEventListener('change', (e) => {
      const key = e.target.value;
      if (key === 'ALL') {
        inputFlag.textContent = '🌐';
        configSubtleBadge.textContent = 'Worldwide Custom 🌐';
        if (!startNumberInput.value.startsWith('+')) {
          startNumberInput.value = '+';
        }
      } else if (COUNTRY_PRESETS[key]) {
        const country = COUNTRY_PRESETS[key];
        inputFlag.textContent = country.flag;
        configSubtleBadge.textContent = `${country.name} ${country.flag}`;
        startNumberInput.value = country.sample;
      }
    });
  }

  startNumberInput.addEventListener('input', (e) => {
    inputFlag.textContent = getFlagForNumber(e.target.value);
  });

  if (presetOperatorSelect) {
    presetOperatorSelect.addEventListener('change', (e) => {
      const selected = e.target.value;
      const template = OPERATOR_PRESETS[selected];
      if (template) {
        if (countrySelect) countrySelect.value = 'BD';
        inputFlag.textContent = '🇧🇩';
        const current = startNumberInput.value.replace(/\D/g, '');
        if (current.length >= 11) {
          const suffix = current.slice(3);
          startNumberInput.value = template.slice(0, 6) + suffix;
        } else {
          startNumberInput.value = template;
        }
      }
    });
  }

  // Spinner frames
  const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let spinnerIdx = 0;
  let isAutomationActive = false;

  setInterval(() => {
    if (isAutomationActive) {
      spinnerIdx = (spinnerIdx + 1) % SPINNER_FRAMES.length;
      spinnerChar.textContent = SPINNER_FRAMES[spinnerIdx];
    }
  }, 120);

  // WebSocket Connection
  let ws = null;
  let isConnectedToTg = false;

  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      appendLog('Established real-time link with extractor engine.', 'success');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        console.error('Error parsing WS message:', err);
      }
    };

    ws.onclose = () => {
      tgStatusDot.className = 'status-dot pulse-offline';
      tgStatusLabel.textContent = 'Reconnecting to server...';
      setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function handleServerMessage(msg) {
    const { type, payload } = msg;

    switch (type) {
      case 'tg_status':
        isConnectedToTg = payload.connected;
        if (payload.connected) {
          tgStatusDot.className = 'status-dot pulse-online';
          tgStatusLabel.textContent = `Online: ${payload.user_display || 'Connected'}`;
          btnStart.disabled = isAutomationActive;
          btnSingleLookup.disabled = false;
        } else {
          tgStatusDot.className = 'status-dot pulse-offline';
          tgStatusLabel.textContent = `Offline: ${payload.error || 'Connecting...'}`;
          btnStart.disabled = true;
          btnSingleLookup.disabled = true;
        }
        break;

      case 'automation_state':
        isAutomationActive = payload.running && !payload.paused;
        if (payload.running) {
          radarPing.className = 'radar-ping active';
          if (payload.paused) {
            scannerStatusText.textContent = 'Automation Paused';
            btnPause.innerHTML = '<span class="btn-icon">▶</span><span>Resume</span>';
            btnPause.className = 'btn btn-primary';
          } else {
            scannerStatusText.textContent = 'Scanning in Progress...';
            btnPause.innerHTML = '<span class="btn-icon">⏸</span><span>Pause</span>';
            btnPause.className = 'btn btn-warning';
          }
          btnStart.disabled = true;
          btnPause.disabled = false;
          btnStop.disabled = false;
        } else {
          radarPing.className = 'radar-ping';
          scannerStatusText.textContent = 'System Idle';
          spinnerChar.textContent = '●';
          btnStart.disabled = !isConnectedToTg;
          btnPause.disabled = true;
          btnStop.disabled = true;
          btnPause.innerHTML = '<span class="btn-icon">⏸</span><span>Pause</span>';
          btnPause.className = 'btn btn-warning';
          countdownVal.textContent = '--';
        }
        break;

      case 'target_number':
        currentTargetNum.textContent = payload.phone_number || 'Ready to extract';
        break;

      case 'countdown':
        countdownVal.textContent = payload.seconds > 0 ? `${payload.seconds}s` : '--';
        break;

      case 'progress':
        const { current, total, percent } = payload;
        progressFraction.textContent = `${current} / ${total}`;
        progressPercentage.textContent = `${percent}%`;
        progressBarFill.style.width = `${percent}%`;
        break;

      case 'metrics':
        metricTotal.textContent = payload.total.toLocaleString();
        metricFound.textContent = payload.found.toLocaleString();
        metricNotFound.textContent = payload.not_found.toLocaleString();
        metricRate.textContent = `${payload.rate}%`;
        break;

      case 'new_record':
        addRecordToTable(payload);
        break;

      case 'records_sync':
        // Full reload of records
        clearTableDOM();
        if (payload.records && payload.records.length > 0) {
          payload.records.forEach((rec) => addRecordToTable(rec, false));
        }
        break;

      case 'log':
        appendLog(payload.message, payload.level || 'info');
        break;

      case 'clear_table':
        clearTableDOM();
        break;
    }
  }

  // DOM Log Appender
  function appendLog(text, level = 'info') {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];

    const row = document.createElement('div');
    row.className = 'log-line';

    const timeSpan = document.createElement('span');
    timeSpan.className = 'log-time';
    timeSpan.textContent = `[${timeStr}]`;

    const msgSpan = document.createElement('span');
    msgSpan.className = `log-msg ${level}`;
    msgSpan.textContent = text;

    row.appendChild(timeSpan);
    row.appendChild(msgSpan);
    consoleBody.appendChild(row);

    // Keep max 200 logs
    while (consoleBody.children.length > 200) {
      consoleBody.removeChild(consoleBody.firstChild);
    }
    consoleBody.scrollTop = consoleBody.scrollHeight;
  }

  btnClearLogs.addEventListener('click', () => {
    consoleBody.innerHTML = '';
  });

  // Table Management
  let allRecords = [];

  function addRecordToTable(record, animate = true) {
    if (emptyStateRow) {
      emptyStateRow.style.display = 'none';
    }

    allRecords.push(record);
    tableCountBadge.textContent = `${allRecords.length} Records`;

    const tr = document.createElement('tr');
    if (animate) tr.className = 'row-new';

    const statusLower = (record.status || '').toLowerCase();
    let badgeClass = 'badge-notfound';
    if (statusLower === 'found') badgeClass = 'badge-found';
    else if (statusLower.includes('limit') || statusLower.includes('error')) badgeClass = 'badge-ratelimit';

    const waLink = record.has_whatsapp
      ? `<a class="app-link active" href="https://wa.me/${encodeURIComponent(record.phone_number)}" target="_blank">✓ Yes</a>`
      : `<span class="app-link">✕ No</span>`;

    const tgLink = record.has_telegram
      ? `<a class="app-link active" href="https://t.me/${encodeURIComponent(record.phone_number)}" target="_blank">✓ Yes</a>`
      : `<span class="app-link">✕ No</span>`;

    tr.innerHTML = `
      <td>${record.id || allRecords.length}</td>
      <td style="color: var(--text-dim);">${record.time || ''}</td>
      <td class="phone-col">${escapeHtml(record.phone_number || '')}</td>
      <td class="name-col">${escapeHtml(record.name || 'Not Found')}</td>
      <td>${escapeHtml(record.carrier || 'Unknown')}</td>
      <td style="text-align: center;">${escapeHtml(record.country || 'Bangladesh')}</td>
      <td style="text-align: center;">${waLink}</td>
      <td style="text-align: center;">${tgLink}</td>
      <td><span class="status-badge ${badgeClass}">${escapeHtml(record.status || 'Unknown')}</span></td>
    `;

    tableBody.insertBefore(tr, tableBody.firstChild);
  }

  function clearTableDOM() {
    allRecords = [];
    tableBody.innerHTML = '';
    const emptyTr = document.createElement('tr');
    emptyTr.className = 'empty-row';
    emptyTr.id = 'emptyStateRow';
    emptyTr.innerHTML = `
      <td colspan="9">
        <div class="empty-state">
          <span class="empty-icon">📭</span>
          <p>No contact records extracted yet. Set starting number and click <b>Start Automation</b>.</p>
        </div>
      </td>
    `;
    tableBody.appendChild(emptyTr);
    tableCountBadge.textContent = '0 Records';
  }

  // Filter Table
  tableSearch.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    const rows = tableBody.querySelectorAll('tr:not(.empty-row)');
    rows.forEach((row) => {
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(term) ? '' : 'none';
    });
  });

  // Action Buttons
  btnStart.addEventListener('click', async () => {
    const startNumber = startNumberInput.value.trim();
    const count = parseInt(batchCountInput.value, 10) || 20;
    const minDelay = parseInt(minDelayInput.value, 10) || 20;
    const maxDelay = parseInt(maxDelayInput.value, 10) || 30;

    if (!startNumber) {
      alert('Please enter a valid starting phone number.');
      return;
    }

    try {
      const res = await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_number: startNumber,
          count: count,
          min_delay: minDelay,
          max_delay: maxDelay,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Failed to start automation.');
      }
    } catch (err) {
      alert(`Network error: ${err.message}`);
    }
  });

  btnPause.addEventListener('click', async () => {
    try {
      await fetch('/api/pause', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
  });

  btnStop.addEventListener('click', async () => {
    try {
      await fetch('/api/stop', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
  });

  btnSingleLookup.addEventListener('click', async () => {
    const num = singleNumberInput.value.trim();
    if (!num) {
      alert('Please enter a phone number to look up.');
      return;
    }
    btnSingleLookup.disabled = true;
    try {
      const res = await fetch('/api/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: num }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Lookup failed.');
      }
    } catch (err) {
      alert(`Lookup error: ${err.message}`);
    } finally {
      btnSingleLookup.disabled = false;
    }
  });

  btnClearTable.addEventListener('click', async () => {
    if (confirm('Clear all extracted records from view?')) {
      try {
        await fetch('/api/clear', { method: 'POST' });
      } catch (err) {
        console.error(err);
      }
    }
  });

  btnExportCsv.addEventListener('click', () => {
    window.location.href = '/api/export';
  });

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initialize WS
  connectWebSocket();
});
