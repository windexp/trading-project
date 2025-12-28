// ===================================
// 공통 유틸리티 함수
// ===================================

// API URL
const API_URL = "/api/v1/strategies";

// 날짜 포맷 함수
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul' });
}

// 날짜+시간 포맷 함수
function formatDateTime(dateString) {
    const dt = new Date(dateString);
    const mmdd = (dt.getMonth()+1).toString().padStart(2,'0') + '/' + dt.getDate().toString().padStart(2,'0');
    const hhmm = dt.getHours().toString().padStart(2,'0') + ':' + dt.getMinutes().toString().padStart(2,'0');
    return { mmdd, hhmm };
}

// 가격 변동률 계산 및 포맷
function formatPriceChange(price, basePrice) {
    if (!basePrice) return { changePercent: 0, changeClass: 'text-muted', changeSymbol: '' };
    const changePercent = (((price - basePrice) / basePrice) * 100).toFixed(2);
    const changeClass = changePercent >= 0 ? 'text-success' : 'text-danger';
    const changeSymbol = changePercent >= 0 ? '▲' : '▼';
    return { changePercent: Math.abs(changePercent), changeClass, changeSymbol };
}

// Status Badge 색상 매핑
function getStatusBadgeClass(status) {
    const statusColorMap = {
        'MANUAL': 'bg-secondary',
        'INIT': 'bg-info',
        'PENDING': 'bg-warning',
        'IN_PROGRESS': 'bg-primary',
        'COMPLETED': 'bg-success',
        'FAILED': 'bg-danger'
    };
    return statusColorMap[(status || '').toUpperCase()] || 'bg-secondary';
}

// 전략 타입 아이콘
function getStrategyIcon(strategyCode) {
    return strategyCode === 'VR' ? '🔄' : '📈';
}

// Status 텍스트 색상
function getStatusClass(status) {
    return status === 'ACTIVE' ? 'bg-success' : 'bg-secondary';
}

// 에러 메시지 표시
function showError(message) {
    alert(message);
}

// 성공 메시지 표시
function showSuccess(message) {
    alert(message);
}

// 확인 대화상자
function confirmAction(message) {
    return confirm(message);
}