// ===================================
// 애플리케이션 초기화 및 전역 변수
// ===================================

// 전역 변수
let currentStrategy = null;
let currentSnapshotId = null;
let createModalInstance = null;
let createSnapshotModalInstance = null;
let priceUpdateInterval = null;
let isSidebarOpen = false;

// 사이드바 토글 함수
function toggleSidebar() {
    isSidebarOpen = !isSidebarOpen;
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const brandIcon = document.getElementById('brandIcon');
    const brandText = document.getElementById('brandText');
    const sidebarContent = document.getElementById('sidebarContent');
    
    if (isSidebarOpen) {
        sidebar.style.width = '220px';
        mainContent.style.marginLeft = '220px';
        brandIcon.classList.remove('mx-auto');
        brandIcon.classList.add('mr-2');
        brandText.style.display = 'inline';
        sidebarContent.style.display = 'block';
    } else {
        sidebar.style.width = '64px';
        mainContent.style.marginLeft = '64px';
        brandIcon.classList.remove('mr-2');
        brandIcon.classList.add('mx-auto');
        brandText.style.display = 'none';
        sidebarContent.style.display = 'none';
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('Trading Dashboard Initialized');
    loadStrategies();
    
    // 사이드바 네비게이션 버튼 활성화 상태 업데이트
    updateSidebarNav();
});