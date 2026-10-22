// Clean, Utilitarian Frontend Controller for SEO & GEO Auditor

let currentReportData = null;
let currentTaskId = null;
let auditStartTime = null;
let auditTimerInterval = null;
let eventSource = null;
let pastReports = [];

// DOM Elements
const auditForm = document.getElementById('auditForm');
const targetUrlInput = document.getElementById('targetUrl');
const startAuditBtn = document.getElementById('startAuditBtn');
const optionsToggleBtn = document.getElementById('optionsToggleBtn');
const optionsPanel = document.getElementById('optionsPanel');
const optionsToggleText = document.getElementById('optionsToggleText');

const progressCard = document.getElementById('progressCard');
const progressTitle = document.getElementById('progressTitle');
const progressSubtitle = document.getElementById('progressSubtitle');
const progressTimer = document.getElementById('progressTimer');
const toggleLogsBtn = document.getElementById('toggleLogsBtn');
const liveLogs = document.getElementById('liveLogs');
const logCountBadge = document.getElementById('logCountBadge');

const errorBanner = document.getElementById('errorBanner');
const errorMessage = document.getElementById('errorMessage');
const closeErrorBtn = document.getElementById('closeErrorBtn');

const reportContainer = document.getElementById('reportContainer');
const recentQuickBar = document.getElementById('recentQuickBar');
const recentPills = document.getElementById('recentPills');

const historyDrawer = document.getElementById('historyDrawer');
const historyDrawerBtn = document.getElementById('historyDrawerBtn');
const closeHistoryBtn = document.getElementById('closeHistoryBtn');
const historyList = document.getElementById('historyList');
const historyCount = document.getElementById('historyCount');

const evidenceModal = document.getElementById('evidenceModal');
const closeEvidenceBtn = document.getElementById('closeEvidenceBtn');
const evidenceModalTitle = document.getElementById('evidenceModalTitle');
const evidenceMeta = document.getElementById('evidenceMeta');
const evidenceJson = document.getElementById('evidenceJson');

const downloadMenuBtn = document.getElementById('downloadMenuBtn');
const downloadMenu = document.getElementById('downloadMenu');

const printReportBtn = document.getElementById('printReportBtn');
const copyMarkdownBtn = document.getElementById('copyMarkdownBtn');

// Options inputs
const optMaxPages = document.getElementById('optMaxPages');
const optMaxDepth = document.getElementById('optMaxDepth');
const optCrawlDelay = document.getElementById('optCrawlDelay');
const optKeywords = document.getElementById('optKeywords');
const optRenderJs = document.getElementById('optRenderJs');
const optCheckExternal = document.getElementById('optCheckExternal');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadPastReports();
});

function setupEventListeners() {
  // Advanced options toggle
  optionsToggleBtn.addEventListener('click', () => {
    const isHidden = optionsPanel.classList.toggle('hidden');
    optionsToggleText.textContent = isHidden ? 'Advanced settings' : 'Hide settings';
  });

  // Audit form submit
  auditForm.addEventListener('submit', (e) => {
    e.preventDefault();
    startAudit();
  });

  // Toggle logs
  toggleLogsBtn.addEventListener('click', () => {
    liveLogs.classList.toggle('hidden');
  });

  // Close error banner
  closeErrorBtn.addEventListener('click', () => {
    errorBanner.classList.add('hidden');
  });

  // History Drawer
  historyDrawerBtn.addEventListener('click', () => {
    historyDrawer.classList.remove('hidden');
  });
  closeHistoryBtn.addEventListener('click', () => {
    historyDrawer.classList.add('hidden');
  });
  historyDrawer.addEventListener('click', (e) => {
    if (e.target === historyDrawer) historyDrawer.classList.add('hidden');
  });

  // Evidence Modal
  closeEvidenceBtn.addEventListener('click', () => {
    evidenceModal.classList.add('hidden');
  });
  evidenceModal.addEventListener('click', (e) => {
    if (e.target === evidenceModal) evidenceModal.classList.add('hidden');
  });

  // Download menu
  downloadMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    downloadMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => {
    downloadMenu.classList.remove('show');
  });

  // Print
  printReportBtn.addEventListener('click', () => {
    window.print();
  });

  // Copy Markdown
  copyMarkdownBtn.addEventListener('click', () => {
    const text = document.getElementById('markdownPreviewContent').innerText;
    navigator.clipboard.writeText(text).then(() => {
      const orig = copyMarkdownBtn.textContent;
      copyMarkdownBtn.textContent = 'Copied ✓';
      setTimeout(() => { copyMarkdownBtn.textContent = orig; }, 1800);
    });
  });

  // Tab switching
  document.querySelectorAll('.seg-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.seg-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  // Severity filter pills
  document.querySelectorAll('#severityFilterPills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#severityFilterPills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterIssuesTable();
    });
  });

  document.getElementById('issuesSearchInput').addEventListener('input', filterIssuesTable);
  document.getElementById('categoryFilterSelect').addEventListener('change', filterIssuesTable);
  document.getElementById('pagesSearchInput').addEventListener('input', filterPagesTable);
}

