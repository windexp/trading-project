/**
 * youtube.js
 * YouTube Summary 관련 기능
 */

let currentSummaryVideoId = null;
let addChannelModalInstance = null;
let editChannelModalInstance = null;
let channelSettingsModalInstance = null;

/**
 * YouTube Summary 뷰 표시
 */
function showYoutubeSummary() {
    hideAllViews();
    document.getElementById('youtube-view').classList.add('active');
    
    // 사이드바 업데이트
    updateSidebarNav();
    const youtubeBtn = document.querySelector('.sidebar-nav-btn[data-view="youtube"]');
    if (youtubeBtn) {
        youtubeBtn.classList.add('bg-white', 'shadow-sm');
    }
    
    loadYoutubeData();
}

/**
 * YouTube 데이터 로드 (채널 + 영상 목록 + 요약 목록)
 */
async function loadYoutubeData() {
    await Promise.all([
        loadYoutubeChannels(),
        loadYoutubeVideos(),
        loadYoutubeSummaries()
    ]);
}

/**
 * 채널 목록 로드
 */
async function loadYoutubeChannels() {
    const container = document.getElementById('youtubeChannelsList');
    container.innerHTML = `
        <div class="text-center py-2">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels?_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load channels');
        
        const data = await response.json();
        const channels = data.channels;
        
        if (channels.length === 0) {
            container.innerHTML = `
                <div class="text-center py-3 text-muted">
                    <small>등록된 채널이 없습니다</small>
                </div>
            `;
            return;
        }
        
        container.innerHTML = channels.map(channel => `
            <div class="list-group-item px-3 py-2 d-flex justify-content-between align-items-center hover:bg-gray-50">
                <div class="d-flex align-items-center gap-2">
                    ${channel.enabled 
                        ? '<i class="bi bi-check-circle-fill text-success"></i>' 
                        : '<i class="bi bi-pause-circle text-muted"></i>'
                    }
                    <span class="text-truncate" style="max-width: 150px; font-size: 0.85rem;">${escapeHtml(channel.channel_name)}</span>
                </div>
                <button class="btn btn-sm btn-link p-0 text-muted" onclick="openEditChannelModal('${channel.channel_id}')">
                    <i class="bi bi-pencil"></i>
                </button>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Failed to load channels:', error);
        container.innerHTML = `
            <div class="text-center py-2 text-danger">
                <small>채널 로드 실패</small>
            </div>
        `;
    }
}

/**
 * 최신 영상 목록 로드
 */
