const API_BASE = 'http://localhost:5000/api';
let users = [];
let groups = [];
let activeGroup = null;
let activeGroupName = '';
let splitMode = 'equal'; // 'equal' or 'custom'

const usersList = document.getElementById('users-list');
const groupsList = document.getElementById('groups-list');
const expContainer = document.getElementById('expenses-container');
const balList = document.getElementById('balances-list');

// ===========================
// INIT & DATA FETCHING
// ===========================

async function init() {
    await fetchUsers();
    await fetchGroups();
    updateSidebar();
    if (groups.length > 0 && !activeGroup) {
        const firstLi = document.querySelector('#groups-list li');
        selectGroup(groups[0].id, groups[0].name, firstLi);
    }
}


function setStatus(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

async function fetchUsers() {
    const r = await fetch(`${API_BASE}/users`);
    users = await r.json();
}
async function fetchGroups() {
    const r = await fetch(`${API_BASE}/groups`);
    groups = await r.json();
}

// ===========================
// SIDEBAR RENDERING
// ===========================

function updateSidebar() {
    // --- USERS LIST ---
    usersList.innerHTML = '';
    if (users.length === 0) {
        usersList.innerHTML = '<li class="empty-state" style="padding:10px;font-size:12px;">No users yet.</li>';
    } else {
        users.forEach(u => {
            let li = document.createElement('li');
            li.innerHTML = `
                <span class="item-name">${u.name}</span>
                <button class="btn-delete-small" title="Delete user" onclick="confirmDelete('user','${u.id}','${u.name}')">✕</button>
            `;
            usersList.appendChild(li);
        });
    }
    
    // --- GROUPS LIST ---
    groupsList.innerHTML = '';
    if (groups.length === 0) {
        groupsList.innerHTML = '<li class="empty-state" style="padding:10px;font-size:12px;">No groups yet.</li>';
    } else {
        groups.forEach(g => {
            let li = document.createElement('li');
            li.innerHTML = `
                <span class="item-name" onclick="selectGroup('${g.id}','${g.name.replace(/'/g, "\\'")}', this.parentElement)">${g.name}</span>
                <button class="btn-delete-small" title="Delete group" onclick="event.stopPropagation(); confirmDelete('group','${g.id}','${g.name.replace(/'/g, "\\'")}')">✕</button>
            `;
            if (activeGroup === g.id) li.classList.add('active');
            groupsList.appendChild(li);
        });
    }
}

// ===========================
// GROUP SELECTION & VIEW
// ===========================

async function selectGroup(id, name, el) {
    activeGroup = id;
    activeGroupName = name;
    document.getElementById('active-group-name').innerText = name;
    
    document.querySelectorAll('#groups-list li').forEach(l => l.classList.remove('active'));
    if (el) el.classList.add('active');
    
    await refreshGroupView();
}

async function refreshGroupView() {
    if (!activeGroup) return;
    
    // 1. Fetch Expenses History
    const r1 = await fetch(`${API_BASE}/groups/${activeGroup}/expenses`);
    const expenses = await r1.json();
    expContainer.innerHTML = '';
    
    if (expenses.length === 0) {
        expContainer.innerHTML = '<div class="empty-state">No expenses found here yet. Click "Add an expense" to get started!</div>';
    } else {
        expenses.forEach(e => {
            const payerName = users.find(u => u.id === e.created_by)?.name || 'Someone';
            let div = document.createElement('div');
            div.className = 'expense-item';
            
            const dateStr = new Date(e.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            
            div.innerHTML = `
                <div class="expense-date">${dateStr}</div>
                <div class="expense-desc">${e.description}</div>
                <div class="expense-info">${payerName} paid<br><span class="expense-amount">$${parseFloat(e.total_amount).toFixed(2)}</span></div>
                <div class="expense-actions">
                    <button class="btn-delete-expense" title="Delete expense" onclick="confirmDelete('expense','${e.id}','${e.description.replace(/'/g, "\\'")}')">🗑</button>
                </div>
            `;
            expContainer.appendChild(div);
        });
    }

    // 2. Fetch Minimized Graph and Cache
    const r2 = await fetch(`${API_BASE}/groups/${activeGroup}/settle`);
    const graph = await r2.json();
    balList.innerHTML = '';
    
    if (graph.minimized_transactions.length === 0) {
        balList.innerHTML = '<li class="empty-state">Everyone is fully settled up! 🎉</li>';
    } else {
        graph.minimized_transactions.forEach(t => {
            const fName = users.find(u => u.id === t.from)?.name || t.from.substring(0, 6);
            const tName = users.find(u => u.id === t.to)?.name || t.to.substring(0, 6);
            let li = document.createElement('li');
            li.innerHTML = `
                <div class="balance-row">
                    <span><span class="debtor">${fName}</span> <span class="owes-text">owes</span> <span class="creditor">${tName}</span></span>
                    <strong>$${t.amount.toFixed(2)}</strong>
                </div>
            `;
            balList.appendChild(li);
        });
    }
}

// ===========================
// CONFIRM DELETE DIALOG
// ===========================

let pendingDelete = null;

function confirmDelete(type, id, name) {
    pendingDelete = { type, id, name };
    const modal = document.getElementById('modal-confirm');
    document.getElementById('confirm-title').innerText = `Delete ${type.charAt(0).toUpperCase() + type.slice(1)}`;
    
    let msg = '';
    if (type === 'user') {
        msg = `Are you sure you want to delete <strong>${name}</strong>? This will remove them from all groups and erase their expense history.`;
    } else if (type === 'group') {
        msg = `Are you sure you want to delete the group <strong>${name}</strong>? All expenses, settlements, and balances in this group will be permanently deleted.`;
    } else if (type === 'expense') {
        msg = `Are you sure you want to delete the expense <strong>"${name}"</strong>? The balance impacts will be reversed.`;
    }
    document.getElementById('confirm-message').innerHTML = msg;
    modal.classList.add('open');
}

document.getElementById('confirm-ok').onclick = async () => {
    if (!pendingDelete) return;
    const { type, id } = pendingDelete;
    
    try {
        if (type === 'user') {
            await fetch(`${API_BASE}/users/${id}`, { method: 'DELETE' });
            setStatus('User deleted successfully!');
        } else if (type === 'group') {
            await fetch(`${API_BASE}/groups/${id}`, { method: 'DELETE' });
            if (activeGroup === id) {
                activeGroup = null;
                document.getElementById('active-group-name').innerText = 'Select a Group';
                expContainer.innerHTML = '<div class="empty-state">No group selected or no expenses yet.</div>';
                balList.innerHTML = '<li class="empty-state">Select a group to view balances.</li>';
            }
            setStatus('Group deleted successfully!');
        } else if (type === 'expense') {
            await fetch(`${API_BASE}/expenses/${id}?group_id=${activeGroup}`, { method: 'DELETE' });
            setStatus('Expense deleted & balances reversed!');
        }
    } catch (e) {
        setStatus('Error deleting. Try again.');
    }
    
    closeModals();
    pendingDelete = null;
    await init();
    if (activeGroup && type !== 'group') await refreshGroupView();
};

// ===========================
// MODAL LOGIC
// ===========================

window.closeModals = () => {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('open'));
};

document.getElementById('btn-refresh-balances').onclick = refreshGroupView;

// --- ADD GROUP ---
document.getElementById('btn-new-group').onclick = async () => {
    let name = prompt("Group Name:");
    if (name) {
        await fetch(`${API_BASE}/groups`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ name: name, description: 'Created in UI' }) 
        });
        setStatus('Group created!');
        await init();
    }
};

