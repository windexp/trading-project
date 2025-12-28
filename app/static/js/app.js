// ===================================
// 애플리케이션 초기화 및 전역 변수
// ===================================

// 전역 변수
let currentStrategy = null;
let currentSnapshotId = null;
let createModalInstance = null;
let createSnapshotModalInstance = null;
let priceUpdateInterval = null;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('Trading Dashboard Initialized');
    loadStrategies();
});