// ===================================
// 주문 관리 관련 함수
// ===================================

// 스냅샷 주문 목록 렌더링
function renderSnapshotOrders(orders) {
    const tbody = document.getElementById("snapshotOrdersBody");
    
    if (orders.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7' class='text-center text-muted'>No orders in this snapshot.</td></tr>";
        return;
    }
    
    tbody.innerHTML = "";
    orders.forEach(o => {
        const tr = document.createElement("tr");
        
        // 시간 포맷
        const { mmdd, hhmm } = formatDateTime(o.ordered_at);
        
        // Price/Qty: 윗줄 filled, 아랫줄 order (괄호)
        const priceHtml = `<div>${o.order_status !== 'SUBMITTED' ? `${o.filled_price}` : `-` }</div><div style='color:#888;'>(${o.order_price})</div>`;
        const qtyHtml = `<div>${o.order_status !== 'SUBMITTED' ? `${o.filled_qty}` : `-` }</div><div style='color:#888;'>(${o.order_qty})</div>`;
        
        // Type: side + order_type
        const typeHtml = `
            <div style="text-align:center"><span class="badge ${o.order_type === 'BUY' ? 'bg-danger' : 'bg-primary'}">${o.order_type}</span></div>
            <div style='color:#888; font-size:0.85em; margin-top:2px; text-align:center;'>${(o.extra.desc) || '-'}</div>
        `;
        // Status
        const statusHtml = `<span id="order-status-${o.order_id}">${o.order_status}</span>`;
        
        // Actions
        const actionsHtml = `
            <button class="btn btn-xs btn-outline-primary px-2 py-1 me-1" style="font-size:0.8em;" onclick="editOrder('${o.order_id}')">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-xs btn-outline-danger px-2 py-1" style="font-size:0.8em;" onclick="deleteOrder('${o.order_id}')">
                <i class="bi bi-trash"></i>
            </button>
        `;
        // console.log(o);
        // <td><span class="badge ${o.order_type === 'BUY' ? 'bg-danger' : 'bg-primary'}">${o.order_type}</span></td>
        tr.innerHTML = `
            <td style='white-space:pre-line;'>${mmdd}\n${hhmm}</td>
            <td>${typeHtml}</td>
            <td>${o.symbol}</td>
            <td>${priceHtml}</td>
            <td>${qtyHtml}</td>
            <td>${statusHtml}</td>
            <td>${actionsHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

// 주문 편집
async function editOrder(orderId) {
    const statusSpan = document.getElementById(`order-status-${orderId}`);
    if (!statusSpan) return;
    
    const current = statusSpan.textContent;
    const select = document.createElement('select');
    select.className = 'form-select order-status-dropdown';
    select.style.width = '110px';
    
    const statusOptions = ['SUBMITTED','FILLED','PARTIALLY_FILLED','UNFILLED','CANCELLED','REJECTED'];
    statusOptions.forEach(opt => {
        const o = document.createElement('option');
        o.value = opt;
        o.text = opt;
        if (opt === current) o.selected = true;
        select.appendChild(o);
    });
    
    statusSpan.replaceWith(select);
    select.focus();
    
    select.onblur = async function() {
        const newStatus = select.value;
        
        // 원래 상태로 복구
        const newSpan = document.createElement('span');
        newSpan.id = `order-status-${orderId}`;
        newSpan.textContent = newStatus;
        select.replaceWith(newSpan);
        
        // 모든 UI 요소 활성화 및 복구
        restoreUIAfterEdit();
        
        // API 호출
        const res = await fetch(`${API_URL}/orders/${orderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_status: newStatus })
        });
        
        if (res.ok) {
            await openSnapshotModal(currentSnapshotId);
            showSuccess('Order updated successfully');
        } else {
            const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
            showError('Error updating order: ' + (err.detail || 'Unknown error'));
        }
    };
}

// UI 복구 함수
function restoreUIAfterEdit() {
    // snapshot modal 및 메인창 모든 버튼/입력 활성화
    const modal = document.getElementById('snapshotModal');
    if (modal) {
        Array.from(modal.querySelectorAll('button,input,select,textarea')).forEach(el => {
            el.disabled = false;
        });
        modal.style.pointerEvents = '';
        modal.style.opacity = '';
    }
    
    ['dashboard-view', 'strategy-details-view'].forEach(id => {
        const view = document.getElementById(id);
        if (view) {
            Array.from(view.querySelectorAll('button,input,select,textarea')).forEach(el => {
                el.disabled = false;
            });
            view.style.pointerEvents = '';
            view.style.opacity = '';
        }
    });
    
    // overlay 제거
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
}

// 주문 삭제
async function deleteOrder(orderId) {
    if (!confirmAction(`Delete order ${orderId}? This cannot be undone.`)) return;

    const res = await fetch(`${API_URL}/orders/${orderId}`, {
        method: 'DELETE'
    });

    if (res.ok) {
        await openSnapshotModal(currentSnapshotId);
        showSuccess('Order deleted successfully');
    } else {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        showError('Error deleting order: ' + (err.detail || 'Unknown error'));
    }
}