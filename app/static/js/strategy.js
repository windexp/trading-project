// ===================================
// 전략 상세 / 스냅샷 관련 함수
// ===================================

// 전략 상세 뷰 표시
function showStrategyDetailsView(strategy) {
    currentStrategy = strategy;
    document.getElementById("dashboard-view").classList.remove("active");
    document.getElementById("strategy-details-view").classList.add("active");

    // Fill Header
    document.getElementById("detailStrategyName").textContent = strategy.name;
    document.getElementById("detailStrategyType").textContent = strategy.strategy_code;
    document.getElementById("detailStrategyStatus").textContent = strategy.status;

    // Fetch and display current price
    fetchCurrentPrice(strategy);

    // Clear any existing interval
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }

    // Update price every 5 seconds
    priceUpdateInterval = setInterval(() => {
        if (currentStrategy) {
            fetchCurrentPrice(currentStrategy);
        }
    }, 5000);

    // Show only the relevant action button (activate/deactivate)
    const deactivateBtn = document.getElementById("deactivateStrategyBtn");
    const activateBtn = document.getElementById("activateStrategyBtn");
    if (strategy.status === "ACTIVE") {
        deactivateBtn.style.display = "block";
        activateBtn.style.display = "none";
    } else {
        deactivateBtn.style.display = "none";
        activateBtn.style.display = "block";
    }

    // Fill Config
    const configStr = JSON.stringify(strategy.base_params, null, 2);
    document.getElementById("detailConfig").textContent = configStr;
    document.getElementById("detailConfigEditor").value = configStr;

    // Reset Config Edit Mode
    cancelStrategyConfig();

    // Load Snapshots
    loadSnapshots();
}

// 현재 가격 가져오기
async function fetchCurrentPrice(strategy) {
    const priceEl = document.getElementById("currentTickerPrice");
    if (!priceEl) return;

    try {
        const ticker = strategy.base_params.ticker;
        if (!ticker) {
            priceEl.innerHTML = '<span class="text-muted">N/A</span>';
            return;
        }

        const res = await fetch(`${API_URL}/${strategy.name}/price`);
        if (res.ok) {
            const data = await res.json();
            if (data.price !== null && data.price !== undefined) {
                const { changePercent, changeClass, changeSymbol } = formatPriceChange(data.price, data.base);
                priceEl.innerHTML = `
                    <div>
                        <strong class="fs-5">$${data.price.toFixed(2)}</strong>
                        <span class="${changeClass} ms-2">${changeSymbol} ${changePercent}%</span>
                    </div>
                    <small class="text-muted">Base: $${data.base ? data.base.toFixed(2) : 'N/A'}</small>
                `;
            } else {
                if (!priceEl.querySelector('.fs-5')) {
                    priceEl.innerHTML = '<span class="text-muted">Price unavailable</span>';
                }
            }
        } else {
            const hasExisting = priceEl.querySelector('.fs-5');
            if (hasExisting) {
                const errorMsg = priceEl.querySelector('.price-error') || document.createElement('div');
                errorMsg.className = 'price-error';
                errorMsg.innerHTML = '<small class="text-danger"><i class="bi bi-exclamation-triangle"></i> Failed to update</small>';
                if (!priceEl.querySelector('.price-error')) {
                    priceEl.appendChild(errorMsg);
                }
                setTimeout(() => errorMsg.remove(), 3000);
            } else {
                priceEl.innerHTML = '<span class="text-danger">Error loading price</span>';
            }
        }
    } catch (e) {
        console.error('Error fetching price:', e);
        const hasExisting = priceEl.querySelector('.fs-5');
        if (hasExisting) {
            const errorMsg = priceEl.querySelector('.price-error') || document.createElement('div');
            errorMsg.className = 'price-error';
            errorMsg.innerHTML = '<small class="text-danger"><i class="bi bi-exclamation-triangle"></i> Connection error</small>';
            if (!priceEl.querySelector('.price-error')) {
                priceEl.appendChild(errorMsg);
            }
            setTimeout(() => errorMsg.remove(), 3000);
        } else {
            priceEl.innerHTML = '<span class="text-danger">Error</span>';
        }
    }
}

// 전략 설정 편집
function editStrategyConfig() {
    document.getElementById("detailConfig").style.display = "none";
    document.getElementById("detailConfigEditor").style.display = "block";

    document.getElementById("editConfigBtn").style.display = "none";
    document.getElementById("saveConfigBtn").style.display = "inline-block";
    document.getElementById("cancelConfigBtn").style.display = "inline-block";
}

// 전략 설정 편집 취소
function cancelStrategyConfig() {
    document.getElementById("detailConfig").style.display = "block";
    document.getElementById("detailConfigEditor").style.display = "none";

    document.getElementById("editConfigBtn").style.display = "inline-block";
    document.getElementById("saveConfigBtn").style.display = "none";
    document.getElementById("cancelConfigBtn").style.display = "none";
}