// Load past reports
async function loadPastReports() {
  try {
    const res = await fetch('/api/reports');
    if (!res.ok) return;
    const data = await res.json();
    pastReports = data.reports || [];

    historyCount.textContent = pastReports.length;

    if (pastReports.length > 0) {
      recentQuickBar.style.display = 'flex';
      recentPills.innerHTML = pastReports.slice(0, 3).map(r => {
        let domain = r.start_url || r.report_id;
        try { domain = new URL(r.start_url).hostname; } catch(e){}
        return `<button type="button" class="recent-pill" onclick="loadReport('${r.report_id}')">${escapeHtml(domain)} <span style="opacity:0.65;">(${r.health_score}/100)</span></button>`;
      }).join('');
    } else {
      recentQuickBar.style.display = 'none';
    }

    historyList.innerHTML = pastReports.map(r => `
      <div class="history-entry" onclick="loadReport('${r.report_id}'); document.getElementById('historyDrawer').classList.add('hidden');">
        <div class="history-entry-top">
          <span class="history-entry-url">${escapeHtml(r.start_url || r.report_id)}</span>
          <span class="history-entry-score">${r.health_score}/100</span>
        </div>
        <div class="history-entry-sub">
          ${r.pages_crawled} pages • ${r.total_issues} issues • ${r.duration_seconds}s • ${new Date(r.generated_at).toLocaleDateString()}
        </div>
      </div>
    `).join('') || '<p style="color:var(--text-dim); text-align:center; padding: 20px;">No audits recorded.</p>';

  } catch (err) {
    console.error('Failed to load past audits', err);
  }
}

// Start audit
async function startAudit() {
  const url = targetUrlInput.value.trim();
  if (!url) return;

  errorBanner.classList.add('hidden');
  progressCard.classList.remove('hidden');
  reportContainer.classList.add('hidden');
  startAuditBtn.disabled = true;

  liveLogs.innerHTML = '';
  logCountBadge.textContent = '0';
  progressTitle.textContent = 'Connecting to site...';
  progressSubtitle.textContent = `Target: ${url}`;

  auditStartTime = Date.now();
  progressTimer.textContent = '0s';
  clearInterval(auditTimerInterval);
  auditTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - auditStartTime) / 1000);
    progressTimer.textContent = `${elapsed}s`;
  }, 1000);

  const payload = {
    url: url,
    max_pages: parseInt(optMaxPages.value, 10) || 10,
    max_depth: parseInt(optMaxDepth.value, 10) || 3,
    crawl_delay: parseFloat(optCrawlDelay.value) || 0.5,
    keywords: optKeywords.value.trim(),
    render_js: optRenderJs.checked,
    check_external: optCheckExternal.checked,
  };

  try {
    const res = await fetch('/api/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Audit request failed');
    }

    const { task_id } = await res.json();
    currentTaskId = task_id;
    listenToAuditStream(task_id);

  } catch (err) {
    handleAuditError(err.message);
  }
}