// --- ADD USER (MODAL) ---
document.getElementById('btn-new-user').onclick = () => {
    const modal = document.getElementById('modal-add-user');
    const groupSelect = document.getElementById('new-user-group');
    groupSelect.innerHTML = '<option value="">— No group —</option>';
    groups.forEach(g => {
        groupSelect.innerHTML += `<option value="${g.id}">${g.name}</option>`;
    });
    document.getElementById('new-user-name').value = '';
    document.getElementById('new-user-email').value = '';
    modal.classList.add('open');
};

document.getElementById('submit-new-user').onclick = async () => {
    const name = document.getElementById('new-user-name').value.trim();
    const email = document.getElementById('new-user-email').value.trim();
    const groupId = document.getElementById('new-user-group').value;
    
    if (!name) return alert('Please enter a user name!');
    
    const payload = { 
        name, 
        email: email || name.toLowerCase().replace(/\s+/g, '.') + '@test.com' 
    };
    if (groupId) payload.group_id = groupId;
    
    try {
        await fetch(`${API_BASE}/users`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        closeModals();
        setStatus(groupId ? 'User created & added to group!' : 'User created!');
        await init();
    } catch (e) { setStatus('Error creating user'); }
};

// ===========================
// ADD EXPENSE MODAL
// ===========================

document.getElementById('btn-add-expense').onclick = () => {
    if (!activeGroup) return setStatus("Select a group first!");
    const m = document.getElementById('modal-expense');
    
    // Reset
    document.getElementById('exp-desc').value = '';
    document.getElementById('exp-amount').value = '';
    splitMode = 'equal';
    document.getElementById('btn-split-equal').classList.add('active');
    document.getElementById('btn-split-custom').classList.remove('active');
    document.getElementById('split-equal-section').style.display = '';
    document.getElementById('split-custom-section').style.display = 'none';
    
    const payerSelect = document.getElementById('exp-payer');
    payerSelect.innerHTML = users.map(u => `<option value="${u.id}">${u.name}</option>`).join('');
    
    // Equal split checkboxes
    const equalContainer = document.getElementById('equal-split-users-container');
    equalContainer.innerHTML = users.map(u => `
        <div class="split-user-row">
            <label>
                <input type="checkbox" class="equal-split-check" data-uid="${u.id}" checked>
                ${u.name}
            </label>
        </div>
    `).join('');
    
    updateEqualSplitPreview();
    
    // Custom split inputs
    const splitContainer = document.getElementById('split-users-container');
    splitContainer.innerHTML = users.map(u => `
        <div class="split-user-row">
            <span>${u.name}</span>
            <input type="number" data-uid="${u.id}" class="split-amt-input" value="0" step="0.01">
        </div>
    `).join('');
    
    m.classList.add('open');
};

// Split mode toggles
document.getElementById('btn-split-equal').onclick = () => {
    splitMode = 'equal';
    document.getElementById('btn-split-equal').classList.add('active');
    document.getElementById('btn-split-custom').classList.remove('active');
    document.getElementById('split-equal-section').style.display = '';
    document.getElementById('split-custom-section').style.display = 'none';
};

document.getElementById('btn-split-custom').onclick = () => {
    splitMode = 'custom';
    document.getElementById('btn-split-custom').classList.add('active');
    document.getElementById('btn-split-equal').classList.remove('active');
    document.getElementById('split-equal-section').style.display = 'none';
    document.getElementById('split-custom-section').style.display = '';
};

function updateEqualSplitPreview() {
    const amt = parseFloat(document.getElementById('exp-amount')?.value) || 0;
    const checks = document.querySelectorAll('.equal-split-check:checked');
    const count = checks.length;
    const preview = document.getElementById('equal-split-preview');
    if (preview) {
        if (count > 0 && amt > 0) {
            preview.innerText = `$${(amt / count).toFixed(2)} per person (${count} people)`;
        } else if (count > 0) {
            preview.innerText = `Split between ${count} people`;
        } else {
            preview.innerText = 'Select at least one person';
        }
    }
}

// Live preview updates
document.addEventListener('change', (e) => {
    if (e.target.classList.contains('equal-split-check')) updateEqualSplitPreview();
});
document.addEventListener('input', (e) => {
    if (e.target.id === 'exp-amount') updateEqualSplitPreview();
});

// Submit expense
document.getElementById('submit-expense').onclick = async () => {
    const desc = document.getElementById('exp-desc').value;
    const amt = parseFloat(document.getElementById('exp-amount').value);
    const payer = document.getElementById('exp-payer').value;
    
    if (!desc || !amt || amt <= 0) return alert("Fill out description & valid amount!");

    let splitsDict = {};
    
    if (splitMode === 'equal') {
        const checks = document.querySelectorAll('.equal-split-check:checked');
        if (checks.length === 0) return alert("Select at least one person to split with!");
        const share = Math.round((amt / checks.length) * 100) / 100;
        let totalAssigned = 0;
        const checksArray = Array.from(checks);
        checksArray.forEach((c, index) => {
            if (index === checksArray.length - 1) {
                splitsDict[c.dataset.uid] = Math.round((amt - totalAssigned) * 100) / 100;
            } else {
                splitsDict[c.dataset.uid] = share;
                totalAssigned += share;
            }
        });
    } else {
        let customTotal = 0;
        document.querySelectorAll('.split-amt-input').forEach(i => {
            let v = parseFloat(i.value);
            if (v > 0) {
                splitsDict[i.dataset.uid] = v;
                customTotal += v;
            }
        });
        if (Object.keys(splitsDict).length === 0) return alert("Enter at least one split amount!");
        if (Math.abs(customTotal - amt) > 0.01) return alert(`Custom splits must sum exactly to $${amt.toFixed(2)}. Currently they sum to $${customTotal.toFixed(2)}.`);
    }

    try {
        await fetch(`${API_BASE}/expenses`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                group_id: activeGroup,
                description: desc,
                total_amount: amt,
                created_by: payer,
                payers: { [payer]: amt },
                splits: splitsDict
            })
        });
        closeModals();
        setStatus("Expense Successfully Logged in Supabase!");
        refreshGroupView();
    } catch (e) { setStatus("Error logging expense"); }
};