async function loadYoutubeVideos() {
    const container = document.getElementById('youtubeVideosList');
    container.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/youtube/videos?limit=10&_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load videos');
        
        const data = await response.json();
        const videos = data.videos;
        
        if (videos.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-inbox fs-3"></i>
                    <p class="mt-2 mb-0">등록된 채널이 없거나 영상을 찾을 수 없습니다</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = videos.map(video => `
            <div class="list-group-item px-3 py-3 hover:bg-gray-50 cursor-pointer" onclick="handleVideoClick('${video.video_id}', '${escapeHtml(video.title)}', '${escapeHtml(video.channel_name)}', ${video.is_analyzed})">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2">
                            ${video.is_analyzed 
                                ? '<span class="badge bg-success">분석완료</span>' 
                                : '<span class="badge bg-secondary">미분석</span>'
                            }
                            <small class="text-muted">${video.channel_name}</small>
                        </div>
                        <div class="fw-medium mt-1" style="font-size: 0.9rem;">${escapeHtml(video.title)}</div>
                        <small class="text-muted">${video.published}</small>
                    </div>
                    <a href="${video.link}" target="_blank" class="btn btn-sm btn-outline-secondary ms-2" onclick="event.stopPropagation();">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Failed to load videos:', error);
        container.innerHTML = `
            <div class="text-center py-4 text-danger">
                <i class="bi bi-exclamation-triangle fs-3"></i>
                <p class="mt-2 mb-0">영상 목록을 불러오는데 실패했습니다</p>
            </div>
        `;
    }
}

/**
 * 요약 목록 로드
 */
async function loadYoutubeSummaries() {
    const container = document.getElementById('youtubeSummariesList');
    container.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/youtube/summaries?limit=50&_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load summaries');
        
        const data = await response.json();
        const summaries = data.summaries;
        
        document.getElementById('summariesCount').textContent = `${summaries.length} summaries`;
        
        if (summaries.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-inbox fs-3"></i>
                    <p class="mt-2 mb-0">분석된 영상이 없습니다</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = summaries.map(summary => `
            <div class="list-group-item px-3 py-2 hover:bg-gray-50 cursor-pointer ${summary.video_id === currentSummaryVideoId ? 'bg-sky-100' : ''}" 
                 onclick="loadSummaryDetail('${summary.video_id}')">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2">
                            ${summary.has_error 
                                ? '<i class="bi bi-exclamation-circle text-danger"></i>' 
                                : '<i class="bi bi-check-circle text-success"></i>'
                            }
                            <small class="text-muted">${summary.channel_name}</small>
                        </div>
                        <div class="fw-medium text-truncate" style="font-size: 0.85rem; max-width: 280px;">${escapeHtml(summary.title)}</div>
                        <small class="text-muted">${formatDate(summary.analyzed_at)}</small>
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Failed to load summaries:', error);
        container.innerHTML = `
            <div class="text-center py-4 text-danger">
                <i class="bi bi-exclamation-triangle fs-3"></i>
                <p class="mt-2 mb-0">요약 목록을 불러오는데 실패했습니다</p>
            </div>
        `;
    }
}

/**
 * 영상 클릭 핸들러
 */
function handleVideoClick(videoId, title, channelName, isAnalyzed) {
    if (isAnalyzed) {
        loadSummaryDetail(videoId);
    } else {
        analyzeVideo(videoId, title, channelName);
    }
}

/**
 * 영상 분석 요청
 */
async function analyzeVideo(videoId, title, channelName) {
    if (!confirm(`"${title}" 영상을 분석하시겠습니까?\n\n분석에 1-2분 정도 소요될 수 있습니다.`)) {
        return;
    }
    
    showAlert('영상 분석 중...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/youtube/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_id: videoId,
                title: title,
                channel_name: channelName
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to analyze video');
        }
        
        const result = await response.json();
        
        if (result.status === 'success' || result.status === 'already_analyzed') {
            showAlert('영상 분석이 완료되었습니다!', 'success');
            await loadYoutubeData();
            loadSummaryDetail(videoId);
        } else {
            throw new Error('Analysis failed');
        }
        
    } catch (error) {
        console.error('Failed to analyze video:', error);
        showAlert('영상 분석에 실패했습니다: ' + error.message, 'danger');
    }
}

/**
 * 모든 새 영상 분석
 */
async function analyzeAllNewVideos() {
    if (!confirm('분석되지 않은 모든 새 영상을 분석하시겠습니까?\n\n영상 수에 따라 시간이 오래 걸릴 수 있습니다.')) {
        return;
    }
    
    showAlert('새 영상 분석 중...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/youtube/analyze-new`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to analyze new videos');
        }
        
        const result = await response.json();
        
        if (result.status === 'no_new_videos') {
            showAlert('분석할 새 영상이 없습니다.', 'info');
        } else {
            showAlert(`${result.count}개의 영상 분석이 완료되었습니다!`, 'success');
            await loadYoutubeData();
        }
        
    } catch (error) {
        console.error('Failed to analyze new videos:', error);
        showAlert('새 영상 분석에 실패했습니다: ' + error.message, 'danger');
    }
}

/**
 * 요약 상세 로드
 */