// SSE stream
function listenToAuditStream(taskId) {
  if (eventSource) eventSource.close();

  eventSource = new EventSource(`/api/audit/stream/${taskId}`);

  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.progress) {
      progressTitle.textContent = data.progress;
    }

    if (data.new_logs && data.new_logs.length > 0) {
      data.new_logs.forEach(log => {
        const div = document.createElement('div');
        div.className = `log-entry ${log.level.toLowerCase()}`;
        div.innerHTML = `<span class="log-time">[${log.time}]</span> <span class="log-msg">${escapeHtml(log.msg)}</span>`;
        liveLogs.appendChild(div);
      });
      liveLogs.scrollTop = liveLogs.scrollHeight;
      logCountBadge.textContent = liveLogs.children.length;
    }

    if (data.status === 'completed') {
      eventSource.close();
      finishAudit(data.data);
    } else if (data.status === 'error') {
      eventSource.close();
      handleAuditError(data.error || 'Audit encountered an error');
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    pollAuditStatus(taskId);
  };
}

// Polling fallback
async function pollAuditStatus(taskId) {
  try {
    const res = await fetch(`/api/audit/status/${taskId}`);
    if (!res.ok) throw new Error('Status polling failed');
    const data = await res.json();

    if (data.progress) progressTitle.textContent = data.progress;

    if (data.status === 'completed') {
      finishAudit(data.data);
    } else if (data.status === 'error') {
      handleAuditError(data.error || 'Audit failed');
    } else {
      setTimeout(() => pollAuditStatus(taskId), 1000);
    }
  } catch (err) {
    handleAuditError(err.message);
  }
}

function finishAudit(auditData) {
  clearInterval(auditTimerInterval);
  progressCard.classList.add('hidden');
  startAuditBtn.disabled = false;
  loadPastReports();
  renderReport(auditData);
}

function handleAuditError(msg) {
  clearInterval(auditTimerInterval);
  progressCard.classList.add('hidden');
  startAuditBtn.disabled = false;
  errorMessage.textContent = msg;
  errorBanner.classList.remove('hidden');
}

// Load a specific report
async function loadReport(reportId) {
  try {
    const res = await fetch(`/api/reports/${reportId}`);
    if (!res.ok) throw new Error('Failed to load report');
    const data = await res.json();
    renderReport(data);
  } catch (err) {
    alert('Error loading report: ' + err.message);
  }
}