// ===========================
// SETTLE UP MODAL
// ===========================

document.getElementById('btn-settle-up').onclick = () => {
    if (!activeGroup) return setStatus("Select a group first!");
    const m = document.getElementById('modal-settle');
    
    document.getElementById('settle-payer').innerHTML = users.map(u => `<option value="${u.id}">${u.name}</option>`).join('');
    document.getElementById('settle-payee').innerHTML = users.map(u => `<option value="${u.id}">${u.name}</option>`).join('');
    document.getElementById('settle-amount').value = '';
    
    m.classList.add('open');
};

// Settle All
document.getElementById('btn-settle-all').onclick = async () => {
    if (!activeGroup) return;
    
    if (!confirm(`Are you sure you want to settle ALL debts in "${activeGroupName}"? This will record settlements for every outstanding balance.`)) return;
    
    try {
        const r = await fetch(`${API_BASE}/groups/${activeGroup}/settle-all`, { method: 'POST' });
        const data = await r.json();
        closeModals();
        
        if (data.settlements && data.settlements.length === 0) {
            setStatus("Everyone is already settled up! 🎉");
        } else {
            setStatus(`✅ All debts settled! (${data.settlements?.length || 0} payments recorded)`);
        }
        refreshGroupView();
    } catch (e) { setStatus("Error settling all debts"); }
};

// Manual Settlement
document.getElementById('submit-settlement').onclick = async () => {
    const payer = document.getElementById('settle-payer').value;
    const payee = document.getElementById('settle-payee').value;
    const amt = parseFloat(document.getElementById('settle-amount').value);
    
    if (payer === payee) return alert("You can't pay yourself!");
    if (!amt || amt <= 0) return alert("Amount must be valid.");

    try {
        await fetch(`${API_BASE}/settlements`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_id: activeGroup, from_user: payer, to_user: payee, amount: amt })
        });
        closeModals();
        setStatus("Cash Payment Sent & Graph Updated!");
        refreshGroupView();
    } catch (e) { setStatus("Error processing settlement"); }
};

// ===========================
// KEYBOARD SHORTCUT
// ===========================
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModals();
});

// Start
init();
