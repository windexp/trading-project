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
 * [Refactor] Promise.allSettled 사용: 일부 API 실패 시에도 나머지 데이터는 정상 렌더링
 */
async function loadYoutubeData() {
    const results = await Promise.allSettled([
        loadYoutubeChannels(),
        loadYoutubeVideos(),
        loadYoutubeSummaries()
    ]);
    
    // 실패한 요청이 있으면 로그 출력
    results.forEach((result, index) => {
        if (result.status === 'rejected') {
            const names = ['채널', '영상', '요약'];
            console.error(`${names[index]} 로드 실패:`, result.reason);
        }
    });
}

// 현재 필터 상태
let currentSourceFilter = '';

/**
 * 소스별 필터링
 */
function filterBySource(sourceId) {
    currentSourceFilter = sourceId;
    
    // 모든 채널 항목의 스타일 초기화
    document.querySelectorAll('.source-filter-item').forEach(item => {
        item.classList.remove('bg-sky-100', '!bg-sky-100');
        item.classList.add('hover:bg-gray-50');
    });
    
    // All 버튼 상태 업데이트
    const allBtn = document.getElementById('allSourcesBtn');
    if (allBtn) {
        if (sourceId === '') {
            allBtn.classList.remove('btn-outline-primary');
            allBtn.classList.add('btn-primary');
        } else {
            allBtn.classList.remove('btn-primary');
            allBtn.classList.add('btn-outline-primary');
        }
    }
    
    // 선택된 채널 항목 하이라이트
    if (sourceId) {
        const selectedItem = document.querySelector(`[data-source-id="${sourceId}"]`);
        if (selectedItem) {
            selectedItem.classList.remove('hover:bg-gray-50');
            selectedItem.classList.add('!bg-sky-100');
        }
    }
    
    // 영상 및 요약 목록 재로드
    loadYoutubeVideos();
    loadYoutubeSummaries();
}

/**
 * 필터 상태 복구
 */
