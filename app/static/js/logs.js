/**
 * logs.js
 * 로그 뷰어 관련 기능
 */

let currentLogFile = null;
let logWrapEnabled = false;
let allLogLines = [];
let currentModuleFilter = 'ALL';

/**
 * 로그 뷰 표시
 */
function showLogs() {
    hideAllViews();
    document.getElementById('logs-view').classList.add('active');
    
    // 사이드바 업데이트
    updateSidebarNav();
    const logsBtn = document.querySelector('.sidebar-nav-btn[data-view="logs"]');
    if (logsBtn) {
        logsBtn.classList.add('bg-white', 'shadow-sm');
    }
    
    loadLogs();
}

/**
 * 로그 파일 목록 및 내용 로드
 */
async function loadLogs() {
    try {
        // 로그 파일 목록 로드 (반환된 목록을 받아 기본 선택을 설정)
        const files = await loadLogFilesList();

        // 기본 선택 파일은 파일 목록을 로드한 뒤 설정 (첫 항목)
        if (!currentLogFile && files && files.length > 0) {
            currentLogFile = files[0].name;
            document.getElementById('currentLogFileName').textContent = currentLogFile;
        }

        // 현재 로그 파일 내용 로드
        if (currentLogFile) await loadLogContent(currentLogFile);
        
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
                <div class="min-h-[120px] flex items-center justify-center py-4 text-gray-400">
                    <i class="bi bi-inbox text-3xl"></i>
                    <p class="mb-0 mt-2 ms-2">No log files found</p>
                </div>
            `;
            return;
        }
        
        listContainer.innerHTML = files.map(file => {
            const isActive = file.name === currentLogFile;
            // Tailwind color mapping for file size indicator
            const sizeColor = file.size_mb > 10 ? 'text-red-500' : file.size_mb > 5 ? 'text-yellow-500' : 'text-gray-500';

            return `
                <a href="#" class="list-group-item block px-4 py-3 hover:bg-gray-50 ${isActive ? 'bg-sky-100' : ''} cursor-pointer no-underline text-current" 
                   onclick="selectLogFile('${file.name}', event); return false;">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center">
                            <i class="bi bi-file-earmark-text mr-2"></i>
                            <strong>${file.name}</strong>
                        </div>
                        <div class="text-right">
                            <span class="${sizeColor} text-sm">${file.size_mb} MB</span>
                            <br>
                            <small class="text-gray-400 text-xs">${file.modified_date}</small>
                        </div>
                    </div>
                </a>
            `;
        }).join('');

        // 반환: 호출자(loadLogs)가 기본 선택을 결정할 수 있도록 파일 목록 반환
        return files;
        
    } catch (error) {
        console.error('Failed to load log files list:', error);
        document.getElementById('logFilesList').innerHTML = `
            <div class="min-h-[160px] flex items-center justify-center py-4 text-red-500">
                <i class="bi bi-exclamation-triangle text-3xl"></i>
                <p class="mb-0 mt-2 ms-2">Failed to load log files</p>
            </div>
        `;
        return [];
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
    
    // 파일 목록 UI 업데이트 (즉시 적용하여 클릭 반응을 빠르게 만듦)
    document.querySelectorAll('#logFilesList .list-group-item').forEach(item => {
        item.classList.remove('active');
    });
    if (event && event.target) {
        const el = event.target.closest('.list-group-item');
        if (el) el.classList.add('active');
    } else {
        // event가 없는 경우 filename으로 찾기
        const activeItem = document.querySelector(`#logFilesList .list-group-item[onclick*="${filename}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }

    // 로그 내용은 비동기적으로 로드 (UI는 즉시 반응)
    loadLogContent(filename).catch(err => console.error('loadLogContent error:', err));
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
