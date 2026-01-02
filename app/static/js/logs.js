/**
 * logs.js
 * 로그 뷰어 관련 기능
 */

let currentLogFile = 'trading.log';
let logWrapEnabled = false;
let allLogLines = [];
let currentModuleFilter = 'ALL';

/**
 * 로그 뷰 표시
 */
function showLogs() {
    hideAllViews();
    document.getElementById('logs-view').classList.add('active');
    loadLogs();
}

/**
 * 로그 파일 목록 및 내용 로드
 */
async function loadLogs() {
    try {
        // 로그 파일 목록 로드
        await loadLogFilesList();
        
        // 현재 로그 파일 내용 로드
        await loadLogContent(currentLogFile);
        
    } catch (error) {
        console.error('Failed to load logs:', error);
        showAlert('Failed to load logs: ' + error.message, 'danger');
    }
}

/**
 * 로그 파일 목록 로드
 */
async function loadLogFilesList() {
    try {
        const response = await fetch(`${API_BASE}/logs/files?limit=50&_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load log files');
        
        const files = await response.json();
        
        // 파일 개수 업데이트
        document.getElementById('logFilesCount').textContent = `${files.length} files`;
        
        // 파일 목록 렌더링
        const listContainer = document.getElementById('logFilesList');
        if (files.length === 0) {
            listContainer.innerHTML = `
                <div class="list-group-item text-center text-muted py-4">
                    <i class="bi bi-inbox fs-3"></i>
                    <p class="mb-0 mt-2">No log files found</p>
                </div>
            `;
            return;
        }
        
        listContainer.innerHTML = files.map(file => {
            const isActive = file.name === currentLogFile;
            const sizeColor = file.size_mb > 10 ? 'text-danger' : file.size_mb > 5 ? 'text-warning' : 'text-muted';
            
            return `
                <a href="#" class="list-group-item list-group-item-action ${isActive ? 'active' : ''}" 
                   onclick="selectLogFile('${file.name}', event); return false;">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi bi-file-earmark-text me-2"></i>
                            <strong>${file.name}</strong>
                        </div>
                        <div class="text-end">
                            <span class="${sizeColor} small">${file.size_mb} MB</span>
                            <br>
                            <small class="text-muted">${file.modified_date}</small>
                        </div>
                    </div>
                </a>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Failed to load log files list:', error);
        document.getElementById('logFilesList').innerHTML = `
            <div class="list-group-item text-center text-danger py-4">
                <i class="bi bi-exclamation-triangle fs-3"></i>
                <p class="mb-0 mt-2">Failed to load log files</p>
            </div>
        `;
    }
}

/**
 * 로그 파일 선택
 */
async function selectLogFile(filename, event) {
    currentLogFile = filename;
    document.getElementById('currentLogFileName').textContent = filename;
    
    // 모듈 필터 초기화 (새 로그 파일 선택 시)
    currentModuleFilter = 'ALL';
    const moduleFilterSelect = document.getElementById('logModuleFilter');
    if (moduleFilterSelect) {
        moduleFilterSelect.value = 'ALL';
    }
    
    await loadLogContent(filename);
    
    // 파일 목록 UI 업데이트
    document.querySelectorAll('#logFilesList .list-group-item').forEach(item => {
        item.classList.remove('active');
    });
    if (event && event.target) {
        event.target.closest('.list-group-item').classList.add('active');
    } else {
        // event가 없는 경우 filename으로 찾기
        const activeItem = document.querySelector(`#logFilesList .list-group-item[onclick*="${filename}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }
}

/**
 * 로그 내용 로드
 */
async function loadLogContent(filename) {
    const logContent = document.getElementById('logContent');
    const lines = document.getElementById('logLinesSelect').value;
    
    try {
        logContent.textContent = 'Loading...';
        
        const response = await fetch(`${API_BASE}/logs/content?filename=${encodeURIComponent(filename)}&lines=${lines}`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Log file not found');
            }
            throw new Error('Failed to load log content');
        }
        
        const content = await response.text();
        
        if (!content || content.trim() === '') {
            logContent.innerHTML = '<span class="text-muted">(Empty log file)</span>';
            allLogLines = [];
        } else {
            allLogLines = content.split('\n');
            updateModuleFilterOptions();
            renderFilteredLogContent();
            // 자동으로 맨 아래로 스크롤
            logContent.scrollTop = logContent.scrollHeight;
        }
        
    } catch (error) {
        console.error('Failed to load log content:', error);
        logContent.innerHTML = `<span class="text-danger">Error: ${error.message}</span>`;
        showAlert('Failed to load log content: ' + error.message, 'danger');
    }
}

/**
 * 로그에서 모듈명 추출
 */
function extractModule(line) {
    // 포맷: "2025-12-29 18:00:00 - app.services.scheduler - INFO"
    const match1 = line.match(/\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?\s+-\s+([^\s-]+)\s+-\s+/);
    if (match1) return match1[1];
    
    // 포맷: "INFO:app.services.scheduler:message"
    const match2 = line.match(/[A-Z]+:([^:]+):/);
    if (match2) return match2[1];
    
    return null;
}

/**
 * 모듈 필터 옵션 업데이트
 */
function updateModuleFilterOptions() {
    const select = document.getElementById('logModuleFilter');
    if (!select) return;
    
    const modules = new Set();
    
    allLogLines.forEach(line => {
        const mod = extractModule(line);
        if (mod) modules.add(mod);
    });
    
    const prevValue = select.value;
    select.innerHTML = '<option value="ALL">ALL MODULES</option>';
    
    Array.from(modules).sort().forEach(mod => {
        const opt = document.createElement('option');
        opt.value = mod;
        opt.textContent = mod;
        select.appendChild(opt);
    });
    
    if (prevValue && Array.from(select.options).some(opt => opt.value === prevValue)) {
        select.value = prevValue;
    } else {
        select.value = 'ALL';
    }
}

/**
 * 필터링된 로그 렌더링
 */
function renderFilteredLogContent() {
    const logContent = document.getElementById('logContent');
    
    if (!allLogLines || allLogLines.length === 0) {
        logContent.innerHTML = '<span class="text-muted">(No log content)</span>';
        return;
    }
    
    let filteredLines = allLogLines;
    
    // 모듈 필터 적용
    if (currentModuleFilter !== 'ALL') {
        filteredLines = allLogLines.filter(line => {
            const module = extractModule(line);
            return module === currentModuleFilter;
        });
    }
    
    if (filteredLines.length === 0) {
        logContent.innerHTML = `<span class="text-warning">No logs found for module: ${currentModuleFilter}</span>`;
        return;
    }
    
    // 로그 레벨별 하이라이팅
    const highlightedLines = filteredLines.map(line => {
        const escapedLine = escapeHtml(line);
        
        if (line.includes('ERROR') || line.includes('CRITICAL')) {
            return `<span class="log-error">${escapedLine}</span>`;
        } else if (line.includes('WARNING') || line.includes('WARN')) {
            return `<span class="log-warning">${escapedLine}</span>`;
        } else if (line.includes('INFO')) {
            return `<span class="log-info">${escapedLine}</span>`;
        } else if (line.includes('DEBUG')) {
            return `<span class="log-debug">${escapedLine}</span>`;
        }
        return `<span>${escapedLine}</span>`;
    });
    
    logContent.innerHTML = highlightedLines.join('<br>');
    
    // 자동으로 맨 아래로 스크롤
    logContent.scrollTop = logContent.scrollHeight;
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 로그 줄바꿈 토글
 */
function toggleLogWrap() {
    const logContent = document.getElementById('logContent');
    logWrapEnabled = !logWrapEnabled;
    
    if (logWrapEnabled) {
        logContent.style.whiteSpace = 'pre-wrap';
        logContent.style.wordWrap = 'break-word';
    } else {
        logContent.style.whiteSpace = 'pre';
        logContent.style.wordWrap = 'normal';
    }
}

/**
 * 로그 내용 복사
 */
async function copyLogContent() {
    const logContent = document.getElementById('logContent');
    
    try {
        await navigator.clipboard.writeText(logContent.textContent);
        showAlert('Log content copied to clipboard!', 'success', 2000);
    } catch (error) {
        console.error('Failed to copy:', error);
        showAlert('Failed to copy to clipboard', 'danger');
    }
}

/**
 * 현재 로그 다운로드
 */
function downloadCurrentLog() {
    const logContent = document.getElementById('logContent').textContent;
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = currentLogFile;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showAlert('Log file downloaded!', 'success', 2000);
}

// 로그 라인 선택 변경 시 자동 새로고침
document.addEventListener('DOMContentLoaded', function() {
    const logLinesSelect = document.getElementById('logLinesSelect');
    if (logLinesSelect) {
        logLinesSelect.addEventListener('change', function() {
            loadLogContent(currentLogFile);
        });
    }
    
    // 모듈 필터 변경 이벤트
    const logModuleFilter = document.getElementById('logModuleFilter');
    if (logModuleFilter) {
        logModuleFilter.addEventListener('change', function() {
            currentModuleFilter = this.value;
            renderFilteredLogContent();
        });
    }
});