function restoreFilterState() {
    if (currentSourceFilter) {
        const selectedItem = document.querySelector(`[data-source-id="${currentSourceFilter}"]`);
        if (selectedItem) {
            selectedItem.classList.remove('hover:bg-gray-50');
            selectedItem.classList.add('!bg-sky-100');
        }
    }
    
    const allBtn = document.getElementById('allSourcesBtn');
    if (allBtn) {
        if (currentSourceFilter === '') {
            allBtn.classList.remove('btn-outline-primary');
            allBtn.classList.add('btn-primary');
        } else {
            allBtn.classList.remove('btn-primary');
            allBtn.classList.add('btn-outline-primary');
        }
    }
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
        
        container.innerHTML = channels.map((channel, index) => {
            const channelType = channel.type || 'channel';
            const identifier = channelType === 'playlist' ? channel.playlist_id : channel.channel_id;
            const isActive = identifier === currentSourceFilter;
            const typeBadge = channelType === 'playlist' 
                ? '<span class="badge bg-info" style="font-size: 0.6rem;">PL</span>' 
                : '<span class="badge bg-primary" style="font-size: 0.6rem;">CH</span>';
            
            return `
            <div class="list-group-item d-flex justify-content-between align-items-center px-3 py-2 ${isActive ? '!bg-sky-100' : 'hover:bg-gray-50'} cursor-pointer source-filter-item" data-source-id="${identifier}" data-channel-index="${index}">
                <div class="d-flex align-items-center gap-2" style="flex: 1;">
                    ${channel.enabled 
                        ? '<i class="bi bi-check-circle-fill text-success"></i>' 
                        : '<i class="bi bi-pause-circle text-muted"></i>'
                    }
                    ${typeBadge}
                    <span class="text-truncate" style="max-width: 110px; font-size: 0.85rem;">${escapeHtml(channel.channel_name)}</span>
                </div>
                <button class="btn btn-sm btn-link p-0 text-muted" onclick="event.stopPropagation(); openEditChannelModal('${identifier}')">
                    <i class="bi bi-pencil"></i>
                </button>
            </div>
            `;
        }).join('');
        
        // 각 채널 항목에 클릭 이벤트 추가
        channels.forEach((channel, index) => {
            const channelType = channel.type || 'channel';
            const identifier = channelType === 'playlist' ? channel.playlist_id : channel.channel_id;
            const element = container.querySelector(`[data-channel-index="${index}"]`);
            if (element) {
                element.addEventListener('click', () => {
                    filterBySource(identifier);
                });
            }
        });
        
        // 현재 필터 상태 부구
        restoreFilterState();
        
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
        const sourceParam = currentSourceFilter ? `&source_id=${currentSourceFilter}` : '';
        
        const response = await fetch(`${API_BASE}/youtube/videos?limit=10${sourceParam}&_t=${Date.now()}`);
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
        
        container.innerHTML = videos.map((video, index) => `
            <div class="list-group-item px-3 py-3 hover:bg-gray-50 cursor-pointer" data-video-index="${index}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2">
                            ${video.is_analyzed 
                                ? '<span class="badge bg-success">분석완료</span>' 
                                : '<span class="badge bg-secondary">미분석</span>'
                            }
                            <small class="text-muted">${escapeHtml(video.channel_name)}</small>
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
        
        // 각 영상 항목에 클릭 이벤트 리스너 추가
        videos.forEach((video, index) => {
            const element = container.querySelector(`[data-video-index="${index}"]`);
            if (element) {
                element.addEventListener('click', () => {
                    handleVideoClick(
                        video.video_id,
                        video.title,
                        video.channel_name,
                        video.is_analyzed,
                        video.source_id || ''
                    );
                });
            }
        });
        
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
        const sourceParam = currentSourceFilter ? `&source_id=${currentSourceFilter}` : '';
        
        const response = await fetch(`${API_BASE}/youtube/summaries?limit=50${sourceParam}&_t=${Date.now()}`);
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
function handleVideoClick(videoId, title, channelName, isAnalyzed, sourceId = '') {
    if (isAnalyzed) {
        loadSummaryDetail(videoId);
    } else {
        analyzeVideo(videoId, title, channelName, sourceId);
    }
}

/**
 * 영상 분석 요청
 * [Refactor] confirm 대신 비동기 확인 함수 사용 (UX 개선)
 */
async function analyzeVideo(videoId, title, channelName, sourceId = '') {
    // [TODO] Bootstrap Modal로 교체 권장 - 현재는 confirm 사용
    const confirmed = await showConfirm(
        '영상 분석',
        `"${title}" 영상을 분석하시겠습니까?\n\n분석에 1-2분 정도 소요될 수 있습니다.`
    );
    if (!confirmed) {
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
                channel_name: channelName,
                source_id: sourceId
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
 * [Refactor] confirm 대신 비동기 확인 함수 사용 (UX 개선)
 */
async function analyzeAllNewVideos() {
    // [TODO] Bootstrap Modal로 교체 권장 - 현재는 confirm 사용
    const confirmed = await showConfirm(
        '전체 영상 분석',
        '분석되지 않은 모든 새 영상을 분석하시겠습니까?\n\n영상 수에 따라 시간이 오래 걸릴 수 있습니다.'
    );
    if (!confirmed) {
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
            let message = `${result.count}개의 영상 분석이 완료되었습니다!`;
            if (result.remaining > 0) {
                message += ` (남은 영상: ${result.remaining}개)`;
            }
            showAlert(message, 'success');
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
            // [SECURITY] innerHTML 사용: XSS 위험 - sanitized된 콘텐츠만 사용
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
 * [Refactor] confirm 대신 비동기 확인 함수 사용 (UX 개선)
 */
async function deleteSummary(videoId) {
    // [TODO] Bootstrap Modal로 교체 권장 - 현재는 confirm 사용
    const confirmed = await showConfirm('요약 삭제', '이 요약을 삭제하시겠습니까?');
    if (!confirmed) {
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
 * Markdown -> HTML 변환 (marked.js 사용)
 * 
 * [SECURITY] marked.js + DOMPurify를 사용하여 안전한 마크다운 렌더링
 * - marked.js: 마크다운 파싱 (https://marked.js.org/)
 * - DOMPurify: XSS 방지를 위한 HTML sanitization (https://github.com/cure53/DOMPurify)
 * 
 * [Refactor] 검증된 라이브러리 사용으로 보안 강화 및 테이블 헤딩 문제 해결
 */
function convertMarkdownToHtml(markdown) {
    if (!markdown) return '';
    
    // [SECURITY] marked.js로 마크다운 파싱
    if (typeof marked === 'undefined') {
        console.error('marked.js가 로드되지 않았습니다.');
        return escapeHtml(markdown);
    }
    
    // marked.js 설정
    marked.setOptions({
        breaks: true, // 줄바꿈을 <br>로 변환
        gfm: true, // GitHub Flavored Markdown 지원
        tables: true // 테이블 지원
    });
    
    // 마크다운을 HTML로 변환
    let html = marked.parse(markdown);
    
    // [SECURITY] DOMPurify로 XSS 공격 방지
    if (typeof DOMPurify !== 'undefined') {
        html = DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'blockquote', 'code', 'pre', 'a'],
            ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'style']
        });
    } else {
        console.warn('DOMPurify가 로드되지 않았습니다. XSS 방어가 약화될 수 있습니다.');
    }
    
    // Bootstrap 스타일 클래스 추가
    html = html.replace(/<table>/g, '<table class="table table-bordered table-striped my-3">');
    html = html.replace(/<h1>/g, '<h1 class="mt-4 mb-3 fw-bold text-dark">');
    html = html.replace(/<h2>/g, '<h2 class="mt-4 mb-3 fw-bold text-primary">');
    html = html.replace(/<h3>/g, '<h3 class="mt-4 mb-3 fw-bold text-primary">');
    html = html.replace(/<h4>/g, '<h4 class="mt-4 mb-3 fw-bold text-primary">');
    html = html.replace(/<h5>/g, '<h5 class="mt-3 mb-2 fw-bold text-primary">');
    html = html.replace(/<h6>/g, '<h6 class="mt-3 mb-2 fw-bold text-primary">');
    html = html.replace(/<p>/g, '<p class="mb-3 text-secondary" style="line-height: 1.8;">');
    html = html.replace(/<ul>/g, '<ul class="ps-3 mb-3">');
    html = html.replace(/<ol>/g, '<ol class="ps-3 mb-3">');
    html = html.replace(/<li>/g, '<li class="mb-2">');
    html = html.replace(/<hr>/g, '<hr class="my-4">');
    html = html.replace(/<strong>/g, '<strong class="text-dark">');
    html = html.replace(/<th>/g, '<th class="px-3 py-2">');
    html = html.replace(/<td>/g, '<td class="px-3 py-2">');
    
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
 * [Refactor] XSS 방지를 위한 필수 유틸리티
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 비동기 확인 다이얼로그
 * [Refactor] confirm() 대체 함수 - 비차단 UI 제공
 * 
 * @param {string} title - 다이얼로그 제목
 * @param {string} message - 확인 메시지
 * @returns {Promise<boolean>} - 사용자 확인 여부
 * 
 * [TODO] 프로덕션에서는 Bootstrap Modal로 구현 권장
 * 현재는 임시로 confirm 사용 (향후 교체 필요)
 */
function showConfirm(title, message) {
    return Promise.resolve(confirm(`[${title}]\n\n${message}`));
}

// =============================================
// 채널 관리 기능
// =============================================

/**
 * 소스 타입에 따라 필드 토글
 */
function toggleSourceFields() {
    const sourceType = document.getElementById('newSourceType').value;
    const channelIdGroup = document.getElementById('newChannelIdGroup');
    const playlistIdGroup = document.getElementById('newPlaylistIdGroup');
    
    if (sourceType === 'playlist') {
        channelIdGroup.style.display = 'none';
        playlistIdGroup.style.display = 'block';
        document.getElementById('newChannelId').removeAttribute('required');
        document.getElementById('newPlaylistId').setAttribute('required', 'required');
    } else {
        channelIdGroup.style.display = 'block';
        playlistIdGroup.style.display = 'none';
        document.getElementById('newChannelId').setAttribute('required', 'required');
        document.getElementById('newPlaylistId').removeAttribute('required');
    }
}

/**
 * 채널 추가 모달 열기
 */
function openAddChannelModal() {
    document.getElementById('newSourceType').value = 'channel';
    document.getElementById('newChannelId').value = '';
    document.getElementById('newPlaylistId').value = '';
    document.getElementById('newChannelName').value = '';
    document.getElementById('newChannelPrompt').value = '';
    document.getElementById('newChannelEnabled').checked = true;
    toggleSourceFields();
    
    if (!addChannelModalInstance) {
        addChannelModalInstance = new bootstrap.Modal(document.getElementById('addChannelModal'));
    }
    addChannelModalInstance.show();
}

/**
 * 채널 추가 제출
 * [Refactor] 입력값 유효성 검사 강화
 */
async function submitAddChannel() {
    const sourceType = document.getElementById('newSourceType').value;
    const channelId = document.getElementById('newChannelId').value.trim();
    const playlistId = document.getElementById('newPlaylistId').value.trim();
    const channelName = document.getElementById('newChannelName').value.trim();
    const customPrompt = document.getElementById('newChannelPrompt').value.trim();
    const enabled = document.getElementById('newChannelEnabled').checked;
    
    // [Refactor] 입력값 검증
    if (sourceType === 'channel' && !channelId) {
        showAlert('Channel ID를 입력하세요.', 'warning');
        return;
    }
    
    if (sourceType === 'playlist' && !playlistId) {
        showAlert('Playlist ID를 입력하세요.', 'warning');
        return;
    }
    
    if (!channelName) {
        showAlert('채널 이름을 입력하세요.', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: sourceType,
                channel_id: channelId,
                playlist_id: playlistId,
                channel_name: channelName,
                custom_prompt: customPrompt,
                enabled: enabled
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add source');
        }
        
        showAlert(`${sourceType === 'playlist' ? '플레이리스트' : '채널'}가 추가되었습니다!`, 'success');
        addChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to add source:', error);
        showAlert('추가 실패: ' + error.message, 'danger');
    }
}

/**
 * 채널 편집 모달 열기
 */
async function openEditChannelModal(identifier) {
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${identifier}?_t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load source');
        
        const channel = await response.json();
        const channelType = channel.type || 'channel';
        const channelId = channelType === 'playlist' ? channel.playlist_id : channel.channel_id;
        
        document.getElementById('editChannelId').value = channelId;
        document.getElementById('editChannelName').value = channel.channel_name || '';
        document.getElementById('editChannelPrompt').value = channel.custom_prompt || '';
        document.getElementById('editChannelEnabled').checked = channel.enabled !== false;
        
        if (!editChannelModalInstance) {
            editChannelModalInstance = new bootstrap.Modal(document.getElementById('editChannelModal'));
        }
        editChannelModalInstance.show();
        
    } catch (error) {
        console.error('Failed to load source:', error);
        showAlert('정보를 불러오는데 실패했습니다.', 'danger');
    }
}

/**
 * 채널 편집 제출
 * [Refactor] 입력값 유효성 검사 추가
 */
async function submitEditChannel() {
    const identifier = document.getElementById('editChannelId').value;
    const channelName = document.getElementById('editChannelName').value.trim();
    const customPrompt = document.getElementById('editChannelPrompt').value.trim();
    const enabled = document.getElementById('editChannelEnabled').checked;
    
    // [Refactor] 필수 입력값 검증
    if (!channelName) {
        showAlert('채널 이름을 입력하세요.', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${identifier}`, {
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
            throw new Error(error.detail || 'Failed to update');
        }
        
        showAlert('수정되었습니다!', 'success');
        editChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to update:', error);
        showAlert('수정 실패: ' + error.message, 'danger');
    }
}

/**
 * 채널 삭제 (모달에서)
 * [Refactor] confirm 대신 비동기 확인 함수 사용 (UX 개선)
 */
async function deleteChannelFromModal() {
    const identifier = document.getElementById('editChannelId').value;
    
    // [TODO] Bootstrap Modal로 교체 권장 - 현재는 confirm 사용
    const confirmed = await showConfirm('채널 삭제', '삭제하시겠습니까?');
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/youtube/channels/${identifier}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete');
        }
        
        showAlert('삭제되었습니다.', 'success');
        editChannelModalInstance.hide();
        await loadYoutubeData();
        
    } catch (error) {
        console.error('Failed to delete:', error);
        showAlert('삭제 실패: ' + error.message, 'danger');
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
 * [Refactor] 입력값 유효성 검사 유지
 */
async function saveDefaultPrompt() {
    const prompt = document.getElementById('defaultPromptText').value.trim();
    
    // [Refactor] 필수 입력값 검증
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
