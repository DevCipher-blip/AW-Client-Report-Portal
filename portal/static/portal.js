'use strict';

// Every value that came from the API is passed through esc() before it is
// placed in markup; event handlers are attached here, never inline, so the
// page can run under a script-src 'self' content security policy.

const state = {
  clients: [],
  editingId: null,
  reportClientId: null,
  newReportId: null,
};

const ACCOUNT_TYPES = {
  ret1: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  ret2: ['IRA', 'Roth IRA', '401K', 'Pension', '403b', 'SEP IRA'],
  nonret: ['Brokerage', 'Joint Brokerage', 'Schwab Brokerage', 'Money Market', 'Savings'],
  liab: ['Mortgage', 'Auto Loan', 'HELOC', 'Student Loan', 'Personal Loan'],
};
const ACCOUNT_KEYS = {
  ret1: 'retirement_accounts_1',
  ret2: 'retirement_accounts_2',
  nonret: 'non_retirement_accounts',
  liab: 'liabilities',
};
const FIELD_LABELS = {
  name_1: 'Full name', name_2: 'Spouse name', dob_1: 'Date of birth', dob_2: 'Spouse date of birth',
  ssn_1: 'SSN', ssn_2: 'Spouse SSN', age_1: 'Age', age_2: 'Spouse age',
  monthly_salary: 'Monthly take-home', expense_budget: 'Monthly expenses', pr_target: 'Reserve target',
  year: 'Year', quarter: 'Quarter',
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
  ));
}

const money = v => '$' + Math.round(Number(v) || 0).toLocaleString('en-US');
const householdName = c => (c.name_2 ? `${c.name_1} & ${c.name_2}` : c.name_1);
const currentQuarter = () => Math.ceil((new Date().getMonth() + 1) / 3);
const currentYear = () => new Date().getFullYear();
const initials = name => (name || '').split(/\s+/).filter(Boolean).map(n => n[0]).join('').slice(0, 2).toUpperCase();

let uidCounter = 0;
const uid = prefix => `${prefix}-${++uidCounter}`;

// SQLite stores "YYYY-MM-DD HH:MM:SS" in UTC; Safari will not parse that form directly.
function formatTimestamp(ts) {
  const date = new Date(String(ts).replace(' ', 'T') + 'Z');
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

function ageFrom(dob) {
  const born = new Date(dob + 'T00:00:00');
  if (Number.isNaN(born.getTime())) return '';
  const now = new Date();
  let age = now.getFullYear() - born.getFullYear();
  if (now < new Date(now.getFullYear(), born.getMonth(), born.getDate())) age -= 1;
  return age >= 0 ? age : '';
}

// ── API ────────────────────────────────────────────────────────────────────
class ApiError extends Error {
  constructor(message, fields) {
    super(message);
    this.fields = fields || null;
  }

  describe() {
    if (!this.fields) return this.message;
    return 'Please check: ' + Object.entries(this.fields)
      .map(([key, problem]) => `${FIELD_LABELS[key] || key.replace(/[._]/g, ' ')} ${problem}`)
      .join('; ');
  }
}

async function api(path, { method = 'GET', body } = {}) {
  const options = { method, headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new ApiError('The portal could not be reached. Check your connection and try again.');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(data?.error || `Request failed (${res.status})`, data?.fields);
  return data;
}

async function loadClients() {
  state.clients = await api(`/api/clients?year=${currentYear()}`);
  renderClientNav();
}

const findClient = id => state.clients.find(c => String(c.id) === String(id));

// ── Shell ──────────────────────────────────────────────────────────────────
function setTopbar(title, sub, actions = '') {
  $('#topbar-title').textContent = title;
  $('#topbar-sub').textContent = sub;
  $('#topbar-actions').innerHTML = actions;
  document.title = `${title} · Client Report Portal`;
}

function setContent(html) {
  const content = $('#content');
  content.innerHTML = html;
  content.removeAttribute('aria-busy');
}

function showLoading(message) {
  const content = $('#content');
  content.setAttribute('aria-busy', 'true');
  content.innerHTML = `<p class="state">${esc(message)}</p>`;
}

function errorState(message) {
  return `<div class="state state-error" role="alert">
      <h2>Something went wrong</h2>
      <p>${esc(message)}</p>
      <button type="button" class="btn btn-outline" data-action="retry">Try again</button>
    </div>`;
}

function emptyState(title, body, action = '') {
  return `<div class="state state-empty"><h2>${esc(title)}</h2><p>${esc(body)}</p>${action}</div>`;
}

function markNav(view, clientId) {
  const mark = (el, on) => (on ? el.setAttribute('aria-current', 'page') : el.removeAttribute('aria-current'));
  $$('[data-nav]').forEach(a => mark(a, a.dataset.nav === view));
  $$('#client-nav a').forEach(a => mark(a, a.dataset.client === String(clientId)));
}

function renderClientNav() {
  $('#client-nav').innerHTML = state.clients
    .map(c => `<li><a href="#/clients/${c.id}" data-client="${c.id}">${esc(householdName(c))}</a></li>`)
    .join('');
}

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 4000);
}