// 전략 설정 저장
async function saveStrategyConfig() {
    try {
        const newConfig = JSON.parse(document.getElementById("detailConfigEditor").value);

        const res = await fetch(`${API_URL}/${currentStrategy.name}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ base_params: newConfig })
        });

        if (res.ok) {
            const updated = await res.json();
            currentStrategy = updated;

            const configStr = JSON.stringify(updated.base_params, null, 2);
            document.getElementById("detailConfig").textContent = configStr;
            document.getElementById("detailConfigEditor").value = configStr;

            cancelStrategyConfig();
            showSuccess("Configuration updated successfully!");
        } else {
            const err = await res.json();
            showError("Error updating config: " + err.detail);
        }
    } catch (e) {
        showError("Invalid JSON format: " + e.message);
    }
}

// 스냅샷 목록 로드
async function loadSnapshots() {
    if (!currentStrategy) return;
    const res = await fetch(`${API_URL}/${currentStrategy.name}/snapshots`);
    const snapshots = await res.json();
    const tbody = document.getElementById("snapshotListBody");
    tbody.innerHTML = "";

    if (snapshots.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan='5' class='empty-state'>
                    <i class="bi bi-camera"></i>
                    <p class="mb-0">No snapshots yet</p>
                    <small>Run the strategy to generate your first snapshot</small>
                </td>
            </tr>
        `;
        return;
    }

    snapshots.forEach(snap => {
        const tr = document.createElement("tr");
        tr.className = "clickable-row";
        tr.onclick = () => openSnapshotModal(snap.id);

        // Format Progress Summary
        let summary = "";
        if (currentStrategy.strategy_code === "InfBuy") {
            const t = snap.progress.current_t ?? '';
            const inv = snap.progress.investment || 0;
            const equity = snap.progress.equity ?? 0;
            const qty = snap.progress.quantity ?? 0;
            const price = snap.progress.avg_price ?? 0;
            summary = `<div style='font-size:0.92em;line-height:1.2;'>
                <span class="text-muted">T:</span> ${t} <span class="text-muted ms-2">Inv:</span> $${inv.toFixed(0)} <span class="text-muted ms-2">Equity:</span> $${equity.toFixed(0)}<br/>
                <span class="text-muted">Qty:</span> ${qty} <span class="text-muted ms-2">Price:</span> $${price.toFixed(2)}
            </div>`;
        } else {
            const v = snap.progress.current_v || 0;
            const pool = snap.progress.current_pool || 0;
            summary = `<span class="text-muted">V:</span> $${v.toFixed(0)} <span class="text-muted ms-2">Pool:</span> $${pool.toFixed(0)}`;
        }

        const statusClass = getStatusBadgeClass(snap.status);

        let createdDateStr = '';
        let executedDateStr = '';
        
        if (snap.created_at) {
            createdDateStr = formatDate(snap.created_at);
        }
        if (snap.executed_at) {
            executedDateStr = formatDate(snap.executed_at);
        }

        tr.innerHTML = `
            <td><span class="badge bg-secondary">#${snap.id}</span></td>
            <td>
                <div><small>${createdDateStr|| ''}</small></div>
                <div><small class="text-muted">${executedDateStr || ''}</small></div>
            </td>
            <td><span class="fw-medium">Cycle ${snap.cycle}</span></td>
            <td><span class="badge ${statusClass}">${snap.status}</span></td>
            <td>${summary}</td>
        `;
        tbody.appendChild(tr);
    });
}

// 전략 실행
async function runStrategy() {
    if (!currentStrategy) return;
    if (!confirmAction(`Run daily routine for ${currentStrategy.name}?`)) return;

    const res = await fetch(`${API_URL}/start/${currentStrategy.name}`, { method: "POST" });
    const data = await res.json();
    showSuccess(data.message);
    setTimeout(loadSnapshots, 2000);
}

// 전략 삭제
async function deleteStrategy() {
    if (!currentStrategy) return;
    if (!confirmAction("Delete this strategy? This cannot be undone.")) return;

    await fetch(`${API_URL}/${currentStrategy.name}`, { method: "DELETE" });
    showDashboard();
}

// 스냅샷 모달 열기
async function openSnapshotModal(snapshotId) {
    currentSnapshotId = snapshotId;
    const modal = new bootstrap.Modal(document.getElementById('snapshotModal'));
    modal.show();

    cancelSnapshotEdit();

    document.getElementById("snapshotStateData").textContent = "Loading...";
    document.getElementById("snapshotOrdersBody").innerHTML = "";

    const res = await fetch(`${API_URL}/${currentStrategy.name}/snapshots/${snapshotId}`);
    const data = await res.json();

    // Set status dropdown
    const statusSelect = document.getElementById("snapshotDetailStatus");
    if (statusSelect) {
        let stat = data.snapshot.status === 'DONE' ? 'COMPLETED' : data.snapshot.status;
        statusSelect.value = stat;
        statusSelect.disabled = true;
    }

    const jsonStr = JSON.stringify(data.snapshot.progress, null, 2);
    document.getElementById("snapshotStateData").textContent = jsonStr;
    document.getElementById("snapshotStateEditor").value = jsonStr;

    renderSnapshotOrders(data.orders);
}

// 스냅샷 편집 활성화
function enableSnapshotEdit() {
    document.getElementById("snapshotStateData").style.display = "none";
    document.getElementById("snapshotStateEditor").style.display = "block";
    const statusSelect = document.getElementById("snapshotDetailStatus");
    if (statusSelect) statusSelect.disabled = false;

    document.getElementById("editSnapshotBtn").style.display = "none";
    document.getElementById("saveSnapshotBtn").style.display = "inline-block";
    document.getElementById("cancelSnapshotBtn").style.display = "inline-block";
}

// 스냅샷 편집 취소
function cancelSnapshotEdit() {
    document.getElementById("snapshotStateData").style.display = "block";
    document.getElementById("snapshotStateEditor").style.display = "none";
    const statusSelect = document.getElementById("snapshotDetailStatus");
    if (statusSelect) statusSelect.disabled = true;

    document.getElementById("editSnapshotBtn").style.display = "inline-block";
    document.getElementById("saveSnapshotBtn").style.display = "none";
    document.getElementById("cancelSnapshotBtn").style.display = "none";
}

// 스냅샷 편집 저장
async function saveSnapshotEdit() {
    try {
        const newJson = JSON.parse(document.getElementById("snapshotStateEditor").value);
        const statusSelect = document.getElementById("snapshotDetailStatus");
        const newStatus = statusSelect ? statusSelect.value : undefined;
        const body = { progress: newJson };
        if (newStatus) body.status = newStatus;
        const statusText = document.getElementById("snapshotStatusText");
        if (statusText && statusSelect) statusText.style.display = '';

        const res = await fetch(`${API_URL}/${currentStrategy.name}/snapshots/${currentSnapshotId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });

        if (res.ok) {
            const updated = await res.json();
            document.getElementById("snapshotStateData").textContent = JSON.stringify(updated.progress, null, 2);
            cancelSnapshotEdit();
            loadSnapshots();
            showSuccess("Snapshot updated successfully!");
        } else {
            const err = await res.json();
            showError("Error updating snapshot: " + err.detail);
        }
    } catch (e) {
        showError("Invalid JSON format: " + e.message);
    }
}

// 스냅샷 삭제
async function deleteSnapshot() {
    if (!currentStrategy || !currentSnapshotId) return;
    if (!confirmAction(`Delete snapshot #${currentSnapshotId}? This cannot be undone.`)) return;

    const res = await fetch(`${API_URL}/${currentStrategy.name}/snapshots/${currentSnapshotId}`, {
        method: "DELETE"
    });
    if (res.ok) {
        const el = document.getElementById('snapshotModal');
        const modal = bootstrap.Modal.getInstance(el);
        if (modal) modal.hide();
        currentSnapshotId = null;
        await loadSnapshots();
        showSuccess("Snapshot deleted successfully.");
    } else {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        showError("Error deleting snapshot: " + (err.detail || 'Unknown error'));
    }
}

// 스냅샷 생성 모달 열기
function openCreateSnapshotModal() {
    if (!currentStrategy) {
        showError("Select a strategy first");
        return;
    }
    const el = document.getElementById('createSnapshotModal');
    if (!createSnapshotModalInstance) {
        createSnapshotModalInstance = new bootstrap.Modal(el);
    }
    // Reset fields
    document.getElementById('snapshotStatus').value = 'MANUAL';
    document.getElementById('snapshotCycle').value = '';
    document.getElementById('snapshotProgress').value = '';
    createSnapshotModalInstance.show();
}

// 스냅샷 생성 제출
async function submitCreateSnapshot() {
    try {
        const status = document.getElementById('snapshotStatus').value || 'MANUAL';
        const cycleInput = document.getElementById('snapshotCycle').value;
        const progressText = document.getElementById('snapshotProgress').value.trim();

        let progressObj = {};
        if (progressText) {
            progressObj = JSON.parse(progressText);
        }

        const payload = {
            status: status,
            progress: progressObj
        };
        if (cycleInput) {
            payload.cycle = parseInt(cycleInput);
        }

        const res = await fetch(`${API_URL}/${currentStrategy.name}/snapshots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            const el = document.getElementById('createSnapshotModal');
            const modal = createSnapshotModalInstance || bootstrap.Modal.getInstance(el);
            if (modal) modal.hide();
            await loadSnapshots();
            showSuccess('Snapshot created successfully');
        } else {
            const err = await res.json();
            showError('Error creating snapshot: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        showError('Invalid JSON format: ' + e.message);
    }
}