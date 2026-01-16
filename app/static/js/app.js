// ===================================
// 애플리케이션 초기화 및 전역 변수
// ===================================

// 전역 변수
let currentStrategy = null;
let currentSnapshotId = null;
let createModalInstance = null;
let createSnapshotModalInstance = null;
let priceUpdateInterval = null;
// isSidebarOpen과 toggleSidebar는 index.html에 인라인으로 정의됨

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('Trading Dashboard Initialized');
    loadStrategies();
    
    // 사이드바 네비게이션 버튼 활성화 상태 업데이트
    updateSidebarNav();
});