async function loadSummaryDetail(videoId) {
    currentSummaryVideoId = videoId;
    
    const contentContainer = document.getElementById('summaryContent');
    const titleContainer = document.getElementById('summaryTitle');
    const metaContainer = document.getElementById('summaryMeta');
    
    contentContainer.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    // 사이드바 목록 하이라이트 업데이트
    document.querySelectorAll('#youtubeSummariesList .list-group-item').forEach(item => {
        item.classList.remove('bg-sky-100');
    });
    const activeItem = document.querySelector(`#youtubeSummariesList .list-group-item[onclick*="${videoId}"]`);
    if (activeItem) {
        activeItem.classList.add('bg-sky-100');
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/summary/${videoId}?_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load summary');
        
        const summary = await response.json();
        
        titleContainer.textContent = summary.title;
        metaContainer.innerHTML = `
            <span class="badge bg-info me-2">${summary.channel_name}</span>
            <small class="text-muted">${formatDate(summary.analyzed_at)}</small>
            <a href="${summary.url}" target="_blank" class="btn btn-sm btn-outline-secondary ms-2">
                <i class="bi bi-youtube me-1"></i>영상 보기
            </a>
            <button class="btn btn-sm btn-outline-danger ms-2" onclick="deleteSummary('${videoId}')">
                <i class="bi bi-trash me-1"></i>삭제
            </button>
        `;
        
        if (summary.error) {
            contentContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    분석 중 오류가 발생했습니다: ${escapeHtml(summary.error)}
                </div>
            `;
        } else if (summary.summary) {
            // Markdown을 HTML로 변환 (간단한 변환)
            const htmlContent = convertMarkdownToHtml(summary.summary);
            contentContainer.innerHTML = `
                <div class="summary-content p-4" style="line-height: 1.8; font-size: 0.95rem;">
                    ${htmlContent}
                </div>
            `;
        } else {
            contentContainer.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="bi bi-file-text fs-3"></i>
                    <p class="mt-2 mb-0">요약 내용이 없습니다</p>
                </div>
            `;
        }
        
        // 영상 목록도 새로고침
        loadYoutubeVideos();
        loadYoutubeSummaries();
        
    } catch (error) {
        console.error('Failed to load summary detail:', error);
        contentContainer.innerHTML = `
            <div class="text-center py-5 text-danger">
                <i class="bi bi-exclamation-triangle fs-3"></i>
                <p class="mt-2 mb-0">요약을 불러오는데 실패했습니다</p>
            </div>
        `;
    }
}

/**
 * 요약 삭제
 */
async function deleteSummary(videoId) {
    if (!confirm('이 요약을 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/summary/${videoId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete summary');
        }
        
        showAlert('요약이 삭제되었습니다.', 'success');
        currentSummaryVideoId = null;
        
        // 컨텐츠 영역 초기화
        document.getElementById('summaryTitle').textContent = 'YouTube Summary';
        document.getElementById('summaryMeta').innerHTML = '';
        document.getElementById('summaryContent').innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-youtube fs-1"></i>
                <p class="mt-3 mb-0">왼쪽 목록에서 영상을 선택하거나<br>새 영상을 분석해주세요</p>
            </div>
        `;
        
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to delete summary:', error);
        showAlert('요약 삭제에 실패했습니다: ' + error.message, 'danger');
    }
}

/**
 * 간단한 Markdown -> HTML 변환
 */
function convertMarkdownToHtml(markdown) {
    if (!markdown) return '';
    
    let html = markdown;
    
    // 테이블 변환: |...|...| 형식
    html = html.replace(/^\|(.+)\|$/gm, function(match, content) {
        const cells = content.split('|').map(c => c.trim());
        if (cells.every(c => c.match(/^:?-+:?$/))) {
            // 헤더 구분선
            return '';
        }
        return '<tr>' + cells.map(c => `<td class="px-3 py-2">${c}</td>`).join('') + '</tr>';
    });
    
    // 테이블 감싸기
    html = html.replace(/(<tr>.*<\/tr>\n?)+/g, '<table class="table table-bordered table-striped my-3">$&</table>');
    
    // Bold: **text** -> <strong>text</strong>
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-dark">$1</strong>');
    
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h6 class="mt-4 mb-3 fw-bold text-primary">$1</h6>');
    html = html.replace(/^## (.+)$/gm, '<h5 class="mt-4 mb-3 fw-bold text-primary">$1</h5>');
    html = html.replace(/^# (.+)$/gm, '<h4 class="mt-4 mb-3 fw-bold text-dark">$1</h4>');
    
    // 수평선
    html = html.replace(/^---$/gm, '<hr class="my-4">');
    
    // Bullet points: - text
    html = html.replace(/^- (.+)$/gm, '<li class="mb-2">$1</li>');
    
    // 연속된 리스트 항목을 <ul>로 감싸기
    html = html.replace(/(<li class="mb-2">.*?<\/li>\n?)+/g, '<ul class="list-unstyled ps-3 mb-3">$&</ul>');
    
    // 빈 줄을 단락 구분으로
    html = html.split('\n\n').map(para => {
        para = para.trim();
        if (!para) return '';
        if (para.startsWith('<h') || para.startsWith('<ul') || para.startsWith('<table') || para.startsWith('<hr')) {
            return para;
        }
        return `<p class="mb-3 text-secondary" style="line-height: 1.8;">${para.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');
    
    return html;
}

/**
 * 날짜 포맷팅
 */
function formatDate(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        return date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return isoString;
    }
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================
// 채널 관리 기능
// =============================================

/**
 * 채널 추가 모달 열기
 */
function openAddChannelModal() {
    document.getElementById('newChannelId').value = '';
    document.getElementById('newChannelName').value = '';
    document.getElementById('newChannelPrompt').value = '';
    document.getElementById('newChannelEnabled').checked = true;
    
    if (!addChannelModalInstance) {
        addChannelModalInstance = new bootstrap.Modal(document.getElementById('addChannelModal'));
    }
    addChannelModalInstance.show();
}

/**
 * 채널 추가 제출
 */
async function submitAddChannel() {
    const channelId = document.getElementById('newChannelId').value.trim();
    const channelName = document.getElementById('newChannelName').value.trim();
    const customPrompt = document.getElementById('newChannelPrompt').value.trim();
    const enabled = document.getElementById('newChannelEnabled').checked;
    
    if (!channelId) {
        showAlert('Channel ID를 입력하세요.', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                channel_id: channelId,
                channel_name: channelName,
                custom_prompt: customPrompt,
                enabled: enabled
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add channel');
        }
        
        showAlert('채널이 추가되었습니다!', 'success');
        addChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to add channel:', error);
        showAlert('채널 추가 실패: ' + error.message, 'danger');
    }
}

/**
 * 채널 편집 모달 열기
 */
async function openEditChannelModal(channelId) {
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${channelId}?_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load channel');
        
        const channel = await response.json();
        
        document.getElementById('editChannelId').value = channel.channel_id;
        document.getElementById('editChannelName').value = channel.channel_name || '';
        document.getElementById('editChannelPrompt').value = channel.custom_prompt || '';
        document.getElementById('editChannelEnabled').checked = channel.enabled !== false;
        
        if (!editChannelModalInstance) {
            editChannelModalInstance = new bootstrap.Modal(document.getElementById('editChannelModal'));
        }
        editChannelModalInstance.show();
        
    } catch (error) {
        console.error('Failed to load channel:', error);
        showAlert('채널 정보를 불러오는데 실패했습니다.', 'danger');
    }
}

