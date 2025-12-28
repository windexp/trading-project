// ===================================
// 대시보드 (전략 리스트) 관련 함수
// ===================================

// 대시보드 뷰로 전환
function showDashboard() {
    document.getElementById("strategy-details-view").classList.remove("active");
    document.getElementById("dashboard-view").classList.add("active");
    currentStrategy = null;
    
    // Clear price update interval
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
        priceUpdateInterval = null;
    }
    
    loadStrategies();
}

// 전략 목록 로드
async function loadStrategies() {
    try {
        const res = await fetch(API_URL);
        const strategies = await res.json();
        const tbody = document.getElementById("strategyListBody");
        tbody.innerHTML = "";

        if (strategies.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-state">
                        <i class="bi bi-inbox"></i>
                        <p class="mb-0">No strategies yet</p>
                        <small>Create your first strategy to get started</small>
                    </td>
                </tr>
            `;
            return;
        }

        strategies.forEach(s => {
            const tr = document.createElement("tr");
            tr.className = "clickable-row";
            tr.onclick = () => showStrategyDetailsView(s);
            
            const typeIcon = getStrategyIcon(s.strategy_code);
            const statusClass = getStatusClass(s.status);
            
            tr.innerHTML = `
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <span style="font-size: 1.2rem;">${typeIcon}</span>
                        <strong>${s.name}</strong>
                    </div>
                </td>
                <td><span class="badge bg-info">${s.strategy_code}</span></td>
                <td><span class="badge ${statusClass}">${s.status}</span></td>
                <td><small class="text-muted">${formatDate(s.created_at)}</small></td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-secondary">
                        <i class="bi bi-chevron-right"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Error loading strategies:", e);
    }
}

// 계정 목록 로드
async function loadAccounts() {
    const res = await fetch("/api/v1/accounts/");
    const accounts = await res.json();
    const select = document.getElementById("accountSelect");
    select.innerHTML = "";
    accounts.forEach(acc => {
        const opt = document.createElement("option");
        opt.value = acc.account_no;
        opt.textContent = acc.account_no;
        select.appendChild(opt);
    });
}

// 전략 생성 모달 열기
function openCreateModal() {
    loadAccounts();
    const el = document.getElementById('createModal');
    if (!createModalInstance) {
        createModalInstance = new bootstrap.Modal(el);
    }
    createModalInstance.show();
}

// 전략 타입별 필드 토글
function toggleCreateFields() {
    const type = document.getElementById("newStrategyType").value;
    document.getElementById("createVrFields").style.display = type === "VR" ? "block" : "none";
    document.getElementById("createInfBuyFields").style.display = type === "InfBuy" ? "block" : "none";
}

// 전략 생성 제출
async function submitCreateStrategy() {
    try {
        const name = document.getElementById("newStrategyName").value;
        const type = document.getElementById("newStrategyType").value;
        const account = document.getElementById("accountSelect").value;
        
        if (!name) { 
            showError("Please enter a strategy name"); 
            return; 
        }
        if (!account) { 
            showError("Please select an account"); 
            return; 
        }

        let params = {};
        if (type === "VR") {
            params = {
                ticker: document.getElementById("vr_ticker").value || "TQQQ",
                is_advanced: document.getElementById("vr_advanced_option").value || "N",
                initial_investment: parseFloat(document.getElementById("vr_initial_investment").value) || 10000,
                periodic_investment: parseFloat(document.getElementById("vr_periodic_investment").value) || 400,
                buy_limit_rate: parseFloat(document.getElementById("vr_buy_limit").value) || 2,
                sell_limit_rate: parseFloat(document.getElementById("vr_sell_limit").value) || 2,
                g_factor: parseFloat(document.getElementById("vr_g").value) || 13,
                u_band: parseFloat(document.getElementById("vr_u_band").value) || 15,
                l_band: parseFloat(document.getElementById("vr_l_band").value) || 15
            };            
        } else if (type === "InfBuy") {
            params = {
                ticker: document.getElementById("inf_ticker").value || "SOXL",
                initial_investment: parseFloat(document.getElementById("inf_investment").value) || 0,
                division: parseInt(document.getElementById("inf_division").value) || 20,
                sell_gain: parseFloat(document.getElementById("inf_sell_gain").value) || 20,
                reinvestment_rate: parseFloat(document.getElementById("inf_reinvestment_rate").value) || 50
            };
        }

        const payload = {
            name: name,
            strategy_code: type,
            account_name: account,
            base_params: params
        };

        const res = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            if (createModalInstance) {
                createModalInstance.hide();
            } else {
                const el = document.getElementById('createModal');
                const modal = bootstrap.Modal.getInstance(el);
                if (modal) modal.hide();
            }
            showDashboard();
        } else {
            const err = await res.json();
            showError("Error: " + (err.detail || "Unknown error"));
        }
    } catch (e) {
        console.error(e);
        showError("Unexpected error: " + e.message);
    }
}