// Render report
function renderReport(data) {
  currentReportData = data;
  reportContainer.classList.remove('hidden');
  reportContainer.scrollIntoView({ behavior: 'smooth' });

  const summary = data.summary || {};
  const issues = data.issues || [];
  const recs = data.recommendations || [];
  const pages = data.pages || [];
  const geo = data.geo || {};
  const proposals = data.proposals || [];
  const reportId = data.report_id || '';

  // Header
  const targetUrl = summary.start_url || data.config?.start_url || '';
  document.getElementById('reportTargetUrl').textContent = targetUrl;
  const extLink = document.getElementById('reportExternalLink');
  extLink.href = targetUrl;

  document.getElementById('reportTimestamp').textContent = data.generated_at
    ? `Generated ${new Date(data.generated_at).toLocaleString()}`
    : '';

  // Download links
  document.getElementById('dlMarkdownBtn').href = `/api/reports/${reportId}/download/report.md`;
  document.getElementById('dlJsonBtn').href = `/api/reports/${reportId}/download/audit.json`;
  document.getElementById('dlIssuesCsvBtn').href = `/api/reports/${reportId}/download/issues.csv`;
  document.getElementById('dlPagesCsvBtn').href = `/api/reports/${reportId}/download/pages.csv`;
  document.getElementById('dlRecsCsvBtn').href = `/api/reports/${reportId}/download/recommendations.csv`;

  // Score
  const score = Number.isFinite(data.health_score) ? data.health_score : null;
  const scoreVal = document.getElementById('healthScoreValue');
  const scoreBadge = document.getElementById('healthScoreBadge');

  scoreVal.textContent = score ?? '—';
  if (score === null) {
    scoreBadge.className = 'score-badge';
    scoreBadge.textContent = 'Unavailable';
  } else if (score >= 80) {
    scoreBadge.className = 'score-badge good';
    scoreBadge.textContent = 'Good';
  } else if (score >= 55) {
    scoreBadge.className = 'score-badge fair';
    scoreBadge.textContent = 'Needs work';
  } else {
    scoreBadge.className = 'score-badge poor';
    scoreBadge.textContent = 'Poor';
  }

  // Issue Counts
  const sev = summary.issues_by_severity || {};
  document.getElementById('totalIssuesCount').textContent = summary.total_issues || issues.length;
  document.getElementById('sevCriticalCount').textContent = sev.CRITICAL || 0;
  document.getElementById('sevHighCount').textContent = sev.HIGH || 0;
  document.getElementById('sevMediumCount').textContent = sev.MEDIUM || 0;
  document.getElementById('sevLowCount').textContent = sev.LOW || 0;

  // Crawl Coverage
  document.getElementById('pagesCrawledCount').textContent = summary.pages_crawled || pages.length;
  document.getElementById('indexableCount').textContent = summary.indexable_pages || 0;

  const statusMap = summary.status_codes || {};
  const statusStr = Object.entries(statusMap).map(([k, v]) => `${k}:${v}`).join(' ');
  const crawlMeta = [];
  if (summary.duration_seconds !== undefined) crawlMeta.push(`Duration: ${summary.duration_seconds}s`);
  if (summary.requests_made !== undefined) crawlMeta.push(`Requests: ${summary.requests_made}`);
  if (statusStr) crawlMeta.push(`Status: ${statusStr}`);
  document.getElementById('crawlExtraMeta').textContent = crawlMeta.join(' • ');

  // AI Bots
  const crawlers = geo.crawlers || [];
  const allowed = crawlers.filter(c => c.allowed).length;
  document.getElementById('geoBotsAllowed').textContent = crawlers.length
    ? `${allowed} / ${crawlers.length} allowed`
    : 'No crawler data';
  document.getElementById('llmsTxtBadge').textContent = geo.llms_txt === true
    ? 'llms.txt present'
    : geo.llms_txt === false ? 'llms.txt not found' : 'Not checked';

  // Tabs count
  document.getElementById('tabRecsCount').textContent = recs.length;
  document.getElementById('tabIssuesCount').textContent = issues.length;
  document.getElementById('tabPagesCount').textContent = pages.length;
  document.getElementById('tabProposalsCount').textContent = proposals.length;

  // Render contents
  renderRecommendations(recs);
  renderGeoTable(geo);
  populateCategoryFilter(issues);
  renderIssuesTable(issues);
  renderPagesTable(pages);
  renderProposals(proposals);
  document.getElementById('markdownPreviewContent').textContent = data.markdown_report || '';
}

// Recommendations
function renderRecommendations(recs) {
  const container = document.getElementById('recommendationsList');
  if (!recs || recs.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); padding:16px 0;">No priority fixes flagged.</div>';
    return;
  }

  container.innerHTML = recs.map((r, idx) => `
    <div class="rec-item">
      <div class="rec-item-header">
        <div class="rec-title-group">
          <span class="rec-rank-label">#${idx + 1}</span>
          <span class="rec-heading">${escapeHtml(r.title)}</span>
        </div>
        <div class="rec-tag-group">
          <span class="tag-badge tag-priority">P ${r.priority}</span>
          <span class="tag-badge ${r.severity.toLowerCase()}">${r.severity}</span>
          <span class="tag-badge" style="background:var(--bg-subtle); color:var(--text-muted);">${r.category}</span>
        </div>
      </div>
      <div class="rec-why-text">
        <strong>Why:</strong> ${escapeHtml(r.why)}
      </div>
      <div class="rec-action-callout">
        <strong>Action:</strong> ${escapeHtml(r.recommendation)}
      </div>
      ${(r.sample_urls?.length || r.examples?.length) ? `
        <details class="rec-samples-dropdown">
          <summary>${(r.sample_urls || []).length} affected page(s) / examples</summary>
          <ul>
            ${(r.examples || []).map(e => `<li>${escapeHtml(e)}</li>`).join('')}
            ${(r.sample_urls || []).slice(0, 5).map(u => `<li><a href="${u}" target="_blank" rel="noopener">${escapeHtml(u)}</a></li>`).join('')}
          </ul>
        </details>
      ` : ''}
    </div>
  `).join('');
}

