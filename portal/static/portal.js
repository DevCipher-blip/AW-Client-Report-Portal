let clients = [];
let currentClient = null;
let editingClientId = null;
let currentReportClientId = null;

// ── DATA ──────────────────────────────────────────────────────────────────
async function fetchClients() {
  const res = await fetch(`/api/clients?year=${new Date().getFullYear()}`);
  clients = await res.json();
  renderSidebarClients();
}

async function fetchReports(cid) {
  const res = await fetch(`/api/clients/${cid}/reports`);
  return await res.json();
}

// ── VIEWS ─────────────────────────────────────────────────────────────────
function showView(v, cid) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (v === 'dashboard') {
    document.getElementById('nav-dashboard').classList.add('active');
    renderDashboard();
    setTopbar('Dashboard', 'Overview of all clients and reports', '');
  } else if (v === 'clients') {
    document.getElementById('nav-clients').classList.add('active');
    renderClients();
    setTopbar('All Clients', `${clients.length} clients on retainer`, `<button class="btn btn-primary" onclick="openClientModal()">＋ Add Client</button>`);
  } else if (v === 'client') {
    renderClientDetail(cid);
  }
}

function setTopbar(title, sub, actions) {
  document.getElementById('topbar-title').textContent = title;
  document.getElementById('topbar-sub').textContent = sub;
  document.getElementById('topbar-actions').innerHTML = actions;
}

function renderSidebarClients() {
  const el = document.getElementById('client-list-nav');
  if (clients.length) {
    el.style.display = 'block';
    el.innerHTML = clients.map(c => `
      <div class="client-nav-item" onclick="showView('client','${c.id}')" id="cnav-${c.id}">
        <span>👤</span> ${c.name_1}${c.name_2 ? ' & ' + c.name_2 : ''}
      </div>`).join('');
  }
}

async function renderDashboard() {
  const currentYear = new Date().getFullYear();
  const reportsThisYear = clients.reduce((sum, c) => sum + (c.reports_this_year || 0), 0);

  document.getElementById('content').innerHTML = `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Total Clients</div>
        <div class="stat-value">${clients.length}</div>
        <div class="stat-sub">on retainer</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Reports Generated</div>
        <div class="stat-value">${reportsThisYear}</div>
        <div class="stat-sub">this year</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Next Meetings</div>
        <div class="stat-value">Q${getCurrentQuarter()}</div>
        <div class="stat-sub">${currentYear} cycle</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Time Savings</div>
        <div class="stat-value">~1hr</div>
        <div class="stat-sub">vs full day manually</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Clients</span>
        <button class="btn btn-primary btn-sm" onclick="openClientModal()">＋ Add Client</button>
      </div>
      <div class="card-body">
        ${clients.length ? renderClientCards() : '<div class="empty-state"><div class="icon">🏦</div><h3>No clients yet</h3><p>Add your first client to get started.</p></div>'}
      </div>
    </div>`;
}

function getCurrentQuarter() {
  return Math.ceil((new Date().getMonth() + 1) / 3);
}

function renderClients() {
  document.getElementById('content').innerHTML = `
    <div class="card">
      <div class="card-body">
        ${clients.length ? renderClientCards() : '<div class="empty-state"><div class="icon">🏦</div><h3>No clients yet</h3><p>Add your first client to get started.</p></div>'}
      </div>
    </div>`;
}

function renderClientCards() {
  return `<div class="client-grid">${clients.map(c => `
    <div class="client-card" onclick="showView('client','${c.id}')">
      <div class="client-card-initials">${initials(c.name_1)}</div>
      <div class="client-card-name">${c.name_1}${c.name_2 ? ' & ' + c.name_2 : ''}</div>
      <div class="client-card-sub">Monthly Inflow: $${Number(c.monthly_salary||0).toLocaleString()}</div>
      <div class="client-card-meta">
        <span class="tag tag-blue">${c.name_2 ? 'Married' : 'Single'}</span>
        ${(c.retirement_accounts_1||[]).length ? `<span class="tag tag-gold">${(c.retirement_accounts_1||[]).length + (c.retirement_accounts_2||[]).length} Ret. Accts</span>` : ''}
      </div>
    </div>`).join('')}</div>`;
}