// ── Views ──────────────────────────────────────────────────────────────────
async function route() {
  const [, section, id] = location.hash.replace(/^#\/?/, '#/').split('/');
  try {
    if (section === 'clients' && id) await renderClientDetail(id);
    else if (section === 'clients') renderClients();
    else renderDashboard();
  } catch (err) {
    setContent(errorState(err instanceof ApiError ? err.describe() : String(err)));
  }
}

function clientCards() {
  return `<ul class="client-grid">${state.clients.map(c => `
    <li>
      <a class="client-card" href="#/clients/${c.id}">
        <span class="client-initials" aria-hidden="true">${esc(initials(c.name_1))}</span>
        <span class="client-name">${esc(householdName(c))}</span>
        <span class="client-sub">Monthly inflow ${money(c.monthly_salary)}</span>
        <span class="client-meta">
          <span class="tag">${c.name_2 ? 'Joint household' : 'Individual'}</span>
          <span class="tag ${c.last_report ? 'tag-gold' : 'tag-muted'}">${c.last_report ? `Last report ${esc(c.last_report)}` : 'No reports yet'}</span>
        </span>
      </a>
    </li>`).join('')}</ul>`;
}

function noClients() {
  return emptyState(
    'No clients yet',
    'Add a household once; every quarterly report reuses its profile and account structure.',
    '<button type="button" class="btn btn-primary" data-action="new-client">Add the first client</button>',
  );
}

function renderDashboard() {
  markNav('dashboard');
  setTopbar('Dashboard', 'Overview of all clients and reports');
  const cycle = `Q${currentQuarter()} ${currentYear()}`;
  const reportsThisYear = state.clients.reduce((sum, c) => sum + (c.reports_this_year || 0), 0);
  const due = state.clients.filter(c => c.last_report !== cycle).length;
  setContent(`
    <section class="stats" aria-label="Summary">
      <div class="stat"><p class="stat-label">Clients</p><p class="stat-value">${state.clients.length}</p><p class="stat-sub">households on file</p></div>
      <div class="stat"><p class="stat-label">Reports</p><p class="stat-value">${reportsThisYear}</p><p class="stat-sub">generated in ${currentYear()}</p></div>
      <div class="stat"><p class="stat-label">Current cycle</p><p class="stat-value">${cycle}</p><p class="stat-sub">quarterly review</p></div>
      <div class="stat ${due ? 'stat-attention' : ''}"><p class="stat-label">Still due</p><p class="stat-value">${due}</p><p class="stat-sub">without a ${cycle} report</p></div>
    </section>
    <section class="card" aria-labelledby="dash-clients">
      <div class="card-header"><h2 class="card-title" id="dash-clients">Clients</h2></div>
      <div class="card-body">${state.clients.length ? clientCards() : noClients()}</div>
    </section>`);
}

function renderClients() {
  markNav('clients');
  setTopbar('All clients', `${state.clients.length} household${state.clients.length === 1 ? '' : 's'} on file`,
    '<button type="button" class="btn btn-primary" data-action="new-client">Add client</button>');
  setContent(`<section class="card"><div class="card-body">${state.clients.length ? clientCards() : noClients()}</div></section>`);
}

function infoRow(label, value) {
  return `<div class="info-row"><dt>${esc(label)}</dt><dd>${esc(value || '—')}</dd></div>`;
}

function accountList(title, accounts) {
  const items = (accounts || []).map(a => `<li>${esc(a.type)}${a.acct_num ? ` <span class="muted">…${esc(a.acct_num)}</span>` : ''}</li>`).join('');
  return `<h3 class="list-title">${esc(title)}</h3>${items ? `<ul class="account-list">${items}</ul>` : '<p class="muted">None on file</p>'}`;
}

async function renderClientDetail(id) {
  const client = findClient(id);
  markNav('client', id);
  if (!client) {
    setTopbar('Client not found', 'It may have been deleted.');
    setContent(emptyState('Client not found', 'This client is not in the portal any more.', '<a class="btn btn-outline" href="#/clients">Back to clients</a>'));
    return;
  }
  setTopbar(householdName(client), 'Client profile and report history', `
    <button type="button" class="btn btn-outline" data-action="edit-client" data-id="${client.id}">Edit client</button>
    <button type="button" class="btn btn-gold" data-action="new-report" data-id="${client.id}">New report</button>`);
  showLoading('Loading report history…');
  const reports = await api(`/api/clients/${client.id}/reports`);

  const history = reports.length
    ? `<ul class="report-list">${reports.map(r => `
        <li class="report-row ${r.id === state.newReportId ? 'is-new' : ''}">
          <div>
            <p class="report-period">${esc(r.quarter)} ${esc(r.year)}${r.id === state.newReportId ? ' <span class="tag tag-gold">Just saved</span>' : ''}</p>
            <p class="muted">${esc(formatTimestamp(r.created_at))}</p>
          </div>
          <div class="report-actions">
            <a class="btn btn-outline btn-sm" href="/api/reports/${r.id}/sacs.pdf" target="_blank" rel="noopener">SACS PDF</a>
            <a class="btn btn-outline btn-sm" href="/api/reports/${r.id}/tcc.pdf" target="_blank" rel="noopener">TCC PDF</a>
          </div>
        </li>`).join('')}</ul>`
    : emptyState('No reports yet', 'Enter this quarter’s balances to produce the SACS and TCC PDFs.',
      `<button type="button" class="btn btn-gold" data-action="new-report" data-id="${client.id}">Create the first report</button>`);

  setContent(`
    <div class="detail-grid">
      <section class="card" aria-labelledby="info-title">
        <div class="card-header"><h2 class="card-title" id="info-title">Client information</h2></div>
        <dl class="card-body info-list">
          ${infoRow('Name', client.name_1)}
          ${client.name_2 ? infoRow('Spouse', client.name_2) : ''}
          ${infoRow('Date of birth', client.dob_1)}
          ${client.name_2 ? infoRow('Spouse date of birth', client.dob_2) : ''}
          ${infoRow('SSN (last 4)', client.ssn_1 ? `xxx-xx-${client.ssn_1}` : '')}
          ${infoRow('Monthly inflow', money(client.monthly_salary))}
          ${infoRow('Monthly outflow', money(client.expense_budget))}
          ${infoRow('Property', client.trust_address)}
        </dl>
      </section>
      <section class="card" aria-labelledby="acct-title">
        <div class="card-header"><h2 class="card-title" id="acct-title">Account structure</h2></div>
        <div class="card-body">
          ${accountList(`${client.name_1} — retirement`, client.retirement_accounts_1)}
          ${client.name_2 ? accountList(`${client.name_2} — retirement`, client.retirement_accounts_2) : ''}
          ${accountList('Non-retirement', client.non_retirement_accounts)}
          ${accountList('Liabilities', client.liabilities)}
        </div>
      </section>
    </div>
    <section class="card" aria-labelledby="history-title">
      <div class="card-header"><h2 class="card-title" id="history-title">Report history</h2></div>
      <div class="card-body">${history}</div>
    </section>`);
}

// ── Dialog helpers ─────────────────────────────────────────────────────────
function openDialog(dialog) {
  $('.form-error', dialog).hidden = true;
  dialog.showModal();
  const first = $('.dialog-body input, .dialog-body select', dialog);
  if (first) first.focus();
}

function showFormError(dialog, err) {
  const box = $('.form-error', dialog);
  box.textContent = err instanceof ApiError ? err.describe() : String(err);
  box.hidden = false;
}

async function whileBusy(button, label, task) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function field(id, label, value, attrs = '') {
  return `<div class="form-group">
      <label for="${id}">${esc(label)}</label>
      <input id="${id}" name="${id}" value="${esc(value)}" ${attrs}>
    </div>`;
}

// ── Client dialog ──────────────────────────────────────────────────────────
function accountRow(kind, acct = {}) {
  const options = ACCOUNT_TYPES[kind];
  const isCustom = Boolean(acct.type) && !options.includes(acct.type);
  const typeId = uid('acct-type');
  const customId = uid('acct-custom');
  const numId = uid('acct-num');
  const rateId = uid('acct-rate');
  return `<div class="account-row" data-kind="${kind}">
      <div class="form-group grow">
        <label for="${typeId}">Type</label>
        <select id="${typeId}" class="acct-type">
          ${options.map(o => `<option ${acct.type === o ? 'selected' : ''}>${esc(o)}</option>`).join('')}
          <option value="" ${isCustom ? 'selected' : ''}>Other…</option>
        </select>
      </div>
      <div class="form-group grow acct-custom-group" ${isCustom ? '' : 'hidden'}>
        <label for="${customId}">Account name</label>
        <input id="${customId}" class="acct-custom" maxlength="60" value="${esc(isCustom ? acct.type : '')}">
      </div>
      <div class="form-group">
        <label for="${numId}">Acct # (last 4)</label>
        <input id="${numId}" class="acct-num" inputmode="numeric" pattern="\\d{0,4}" maxlength="4" value="${esc(acct.acct_num)}" placeholder="0000">
      </div>
      ${kind === 'liab' ? `<div class="form-group">
        <label for="${rateId}">Interest rate %</label>
        <input id="${rateId}" class="acct-rate" type="number" step="0.01" min="0" value="${esc(acct.rate)}" placeholder="3.5">
      </div>` : ''}
      <button type="button" class="btn-icon" data-action="remove-account" aria-label="Remove this account">&times;</button>
    </div>`;
}

function accountSection(kind, title, accounts, addLabel, extraClass = '') {
  return `<fieldset class="form-section ${extraClass}">
      <legend>${esc(title)}</legend>
      <div class="account-rows" data-rows="${kind}">${(accounts || []).map(a => accountRow(kind, a)).join('')}</div>
      <button type="button" class="btn-add" data-action="add-account" data-kind="${kind}"><span aria-hidden="true">+</span> ${esc(addLabel)}</button>
    </fieldset>`;
}

function clientFormHtml(d = {}) {
  return `
    <fieldset class="form-section">
      <legend>Primary client</legend>
      <div class="form-grid">
        ${field('f-name1', 'Full name (required)', d.name_1, 'required maxlength="120" autocomplete="off" placeholder="e.g. Dana Whitfield"')}
        ${field('f-dob1', 'Date of birth', d.dob_1, 'type="date" data-age-target="f-age1"')}
        ${field('f-ssn1', 'SSN (last 4 digits)', d.ssn_1, 'inputmode="numeric" pattern="\\d{0,4}" maxlength="4" placeholder="0000"')}
        ${field('f-age1', 'Age', d.age_1, 'type="number" min="0" max="130" placeholder="Filled from date of birth"')}
      </div>
    </fieldset>
    <fieldset class="form-section">
      <legend>Spouse or partner</legend>
      <div class="checkbox-row">
        <input type="checkbox" id="has-spouse" ${d.name_2 ? 'checked' : ''}>
        <label for="has-spouse">This client has a spouse or partner</label>
      </div>
      <div id="spouse-fields" class="form-grid" ${d.name_2 ? '' : 'hidden'}>
        ${field('f-name2', 'Spouse full name', d.name_2, 'maxlength="120" autocomplete="off"')}
        ${field('f-dob2', 'Spouse date of birth', d.dob_2, 'type="date" data-age-target="f-age2"')}
        ${field('f-ssn2', 'Spouse SSN (last 4)', d.ssn_2, 'inputmode="numeric" pattern="\\d{0,4}" maxlength="4" placeholder="0000"')}
        ${field('f-age2', 'Spouse age', d.age_2, 'type="number" min="0" max="130"')}
      </div>
    </fieldset>
    <fieldset class="form-section">
      <legend>Financial setup</legend>
      <div class="form-grid">
        ${field('f-salary', 'Monthly take-home (inflow)', d.monthly_salary, 'type="number" min="0" step="any" placeholder="15000"')}
        ${field('f-expenses', 'Monthly expense budget (outflow)', d.expense_budget, 'type="number" min="0" step="any" placeholder="11000"')}
        ${field('f-pr-target', 'Private reserve target', d.pr_target, 'type="number" min="0" step="any" placeholder="Defaults to 6 × monthly expenses"')}
        ${field('f-trust-addr', 'Trust property address', d.trust_address, 'maxlength="200" placeholder="e.g. 14 Juniper Lane"')}
      </div>
    </fieldset>
    ${accountSection('ret1', 'Primary client — retirement accounts', d.retirement_accounts_1, 'Add retirement account')}
    ${accountSection('ret2', 'Spouse — retirement accounts', d.retirement_accounts_2, 'Add spouse retirement account', 'spouse-only')}
    ${accountSection('nonret', 'Non-retirement accounts', d.non_retirement_accounts, 'Add non-retirement account')}
    ${accountSection('liab', 'Liabilities', d.liabilities, 'Add liability')}`;
}

function syncSpouse() {
  const on = $('#has-spouse').checked;
  $('#spouse-fields').hidden = !on;
  $('#client-form .spouse-only').hidden = !on;
}

function openClientDialog(id) {
  const existing = id ? findClient(id) : null;
  state.editingId = existing ? existing.id : null;
  const dialog = $('#client-dialog');
  $('#client-dialog-title').textContent = existing ? `Edit ${householdName(existing)}` : 'Add client';
  $('#client-form-body').innerHTML = clientFormHtml(existing || {});
  $('[data-action="delete-client"]', dialog).hidden = !existing;
  syncSpouse();
  openDialog(dialog);
}

function collectAccounts(kind) {
  return $$(`#client-form [data-rows="${kind}"] .account-row`).map(row => {
    const select = $('.acct-type', row);
    const account = {
      type: select.value || $('.acct-custom', row).value.trim() || 'Other',
      acct_num: $('.acct-num', row).value.trim(),
    };
    const rate = $('.acct-rate', row);
    if (rate) account.rate = rate.value;
    return account;
  });
}

function collectClient() {
  const value = id => $(`#${id}`).value.trim();
  const spouse = $('#has-spouse').checked;
  return {
    name_1: value('f-name1'),
    dob_1: value('f-dob1'),
    ssn_1: value('f-ssn1'),
    age_1: value('f-age1'),
    name_2: spouse ? value('f-name2') : '',
    dob_2: spouse ? value('f-dob2') : '',
    ssn_2: spouse ? value('f-ssn2') : '',
    age_2: spouse ? value('f-age2') : '',
    monthly_salary: value('f-salary'),
    expense_budget: value('f-expenses'),
    pr_target: value('f-pr-target'),
    trust_address: value('f-trust-addr'),
    non_retirement_accounts: collectAccounts('nonret'),
    liabilities: collectAccounts('liab'),
    retirement_accounts_1: collectAccounts('ret1'),
    retirement_accounts_2: spouse ? collectAccounts('ret2') : [],
  };
}

async function saveClient(event) {
  event.preventDefault();
  const dialog = $('#client-dialog');
  const data = collectClient();
  if (!data.name_1) {
    showFormError(dialog, 'Enter the client’s full name.');
    $('#f-name1').focus();
    return;
  }
  try {
    const saved = await whileBusy(event.submitter || $('[type=submit]', dialog), 'Saving…', () => (
      state.editingId
        ? api(`/api/clients/${state.editingId}`, { method: 'PUT', body: data })
        : api('/api/clients', { method: 'POST', body: data })
    ));
    dialog.close();
    await loadClients();
    showToast(state.editingId ? 'Client updated.' : 'Client added.');
    if (location.hash === `#/clients/${saved.id}`) await route();
    else location.hash = `#/clients/${saved.id}`;
  } catch (err) {
    showFormError(dialog, err);
  }
}

async function deleteClient() {
  const client = findClient(state.editingId);
  if (!client || !confirm(`Delete ${householdName(client)} and all of their reports? This cannot be undone.`)) return;
  const dialog = $('#client-dialog');
  try {
    await api(`/api/clients/${client.id}`, { method: 'DELETE' });
    dialog.close();
    await loadClients();
    showToast('Client deleted.');
    location.hash = '#/clients';
  } catch (err) {
    showFormError(dialog, err);
  }
}

// ── Report dialog ──────────────────────────────────────────────────────────
function amountField(id, label, value, previous, attrs = '') {
  return `<div class="form-group">
      <label for="${id}">${esc(label)}</label>
      <input id="${id}" type="number" step="any" min="0" placeholder="0" value="${esc(value)}" ${attrs}>
      ${previous ? `<p class="prev-val">Last report: ${money(previous)}</p>` : ''}
    </div>`;
}

function balanceRows(listKey, accounts, previous, withCash = false) {
  if (!accounts?.length) {
    return '<p class="muted">No accounts on file. Edit the client to add them.</p>';
  }
  return accounts.map((a, i) => {
    const last = (previous || [])[i] || {};
    const label = `${a.type}${a.acct_num ? ` (…${a.acct_num})` : ''}`;
    const balId = uid('bal');
    const cashId = uid('cash');
    return `<div class="account-row">
        <p class="account-label grow">${esc(label)}${a.rate !== undefined && a.rate !== '' ? ` <span class="muted">${esc(a.rate)}%</span>` : ''}</p>
        <div class="form-group">
          <label for="${balId}">Balance</label>
          <input id="${balId}" type="number" step="any" min="0" placeholder="0" data-list="${listKey}" data-idx="${i}" data-part="balance" value="${esc(last.balance)}">
          ${last.balance ? `<p class="prev-val">Last report: ${money(last.balance)}</p>` : ''}
        </div>
        ${withCash ? `<div class="form-group">
          <label for="${cashId}">Cash balance</label>
          <input id="${cashId}" type="number" step="any" min="0" placeholder="0" data-list="${listKey}" data-idx="${i}" data-part="cash" value="${esc(last.cash)}">
        </div>` : ''}
      </div>`;
  }).join('');
}

function reportFormHtml(client, last) {
  const salary = Number(client.monthly_salary || 0);
  const expenses = Number(client.expense_budget || 0);
  const target = Number(client.pr_target || expenses * 6);
  const quarter = `Q${currentQuarter()}`;
  return `
    <div class="calc-strip">
      <div><p class="calc-label">Inflow</p><p class="calc-value">${money(salary)}/mo</p></div>
      <div><p class="calc-label">Outflow</p><p class="calc-value">${money(expenses)}/mo</p></div>
      <div><p class="calc-label">Monthly excess</p><p class="calc-value calc-positive">${money(salary - expenses)}/mo</p></div>
      <div><p class="calc-label">Reserve target</p><p class="calc-value">${money(target)}</p></div>
    </div>
    <div class="form-grid">
      <div class="form-group">
        <label for="r-quarter">Quarter</label>
        <select id="r-quarter">${['Q1', 'Q2', 'Q3', 'Q4'].map(q => `<option ${q === quarter ? 'selected' : ''}>${q}</option>`).join('')}</select>
      </div>
      ${field('r-year', 'Year', currentYear(), 'type="number" min="2000" max="2100" required')}
    </div>
    <fieldset class="form-section panel">
      <legend>Cash flow (SACS)</legend>
      <div class="form-grid form-grid-3">
        ${amountField('r-pr-balance', 'Private reserve balance', last.private_reserve_balance, last.private_reserve_balance)}
        ${amountField('r-pinnacle-checking', 'Pinnacle checking', last.pinnacle_checking, last.pinnacle_checking)}
        ${amountField('r-pinnacle-savings', 'Pinnacle savings', last.pinnacle_savings, last.pinnacle_savings)}
        ${amountField('r-schwab-balance', 'Schwab investment balance', last.schwab_balance, last.schwab_balance)}
        ${amountField('r-schwab-cash', 'Schwab cash balance', last.schwab_cash, last.schwab_cash)}
      </div>
    </fieldset>
    <fieldset class="form-section panel">
      <legend>${esc(client.name_1)} — retirement</legend>
      ${balanceRows('retirement_1', client.retirement_accounts_1, last.retirement_1)}
    </fieldset>
    ${client.name_2 ? `<fieldset class="form-section panel">
      <legend>${esc(client.name_2)} — retirement</legend>
      ${balanceRows('retirement_2', client.retirement_accounts_2, last.retirement_2)}
    </fieldset>` : ''}
    <fieldset class="form-section panel">
      <legend>Non-retirement accounts</legend>
      ${balanceRows('non_retirement', client.non_retirement_accounts, last.non_retirement, true)}
    </fieldset>
    <fieldset class="form-section panel">
      <legend>Trust / property</legend>
      <div class="form-grid">
        ${amountField('r-trust-value', 'Zillow Zestimate (home value)', last.trust_value, last.trust_value)}
        ${field('r-trust-address', 'Property address', last.trust_address || client.trust_address, 'maxlength="200"')}
      </div>
    </fieldset>
    <fieldset class="form-section panel">
      <legend>Liabilities</legend>
      ${balanceRows('liabilities', client.liabilities, last.liabilities)}
    </fieldset>
    <section class="totals" aria-labelledby="totals-title">
      <h3 class="calc-label" id="totals-title">Calculated totals (TCC)</h3>
      <div class="totals-grid" aria-live="polite">
        <div><p class="calc-label">${esc(client.name_1)} retirement</p><p class="calc-value" data-total="retirement_1">$0</p></div>
        ${client.name_2 ? `<div><p class="calc-label">${esc(client.name_2)} retirement</p><p class="calc-value" data-total="retirement_2">$0</p></div>` : ''}
        <div><p class="calc-label">Non-retirement</p><p class="calc-value" data-total="non_retirement">$0</p></div>
        <div><p class="calc-label">Trust / property</p><p class="calc-value" data-total="trust">$0</p></div>
        <div><p class="calc-label">Grand total net worth</p><p class="calc-value calc-positive calc-big" data-total="grand">$0</p></div>
        <div><p class="calc-label">Liabilities (separate)</p><p class="calc-value calc-negative" data-total="liabilities">$0</p></div>
      </div>
    </section>`;
}

function sumList(listKey) {
  return $$(`#report-form [data-list="${listKey}"][data-part="balance"]`).reduce((s, el) => s + (Number(el.value) || 0), 0);
}

function updateTotals() {
  const totals = {
    retirement_1: sumList('retirement_1'),
    retirement_2: sumList('retirement_2'),
    non_retirement: sumList('non_retirement'),
    trust: Number($('#r-trust-value')?.value) || 0,
    liabilities: sumList('liabilities'),
  };
  totals.grand = totals.retirement_1 + totals.retirement_2 + totals.non_retirement + totals.trust;
  $$('#report-form [data-total]').forEach(el => { el.textContent = money(totals[el.dataset.total]); });
}

async function openReportDialog(id, button) {
  const client = findClient(id);
  if (!client) return;
  state.reportClientId = client.id;
  try {
    const reports = await whileBusy(button, 'Loading…', () => api(`/api/clients/${client.id}/reports`));
    $('#report-dialog-title').textContent = `New report — ${householdName(client)}`;
    $('#report-form-body').innerHTML = reportFormHtml(client, reports[0] || {});
    updateTotals();
    openDialog($('#report-dialog'));
  } catch (err) {
    showToast(err instanceof ApiError ? err.describe() : String(err));
  }
}

function collectBalances(listKey, accounts) {
  return (accounts || []).map((account, i) => {
    const entry = { ...account };
    $$(`#report-form [data-list="${listKey}"][data-idx="${i}"]`).forEach(el => { entry[el.dataset.part] = el.value; });
    return entry;
  });
}

async function saveReport(event) {
  event.preventDefault();
  const dialog = $('#report-dialog');
  const client = findClient(state.reportClientId);
  const expenses = Number(client.expense_budget || 0);
  const value = id => $(`#${id}`).value;
  const data = {
    quarter: value('r-quarter'),
    year: Number(value('r-year')),
    inflow: Number(client.monthly_salary || 0),
    outflow: expenses,
    private_reserve_target: Number(client.pr_target || expenses * 6),
    private_reserve_balance: value('r-pr-balance'),
    pinnacle_checking: value('r-pinnacle-checking'),
    pinnacle_savings: value('r-pinnacle-savings'),
    schwab_balance: value('r-schwab-balance'),
    schwab_cash: value('r-schwab-cash'),
    trust_value: value('r-trust-value'),
    trust_address: value('r-trust-address').trim(),
    retirement_1: collectBalances('retirement_1', client.retirement_accounts_1),
    retirement_2: client.name_2 ? collectBalances('retirement_2', client.retirement_accounts_2) : [],
    non_retirement: collectBalances('non_retirement', client.non_retirement_accounts),
    liabilities: collectBalances('liabilities', client.liabilities),
  };
  try {
    const { id } = await whileBusy(event.submitter || $('[type=submit]', dialog), 'Saving…', () => (
      api(`/api/clients/${client.id}/reports`, { method: 'POST', body: data })
    ));
    dialog.close();
    state.newReportId = id;
    await loadClients();
    showToast(`${data.quarter} ${data.year} report saved. Download the PDFs from the history below.`);
    if (location.hash === `#/clients/${client.id}`) await route();
    else location.hash = `#/clients/${client.id}`;
  } catch (err) {
    showFormError(dialog, err);
  }
}

// ── Events ─────────────────────────────────────────────────────────────────
const ACTIONS = {
  'new-client': () => openClientDialog(null),
  'edit-client': el => openClientDialog(el.dataset.id),
  'delete-client': () => deleteClient(),
  'new-report': el => openReportDialog(el.dataset.id, el),
  'close-dialog': el => el.closest('dialog').close(),
  'add-account': el => {
    const rows = $(`#client-form [data-rows="${el.dataset.kind}"]`);
    rows.insertAdjacentHTML('beforeend', accountRow(el.dataset.kind));
    $('.account-row:last-child select', rows).focus();
  },
  'remove-account': el => el.closest('.account-row').remove(),
  retry: () => init(),
};

document.addEventListener('click', event => {
  const el = event.target.closest('[data-action]');
  if (el && ACTIONS[el.dataset.action]) ACTIONS[el.dataset.action](el);
});

document.addEventListener('change', event => {
  const el = event.target;
  if (el.id === 'has-spouse') syncSpouse();
  if (el.classList.contains('acct-type')) {
    const custom = $('.acct-custom-group', el.closest('.account-row'));
    custom.hidden = el.value !== '';
    if (!custom.hidden) $('input', custom).focus();
  }
  if (el.dataset.ageTarget && el.value) {
    const age = $(`#${el.dataset.ageTarget}`);
    if (age && !age.value) age.value = ageFrom(el.value);
  }
});

async function init() {
  showLoading('Loading clients…');
  try {
    await loadClients();
    await route();
  } catch (err) {
    setTopbar('Client Report Portal', '');
    setContent(errorState(err instanceof ApiError ? err.describe() : String(err)));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  $('#client-form').addEventListener('submit', saveClient);
  $('#report-form').addEventListener('submit', saveReport);
  $('#report-form').addEventListener('input', updateTotals);
  window.addEventListener('hashchange', route);
  init();
});