// GEO table
function renderGeoTable(geo) {
  const tbody = document.getElementById('geoCrawlersTableBody');
  const crawlers = geo.crawlers || [];

  if (crawlers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="padding:16px; color:var(--text-muted);">No crawler records found.</td></tr>';
  } else {
    tbody.innerHTML = crawlers.map(c => `
      <tr>
        <td><span class="crawler-tag">${c.token}</span></td>
        <td>${escapeHtml(c.operator)}</td>
        <td style="color:var(--text-muted);">${escapeHtml(c.purpose)}</td>
        <td style="text-transform:capitalize;">${c.category}</td>
        <td>
          <span class="status-pill ${c.allowed ? 'allowed' : 'blocked'}">
            <span class="dot ${c.allowed ? 'dot-low' : 'dot-critical'}" style="background:${c.allowed ? 'var(--sev-success)' : 'var(--sev-critical)'}"></span>
            ${c.allowed ? 'Allowed' : 'Blocked'}
          </span>
        </td>
        <td>${c.docs ? `<a href="${c.docs}" target="_blank" rel="noopener" style="color:var(--text-dim); text-decoration:underline;">Docs</a>` : '-'}</td>
      </tr>
    `).join('');
  }

  // llms.txt status
  const llmsBox = document.getElementById('llmsTxtStatusBox');
  if (geo.llms_txt === true) {
    llmsBox.innerHTML = '<strong style="color:var(--sev-success)">Present</strong> • Server returned a valid /llms.txt declaration.';
  } else {
    llmsBox.innerHTML = '<strong style="color:var(--text-dim)">Not found</strong> • Optional emerging standard. Not having this does not penalize rankings.';
  }
}

// Populate Category Filter
function populateCategoryFilter(issues) {
  const select = document.getElementById('categoryFilterSelect');
  const categories = [...new Set(issues.map(i => i.category).filter(Boolean))].sort();

  select.innerHTML = '<option value="ALL">All categories</option>' +
    categories.map(c => `<option value="${c}">${c.charAt(0).toUpperCase() + c.slice(1)}</option>`).join('');
}

// Issues Table
function renderIssuesTable(issues) {
  const tbody = document.getElementById('issuesTableBody');
  if (!issues || issues.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 24px; color:var(--text-muted);">No issues detected.</td></tr>';
    return;
  }

  tbody.innerHTML = issues.map((issue, idx) => `
    <tr>
      <td><span class="tag-badge ${issue.severity.toLowerCase()}">${issue.severity}</span></td>
      <td style="color:var(--text-muted);">${issue.category}</td>
      <td>
        <div class="tbl-issue-title">${escapeHtml(issue.title)}</div>
        <div class="tbl-issue-msg">${escapeHtml(issue.message)}</div>
      </td>
      <td>
        <div class="tbl-url" title="${escapeHtml(issue.url)}">
          <a href="${issue.url}" target="_blank" rel="noopener">${escapeHtml(issue.url)}</a>
        </div>
      </td>
      <td style="text-align: right;">
        <button class="btn-inspect" type="button" onclick="viewEvidence(${idx})">Inspect</button>
      </td>
    </tr>
  `).join('');
}

function filterIssuesTable() {
  if (!currentReportData || !currentReportData.issues) return;

  const activeBtn = document.querySelector('#severityFilterPills .pill-btn.active');
  const selectedSeverity = activeBtn ? activeBtn.dataset.severity : 'ALL';
  const selectedCategory = document.getElementById('categoryFilterSelect').value;
  const search = document.getElementById('issuesSearchInput').value.toLowerCase().trim();

  const filtered = currentReportData.issues.filter(issue => {
    const matchSev = selectedSeverity === 'ALL' || issue.severity.toUpperCase() === selectedSeverity;
    const matchCat = selectedCategory === 'ALL' || issue.category.toLowerCase() === selectedCategory.toLowerCase();
    const matchSearch = !search ||
      (issue.title && issue.title.toLowerCase().includes(search)) ||
      (issue.message && issue.message.toLowerCase().includes(search)) ||
      (issue.url && issue.url.toLowerCase().includes(search));

    return matchSev && matchCat && matchSearch;
  });

  renderIssuesTable(filtered);
}