/**
 * 채널 편집 제출
 */
async function submitEditChannel() {
    const channelId = document.getElementById('editChannelId').value;
    const channelName = document.getElementById('editChannelName').value.trim();
    const customPrompt = document.getElementById('editChannelPrompt').value.trim();
    const enabled = document.getElementById('editChannelEnabled').checked;
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${channelId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                channel_name: channelName,
                custom_prompt: customPrompt,
                enabled: enabled
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update channel');
        }
        
        showAlert('채널이 수정되었습니다!', 'success');
        editChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to update channel:', error);
        showAlert('채널 수정 실패: ' + error.message, 'danger');
    }
}

/**
 * 채널 삭제 (모달에서)
 */
async function deleteChannelFromModal() {
    const channelId = document.getElementById('editChannelId').value;
    
    if (!confirm('이 채널을 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${channelId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete channel');
        }
        
        showAlert('채널이 삭제되었습니다.', 'success');
        editChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to delete channel:', error);
        showAlert('채널 삭제 실패: ' + error.message, 'danger');
    }
}

/**
 * 채널 설정 모달 열기 (기본 프롬프트)
 */
async function openChannelSettingsModal() {
    try {
        const response = await fetch(`${API_BASE}/youtube/prompt/default?_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load default prompt');
        
        const data = await response.json();
        document.getElementById('defaultPromptText').value = data.prompt || '';
        
        if (!channelSettingsModalInstance) {
            channelSettingsModalInstance = new bootstrap.Modal(document.getElementById('channelSettingsModal'));
        }
        channelSettingsModalInstance.show();
        
    } catch (error) {
        console.error('Failed to load settings:', error);
        showAlert('설정을 불러오는데 실패했습니다.', 'danger');
    }
}

/**
 * 기본 프롬프트 저장
 */
async function saveDefaultPrompt() {
    const prompt = document.getElementById('defaultPromptText').value.trim();
    
    if (!prompt) {
        showAlert('프롬프트를 입력하세요.', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/prompt/default`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save prompt');
        }
        
        showAlert('기본 프롬프트가 저장되었습니다!', 'success');
        channelSettingsModalInstance.hide();
        
    } catch (error) {
        console.error('Failed to save default prompt:', error);
        showAlert('프롬프트 저장 실패: ' + error.message, 'danger');
    }
}