function initials(name) {
  return (name || '').split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase();
}

async function renderClientDetail(cid) {
  currentClient = clients.find(c => String(c.id) === String(cid));
  if (!currentClient) return;
  const reports = await fetchReports(cid);
  const name = `${currentClient.name_1}${currentClient.name_2 ? ' & ' + currentClient.name_2 : ''}`;
  setTopbar(name, 'Client profile & report history',
    `<div style="display:flex;gap:10px">
      <button class="btn btn-outline btn-sm" onclick="openClientModal(${cid})">✏️ Edit</button>
      <button class="btn btn-gold" onclick="openReportModal(${cid})">📋 Generate Report</button>
    </div>`);

  document.querySelectorAll('.client-nav-item').forEach(e => e.classList.remove('active'));
  const nav = document.getElementById(`cnav-${cid}`);
  if (nav) nav.classList.add('active');

  document.getElementById('content').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <div class="card-header"><span class="card-title">Client Information</span></div>
        <div class="card-body">
          ${infoRow('Name', currentClient.name_1)}
          ${currentClient.name_2 ? infoRow('Spouse', currentClient.name_2) : ''}
          ${infoRow('DOB', currentClient.dob_1)}
          ${currentClient.dob_2 ? infoRow('Spouse DOB', currentClient.dob_2) : ''}
          ${infoRow('SSN (last 4)', `xxx-xx-${currentClient.ssn_1||'0000'}`)}
          ${infoRow('Monthly Inflow', '$' + Number(currentClient.monthly_salary||0).toLocaleString())}
          ${infoRow('Monthly Outflow', '$' + Number(currentClient.expense_budget||0).toLocaleString())}
          ${infoRow('Property', currentClient.trust_address || 'N/A')}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Account Structure</span></div>
        <div class="card-body">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:8px">${currentClient.name_1} — Retirement</div>
          ${(currentClient.retirement_accounts_1||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}
          ${currentClient.name_2 ? `
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin:12px 0 8px">${currentClient.name_2} — Retirement</div>
          ${(currentClient.retirement_accounts_2||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}` : ''}
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin:12px 0 8px">Non-Retirement</div>
          ${(currentClient.non_retirement_accounts||[]).map(a => `<div style="padding:6px 10px;background:var(--bg);border-radius:6px;margin-bottom:6px;font-size:13px">${a.type}</div>`).join('') || '<div style="color:var(--muted);font-size:13px">None</div>'}
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Report History</span>
        <button class="btn btn-gold btn-sm" onclick="openReportModal(${cid})">📋 New Report</button>
      </div>
      <div class="card-body">
        ${reports.length ? reports.map(r => `
          <div class="report-row">
            <div>
              <div style="font-weight:600;font-size:14px">${r.quarter} ${r.year}</div>
              <div style="font-size:12px;color:var(--muted)">${new Date(r.created_at).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}</div>
            </div>
            <div style="display:flex;gap:8px">
              <a href="/api/reports/${r.id}/sacs.pdf" target="_blank" class="btn btn-outline btn-sm">⬇ SACS</a>
              <a href="/api/reports/${r.id}/tcc.pdf" target="_blank" class="btn btn-outline btn-sm">⬇ TCC</a>
            </div>
          </div>`).join('') : `<div class="empty-state" style="padding:30px"><div class="icon">📄</div><h3>No reports yet</h3><p>Generate the first report for this client.</p></div>`}
      </div>
    </div>`;
}

function infoRow(label, value) {
  return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">
    <span style="color:var(--muted)">${label}</span>
    <span style="font-weight:500">${value || '—'}</span>
  </div>`;
}

// ── CLIENT MODAL ──────────────────────────────────────────────────────────
function openClientModal(cid) {
  editingClientId = cid || null;
  const existing = cid ? clients.find(c => String(c.id) === String(cid)) : null;
  document.getElementById('client-modal-title').textContent = cid ? 'Edit Client' : 'Add New Client';
  document.getElementById('client-modal-body').innerHTML = buildClientForm(existing);
  document.getElementById('client-modal').classList.add('open');
  if (existing) {
    renderAccountList('ret1-accounts', existing.retirement_accounts_1||[], 'ret1');
    renderAccountList('ret2-accounts', existing.retirement_accounts_2||[], 'ret2');
    renderAccountList('nonret-accounts', existing.non_retirement_accounts||[], 'nonret');
    renderAccountList('liab-accounts', existing.liabilities||[], 'liab');
    toggleSpouse();
  }
}

function closeClientModal() {
  document.getElementById('client-modal').classList.remove('open');
  editingClientId = null;
}

function buildClientForm(d) {
  d = d || {};
  return `
  <div class="section-divider"><span>Primary Client</span></div>
  <div class="form-grid">
    <div class="form-group">
      <label>Full Name *</label>
      <input id="f-name1" value="${d.name_1||''}" placeholder="e.g. John Smith">
    </div>
    <div class="form-group">
      <label>Date of Birth</label>
      <input id="f-dob1" type="date" value="${d.dob_1||''}">
    </div>
    <div class="form-group">
      <label>SSN (last 4 digits)</label>
      <input id="f-ssn1" maxlength="4" value="${d.ssn_1||''}" placeholder="0000">
    </div>
    <div class="form-group">
      <label>Age</label>
      <input id="f-age1" type="number" value="${d.age_1||''}" placeholder="Auto-calculated">
    </div>
  </div>
  <div class="section-divider"><span>Spouse / Partner (optional)</span></div>
  <div style="margin-bottom:12px;display:flex;align-items:center;gap:8px">
    <input type="checkbox" id="has-spouse" onchange="toggleSpouse()" ${d.name_2 ? 'checked' : ''} style="width:auto;padding:0">
    <label for="has-spouse" style="text-transform:none;letter-spacing:0;color:var(--text);font-size:13.5px;cursor:pointer">This client has a spouse / partner</label>
  </div>
  <div id="spouse-fields" style="display:${d.name_2 ? 'block' : 'none'}">
    <div class="form-grid">
      <div class="form-group">
        <label>Spouse Full Name</label>
        <input id="f-name2" value="${d.name_2||''}" placeholder="e.g. Jane Smith">
      </div>
      <div class="form-group">
        <label>Spouse Date of Birth</label>
        <input id="f-dob2" type="date" value="${d.dob_2||''}">
      </div>
      <div class="form-group">
        <label>Spouse SSN (last 4)</label>
        <input id="f-ssn2" maxlength="4" value="${d.ssn_2||''}" placeholder="0000">
      </div>
      <div class="form-group">
        <label>Spouse Age</label>
        <input id="f-age2" type="number" value="${d.age_2||''}" placeholder="Auto-calculated">
      </div>
    </div>
  </div>
  <div class="section-divider"><span>Financial Setup</span></div>
  <div class="form-grid">
    <div class="form-group">
      <label>Monthly Take-Home (Inflow) *</label>
      <input id="f-salary" type="number" value="${d.monthly_salary||''}" placeholder="15000">
    </div>
    <div class="form-group">
      <label>Monthly Expense Budget (Outflow) *</label>
      <input id="f-expenses" type="number" value="${d.expense_budget||''}" placeholder="11000">
    </div>
    <div class="form-group">
      <label>Private Reserve Target</label>
      <input id="f-pr-target" type="number" value="${d.pr_target||''}" placeholder="Auto: 6mo expenses">
    </div>
    <div class="form-group">
      <label>Trust Property Address</label>
      <input id="f-trust-addr" value="${d.trust_address||''}" placeholder="123 Main St, Atlanta GA">
    </div>
  </div>
  <div class="section-divider"><span>${d.name_1||'Client 1'} — Retirement Accounts</span></div>
  <div id="ret1-accounts"></div>
  <button class="btn-add" onclick="addAccount('ret1')">＋ Add Retirement Account</button>

  <div class="section-divider" id="ret2-section"><span id="ret2-label">${d.name_2||'Spouse'} — Retirement Accounts</span></div>
  <div id="ret2-accounts"></div>
  <button class="btn-add" onclick="addAccount('ret2')">＋ Add Spouse Retirement Account</button>

  <div class="section-divider"><span>Non-Retirement Accounts</span></div>
  <div id="nonret-accounts"></div>
  <button class="btn-add" onclick="addAccount('nonret')">＋ Add Non-Retirement Account</button>

  <div class="section-divider"><span>Liabilities</span></div>
  <div id="liab-accounts"></div>
  <button class="btn-add" onclick="addAccount('liab')">＋ Add Liability</button>
  `;
}

function toggleSpouse() {
  const checked = document.getElementById('has-spouse').checked;
  document.getElementById('spouse-fields').style.display = checked ? 'block' : 'none';
}

const accountTypes = {
  ret1: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  ret2: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  nonret: ['Brokerage', 'Joint Brokerage', 'Schwab Brokerage', 'Money Market', 'Savings'],
  liab: ['Mortgage', 'Auto Loan', 'HELOC', 'Student Loan', 'Personal Loan'],
};

function renderAccountList(containerId, accounts, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  accounts.forEach((a, i) => addAccount(type, a));
}

function addAccount(type, existing) {
  const containerId = `${type}-accounts`;
  const el = document.getElementById(containerId);
  const idx = Date.now() + Math.random();
  const opts = accountTypes[type] || [];
  const isLiab = type === 'liab';
  const div = document.createElement('div');
  div.className = 'account-row';
  div.dataset.type = type;
  div.innerHTML = `
    <div class="form-group" style="flex:2">
      <label>Type</label>
      <select class="acct-type">
        ${opts.map(o => `<option ${existing && existing.type===o ? 'selected':''}>${o}</option>`).join('')}
        <option value="custom" ${existing && !opts.includes(existing.type) ? 'selected':''}>Custom...</option>
      </select>
    </div>
    <div class="form-group">
      <label>Acct # (last 4)</label>
      <input class="acct-num" maxlength="4" value="${existing?.acct_num||''}" placeholder="0000">
    </div>
    ${isLiab ? `<div class="form-group"><label>Interest Rate %</label><input class="acct-rate" type="number" step="0.01" value="${existing?.rate||''}" placeholder="3.5"></div>` : ''}
    <button class="btn-icon" onclick="this.parentElement.remove()" title="Remove">✕</button>`;
  el.appendChild(div);
}

function collectAccounts(type) {
  return [...document.querySelectorAll(`#${type}-accounts .account-row`)].map(row => {
    const typeVal = row.querySelector('.acct-type').value;
    const obj = {
      type: typeVal,
      acct_num: row.querySelector('.acct-num')?.value || '',
    };
    const rateEl = row.querySelector('.acct-rate');
    if (rateEl) obj.rate = rateEl.value;
    return obj;
  });
}

async function saveClient() {
  const name1 = document.getElementById('f-name1').value.trim();
  if (!name1) { showToast('Client name is required'); return; }

  const hasSpouse = document.getElementById('has-spouse').checked;
  const data = {
    name_1: name1,
    dob_1: document.getElementById('f-dob1').value,
    ssn_1: document.getElementById('f-ssn1').value,
    age_1: document.getElementById('f-age1').value,
    name_2: hasSpouse ? document.getElementById('f-name2').value : '',
    dob_2: hasSpouse ? document.getElementById('f-dob2').value : '',
    ssn_2: hasSpouse ? document.getElementById('f-ssn2').value : '',
    age_2: hasSpouse ? document.getElementById('f-age2').value : '',
    monthly_salary: document.getElementById('f-salary').value,
    expense_budget: document.getElementById('f-expenses').value,
    pr_target: document.getElementById('f-pr-target').value,
    trust_address: document.getElementById('f-trust-addr').value,
    retirement_accounts_1: collectAccounts('ret1'),
    retirement_accounts_2: collectAccounts('ret2'),
    non_retirement_accounts: collectAccounts('nonret'),
    liabilities: collectAccounts('liab'),
  };

  if (editingClientId) {
    await fetch(`/api/clients/${editingClientId}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    showToast('Client updated!');
  } else {
    await fetch('/api/clients', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    showToast('Client added!');
  }
  closeClientModal();
  await fetchClients();
  showView('clients');
}

// ── REPORT MODAL ──────────────────────────────────────────────────────────
async function openReportModal(cid) {
  currentReportClientId = cid;
  const client = clients.find(c => String(c.id) === String(cid));
  const reports = await fetchReports(cid);
  const last = reports[0] || {};
  const lastData = last;

  const salary = Number(client.monthly_salary || 0);
  const expenses = Number(client.expense_budget || 0);
  const prTarget = Number(client.pr_target || expenses * 6);
  const qtr = `Q${getCurrentQuarter()}`;
  const yr = new Date().getFullYear();

  document.getElementById('report-modal-body').innerHTML = `
    <div style="background:var(--navy);border-radius:10px;padding:16px 20px;margin-bottom:20px;display:flex;gap:24px">
      <div><div class="calc-label">Inflow (Salary)</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${salary.toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Outflow (Budget)</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${expenses.toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Monthly Excess</div><div style="color:#4CAF50;font-family:'DM Serif Display',serif;font-size:20px" id="r-excess-display">$${(salary-expenses).toLocaleString()}/mo</div></div>
      <div><div class="calc-label">Reserve Target</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:20px">$${prTarget.toLocaleString()}</div></div>
    </div>

    <div class="form-grid" style="margin-bottom:16px">
      <div class="form-group">
        <label>Quarter *</label>
        <select id="r-quarter">
          <option ${qtr==='Q1'?'selected':''}>Q1</option>
          <option ${qtr==='Q2'?'selected':''}>Q2</option>
          <option ${qtr==='Q3'?'selected':''}>Q3</option>
          <option ${qtr==='Q4'?'selected':''}>Q4</option>
        </select>
      </div>
      <div class="form-group">
        <label>Year *</label>
        <input id="r-year" type="number" value="${yr}">
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">💰 Cash Flow (SACS)</div>
      <div class="form-grid-3">
        <div class="form-group">
          <label>Private Reserve Balance</label>
          <input id="r-pr-balance" type="number" placeholder="0" value="${lastData.private_reserve_balance||''}">
          ${lastData.private_reserve_balance ? `<div class="prev-val">Last: $${Number(lastData.private_reserve_balance).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Pinnacle Checking Balance</label>
          <input id="r-pinnacle-checking" type="number" placeholder="0" value="${lastData.pinnacle_checking||''}">
          ${lastData.pinnacle_checking ? `<div class="prev-val">Last: $${Number(lastData.pinnacle_checking).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Pinnacle Savings Balance</label>
          <input id="r-pinnacle-savings" type="number" placeholder="0" value="${lastData.pinnacle_savings||''}">
        </div>
        <div class="form-group">
          <label>Schwab Investment Balance</label>
          <input id="r-schwab-balance" type="number" placeholder="0" value="${lastData.schwab_balance||''}">
        </div>
        <div class="form-group">
          <label>Schwab Cash Balance</label>
          <input id="r-schwab-cash" type="number" placeholder="0" value="${lastData.schwab_cash||''}">
        </div>
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">🏛 ${client.name_1} — Retirement Accounts</div>
      <div id="r-ret1-balances">
        ${(client.retirement_accounts_1||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-ret1-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.retirement_1||[])[i]?.balance||''}">
              ${(lastData.retirement_1||[])[i]?.balance ? `<div class="prev-val">Last: $${Number((lastData.retirement_1||[])[i].balance).toLocaleString()}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>
    </div>

    ${client.name_2 ? `<div class="report-section">
      <div class="report-section-title">🏛 ${client.name_2} — Retirement Accounts</div>
      <div id="r-ret2-balances">
        ${(client.retirement_accounts_2||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-ret2-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.retirement_2||[])[i]?.balance||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''}

    <div class="report-section">
      <div class="report-section-title">📈 Non-Retirement Accounts</div>
      <div id="r-nonret-balances">
        ${(client.non_retirement_accounts||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (...${a.acct_num||''})</div>
            <div class="form-group">
              <label>Balance</label>
              <input class="r-nonret-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.non_retirement||[])[i]?.balance||''}">
            </div>
            <div class="form-group">
              <label>Cash Balance</label>
              <input class="r-nonret-cash" type="number" placeholder="0" data-idx="${i}" value="${(lastData.non_retirement||[])[i]?.cash||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">🏠 Trust / Property</div>
      <div class="form-grid">
        <div class="form-group">
          <label>Zillow Zestimate (Home Value)</label>
          <input id="r-trust-value" type="number" placeholder="0" value="${lastData.trust_value||''}">
          ${lastData.trust_value ? `<div class="prev-val">Last: $${Number(lastData.trust_value).toLocaleString()}</div>` : ''}
        </div>
        <div class="form-group">
          <label>Property Address</label>
          <input id="r-trust-address" value="${lastData.trust_address || client.trust_address || ''}">
        </div>
      </div>
    </div>

    <div class="report-section">
      <div class="report-section-title">⚠️ Liabilities</div>
      <div id="r-liab-balances">
        ${(client.liabilities||[]).map((a,i) => `
          <div class="account-row">
            <div style="flex:2;font-weight:500;font-size:13px;padding-bottom:4px">${a.type} (${a.rate||'?'}%)</div>
            <div class="form-group" style="flex:1">
              <label>Balance</label>
              <input class="r-liab-bal" type="number" placeholder="0" data-idx="${i}" value="${(lastData.liabilities||[])[i]?.balance||''}">
            </div>
          </div>`).join('')}
      </div>
    </div>

    <!-- Live totals -->
    <div style="background:var(--navy);border-radius:10px;padding:20px;margin-top:8px">
      <div style="color:rgba(255,255,255,0.5);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:14px">Calculated Totals (TCC)</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px" id="live-totals">
        <div><div class="calc-label">${client.name_1} Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-ret1">$0</div></div>
        ${client.name_2 ? `<div><div class="calc-label">${client.name_2} Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-ret2">$0</div></div>` : ''}
        <div><div class="calc-label">Non-Retirement</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-nonret">$0</div></div>
        <div><div class="calc-label">Trust / Property</div><div style="color:var(--gold);font-family:'DM Serif Display',serif;font-size:18px" id="tot-trust">$0</div></div>
        <div><div class="calc-label">Grand Total Net Worth</div><div style="color:#4CAF50;font-family:'DM Serif Display',serif;font-size:22px;font-weight:bold" id="tot-grand">$0</div></div>
        <div><div class="calc-label">Liabilities (separate)</div><div style="color:#EF5350;font-family:'DM Serif Display',serif;font-size:18px" id="tot-liab">$0</div></div>
      </div>
    </div>`;

  // Live calculation
  const inputs = document.querySelectorAll('#report-modal-body input[type=number]');
  inputs.forEach(inp => inp.addEventListener('input', updateLiveTotals));
  updateLiveTotals();
  document.getElementById('report-modal').classList.add('open');
}

function updateLiveTotals() {
  const getSum = (cls) => [...document.querySelectorAll(`.${cls}`)].reduce((s,e) => s + (Number(e.value)||0), 0);
  const ret1 = getSum('r-ret1-bal');
  const ret2 = getSum('r-ret2-bal');
  const nonret = getSum('r-nonret-bal');
  const trust = Number(document.getElementById('r-trust-value')?.value||0);
  const liab = getSum('r-liab-bal');
  const grand = ret1 + ret2 + nonret + trust;
  const fmt = v => '$' + Math.round(v).toLocaleString();
  if(document.getElementById('tot-ret1')) document.getElementById('tot-ret1').textContent = fmt(ret1);
  if(document.getElementById('tot-ret2')) document.getElementById('tot-ret2').textContent = fmt(ret2);
  if(document.getElementById('tot-nonret')) document.getElementById('tot-nonret').textContent = fmt(nonret);
  if(document.getElementById('tot-trust')) document.getElementById('tot-trust').textContent = fmt(trust);
  if(document.getElementById('tot-grand')) document.getElementById('tot-grand').textContent = fmt(grand);
  if(document.getElementById('tot-liab')) document.getElementById('tot-liab').textContent = fmt(liab);
}

function closeReportModal() {
  document.getElementById('report-modal').classList.remove('open');
}

async function saveReport() {
  const client = clients.find(c => String(c.id) === String(currentReportClientId));
  const salary = Number(client.monthly_salary||0);
  const expenses = Number(client.expense_budget||0);
  const prTarget = Number(client.pr_target || expenses * 6);

  const getBalances = (cls, accounts, extra) => [...document.querySelectorAll(`.${cls}`)].map((el, i) => {
    const obj = { ...accounts[i], balance: el.value };
    if (extra) {
      const cashEl = document.querySelectorAll(`.${extra}`)[i];
      if (cashEl) obj.cash = cashEl.value;
    }
    return obj;
  });

  const data = {
    quarter: document.getElementById('r-quarter').value,
    year: Number(document.getElementById('r-year').value),
    inflow: salary,
    outflow: expenses,
    private_reserve_target: prTarget,
    private_reserve_balance: document.getElementById('r-pr-balance').value,
    pinnacle_checking: document.getElementById('r-pinnacle-checking').value,
    pinnacle_savings: document.getElementById('r-pinnacle-savings').value,
    schwab_balance: document.getElementById('r-schwab-balance').value,
    schwab_cash: document.getElementById('r-schwab-cash').value,
    trust_value: document.getElementById('r-trust-value').value,
    trust_address: document.getElementById('r-trust-address').value,
    retirement_1: getBalances('r-ret1-bal', client.retirement_accounts_1||[]),
    retirement_2: getBalances('r-ret2-bal', client.retirement_accounts_2||[]),
    non_retirement: getBalances('r-nonret-bal', client.non_retirement_accounts||[], 'r-nonret-cash'),
    liabilities: getBalances('r-liab-bal', client.liabilities||[]),
  };

  const res = await fetch(`/api/clients/${currentReportClientId}/reports`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data)
  });
  const { id } = await res.json();
  closeReportModal();
  showToast('Report saved! Downloading PDFs...');
  setTimeout(() => {
    window.open(`/api/reports/${id}/sacs.pdf`, '_blank');
    setTimeout(() => window.open(`/api/reports/${id}/tcc.pdf`, '_blank'), 800);
  }, 300);
  await renderClientDetail(currentReportClientId);
}

// ── UTILS ─────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

// ── INIT ──────────────────────────────────────────────────────────────────
(async () => {
  await fetchClients();
  showView('dashboard');
})();