// Inspect modal
window.viewEvidence = function(idx) {
  if (!currentReportData || !currentReportData.issues) return;
  const issue = currentReportData.issues[idx];
  if (!issue) return;

  evidenceModalTitle.textContent = `${issue.title} [${issue.severity}]`;
  evidenceMeta.innerHTML = `
    <div><strong>URL:</strong> <a href="${issue.url}" target="_blank">${escapeHtml(issue.url)}</a></div>
    <div><strong>Check ID:</strong> <code>${issue.check_id}</code> • <strong>Category:</strong> ${issue.category}</div>
    <div><strong>Detail:</strong> ${escapeHtml(issue.message)}</div>
  `;
  evidenceJson.textContent = JSON.stringify(issue.evidence || {}, null, 2);
  evidenceModal.classList.remove('hidden');
};

// Pages Table
function renderPagesTable(pages) {
  const tbody = document.getElementById('pagesTableBody');
  document.getElementById('pagesFilteredCount').textContent = `${pages.length} pages`;

  if (!pages || pages.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px; color:var(--text-muted);">No page records.</td></tr>';
    return;
  }

  tbody.innerHTML = pages.map(p => `
    <tr>
      <td>
        <div class="tbl-url" title="${escapeHtml(p.url)}">
          <a href="${p.url}" target="_blank" rel="noopener">${escapeHtml(p.url)}</a>
        </div>
      </td>
      <td><span class="code-status s${p.status || 0}">${p.status || '-'}</span></td>
      <td>${p.indexable ? '<span style="color:var(--sev-success); font-weight:600;">Yes</span>' : '<span style="color:var(--sev-critical); font-weight:600;">No</span>'}</td>
      <td>
        <div style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(p.title || '')}">
          ${escapeHtml(p.title || '(No title)')}
        </div>
      </td>
      <td>${p.h1_count || 0}</td>
      <td>${p.word_count || 0}</td>
      <td>${p.ttfb_s ? p.ttfb_s.toFixed(2) + 's' : '-'}</td>
      <td>${p.images || 0} ${p.images_missing_alt ? `<span style="color:var(--sev-high)">(${p.images_missing_alt} no alt)</span>` : ''}</td>
    </tr>
  `).join('');
}

function filterPagesTable() {
  if (!currentReportData || !currentReportData.pages) return;
  const search = document.getElementById('pagesSearchInput').value.toLowerCase().trim();

  const filtered = currentReportData.pages.filter(p => {
    return !search || (p.url && p.url.toLowerCase().includes(search)) || (p.title && p.title.toLowerCase().includes(search));
  });

  renderPagesTable(filtered);
}

// Proposals
function renderProposals(proposals) {
  const container = document.getElementById('proposalsContainer');
  if (!proposals || proposals.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); padding:16px 0;">No automated metadata proposals. Add focus keywords or enable AI suggestions in config if desired.</div>';
    return;
  }

  container.innerHTML = proposals.map(p => `
    <div class="proposal-item">
      <div class="prop-meta-row">
        <span class="prop-url">${escapeHtml(p.url)}</span>
        <span class="prop-field">${p.field}</span>
      </div>
      <div class="prop-comparison">
        <div>
          <div class="prop-col-label">Current</div>
          <div>${escapeHtml(p.before || '(Empty)')}</div>
        </div>
        <div>
          <div class="prop-col-label" style="color:var(--text-main);">Proposed</div>
          <div style="font-weight:600;">${escapeHtml(p.after)}</div>
        </div>
      </div>
      <div class="prop-reason">${escapeHtml(p.reason)}</div>
    </div>
  `).join('');
}

// Helpers
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
