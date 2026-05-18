/** 禅道BUG分析工具 - 应用逻辑 */

// ========== 路由 ==========
function navigateTo(pageName) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + pageName).classList.add('active');

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.querySelector('[data-page="' + pageName + '"]');
  if (nav) nav.classList.add('active');

  // URL hash 路由，刷新后保持当前页面
  if (location.hash !== '#' + pageName) {
    history.replaceState(null, '', '#' + pageName);
  }

  if (pageName === 'settings') loadSettingsPage();
  if (pageName === 'batch') loadBatchPage();
  if (pageName === 'config') loadConfigPage();
  if (pageName === 'analysis') {
    var pid = getSelectedProjectId('#project-select');
    if (pid) loadAnalysisData(pid);
  }
  // 进入下载页时重新检查 cookie 状态
  if (pageName === 'batch') {
    checkCookieWarn();
  }
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => navigateTo(item.dataset.page));
});

// ========== 项目下拉 ==========
async function populateProjectSelects() {
  try {
    const data = await API.projects.list();
    const projects = data.projects || [];
    updateSelect('#project-select', projects);
  } catch (e) {
    console.warn('加载项目列表失败，后端可能未就绪');
  }
}

function updateSelect(selector, projects) {
  const sel = document.querySelector(selector);
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">选择项目...</option>';
  projects.forEach(p => {
    sel.innerHTML += '<option value="' + p.id + '">' + escHtml(p.name) + '</option>';
  });
  if (current) sel.value = current;
}

function getSelectedProjectId(selector) {
  const sel = document.querySelector(selector);
  return sel ? sel.value : '';
}

// ========== 数据分析页 ==========
// ===== 忽略记录：服务端 JSON 文件持久化（不受浏览器/WebView2 切换影响） =====
var _ignoredUnfocusedCache = {};  // { projectId: [names...] }
var _ignoredAmbiguousCache = {}; // { projectId: [pool_names...] }

function _getIgnored(projectId) {
  return (_ignoredUnfocusedCache[projectId] || []).slice();
}

function _addIgnored(projectId, names) {
  var existing = _ignoredUnfocusedCache[projectId] || [];
  names.forEach(function(n) { if (existing.indexOf(n) === -1) existing.push(n); });
  _ignoredUnfocusedCache[projectId] = existing;
  // 同步到服务端 + localStorage（兜底）
  API.post('/ignored/' + projectId + '/unfocused', { names: names }).catch(function(){});
  try { localStorage.setItem('ignored_unfocused_' + projectId, JSON.stringify(existing)); } catch(e) {}
}

// 重名确认弹窗
var _ambiguousData = [];
var _ambiguousProjectId = '';

function _getIgnoredAmbiguous(projectId) {
  return (_ignoredAmbiguousCache[projectId] || []).slice();
}

function _addIgnoredAmbiguous(projectId, poolNames) {
  var existing = _ignoredAmbiguousCache[projectId] || [];
  poolNames.forEach(function(n) { if (existing.indexOf(n) === -1) existing.push(n); });
  _ignoredAmbiguousCache[projectId] = existing;
  API.post('/ignored/' + projectId + '/ambiguous', { pool_names: poolNames }).catch(function(){});
  try { localStorage.setItem('ignored_ambiguous_' + projectId, JSON.stringify(existing)); } catch(e) {}
}

/** 项目加载时调用：从服务端拉取忽略列表，自动合并 localStorage 遗留数据 */
async function _loadIgnoredData(projectId) {
  try {
    var res = await API.get('/ignored/' + projectId);
    _ignoredUnfocusedCache[projectId] = res.unfocused || [];
    _ignoredAmbiguousCache[projectId] = res.ambiguous || [];

    // 迁移 localStorage 中的遗留数据到服务端（一次性）
    try {
      var legacyUnfocused = JSON.parse(localStorage.getItem('ignored_unfocused_' + projectId) || '[]');
      var legacyAmbiguous = JSON.parse(localStorage.getItem('ignored_ambiguous_' + projectId) || '[]');
      var mergedUnfocused = false, mergedAmbiguous = false;
      legacyUnfocused.forEach(function(n) {
        if (_ignoredUnfocusedCache[projectId].indexOf(n) === -1) {
          _ignoredUnfocusedCache[projectId].push(n); mergedUnfocused = true;
        }
      });
      legacyAmbiguous.forEach(function(n) {
        if (_ignoredAmbiguousCache[projectId].indexOf(n) === -1) {
          _ignoredAmbiguousCache[projectId].push(n); mergedAmbiguous = true;
        }
      });
      if (mergedUnfocused) {
        API.post('/ignored/' + projectId + '/unfocused', { names: legacyUnfocused }).catch(function(){});
      }
      if (mergedAmbiguous) {
        API.post('/ignored/' + projectId + '/ambiguous', { pool_names: legacyAmbiguous }).catch(function(){});
      }
    } catch(e) {}
  } catch(e) {
    // 服务端不可用时降级到 localStorage
    _ignoredUnfocusedCache[projectId] = JSON.parse(localStorage.getItem('ignored_unfocused_' + projectId) || '[]');
    _ignoredAmbiguousCache[projectId] = JSON.parse(localStorage.getItem('ignored_ambiguous_' + projectId) || '[]');
  }
}

function showAmbiguousModal(projectId, ambiguousList) {
  // 过滤掉已跳过/确认过的
  var ignored = _getIgnoredAmbiguous(projectId);
  ambiguousList = ambiguousList.filter(function(item) {
    return ignored.indexOf(item.pool_name) === -1;
  });
  if (!ambiguousList.length) return;

  _ambiguousData = ambiguousList;
  _ambiguousProjectId = projectId;
  var listEl = document.getElementById('ambiguous-list');
  var html = '';
  ambiguousList.forEach(function(item) {
    html += '<div style="margin-bottom:16px;">';
    html += '<div style="font-size:13px; font-weight:600; margin-bottom:6px;">池中姓名: ' + escHtml(item.pool_name) + '</div>';
    html += '<div style="font-size:12px; color:var(--silver); margin-bottom:4px;">禅道匹配到 ' + item.matches.length + ' 人:</div>';
    item.matches.forEach(function(name) {
      html += '<label style="display:flex; align-items:center; gap:6px; padding:4px 0; cursor:pointer; font-size:13px;">';
      html += '<input type="radio" name="amb_' + escHtml(item.pool_name) + '" value="' + escHtml(name) + '" checked>';
      html += escHtml(name) + '</label>';
    });
    html += '</div>';
  });
  listEl.innerHTML = html;
  document.getElementById('ambiguous-modal').style.display = 'flex';
}

// 确认按钮
document.addEventListener('DOMContentLoaded', function() {
  var confirmBtn = document.getElementById('btn-ambiguous-confirm');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', async function() {
      var selected = [];
      var allPoolNames = [];
      _ambiguousData.forEach(function(item) {
        allPoolNames.push(item.pool_name);
        var radio = document.querySelector('input[name="amb_' + item.pool_name.replace(/"/g, '\\"') + '"]:checked');
        if (radio) {
          selected.push({ pool_name: item.pool_name, chosen_name: radio.value });
        }
      });
      // 持久化：已确认过的不再弹
      _addIgnoredAmbiguous(_ambiguousProjectId, allPoolNames);
      if (selected.length > 0) {
        try {
          await API.post('/focus-pool/confirm-ambiguous', { project_id: _ambiguousProjectId, selected: selected });
        } catch (e) {}
      }
      document.getElementById('ambiguous-modal').style.display = 'none';
      loadAnalysisData(_ambiguousProjectId);
    });
  }

  var skipBtn = document.getElementById('btn-ambiguous-skip');
  if (skipBtn) {
    skipBtn.addEventListener('click', function() {
      // 持久化：跳过的池名不再弹
      var poolNames = _ambiguousData.map(function(item) { return item.pool_name; });
      _addIgnoredAmbiguous(_ambiguousProjectId, poolNames);
      document.getElementById('ambiguous-modal').style.display = 'none';
    });
  }

  // 点击遮罩关闭也持久化
  var ambModal = document.getElementById('ambiguous-modal');
  if (ambModal) {
    ambModal.addEventListener('click', function(e) {
      if (e.target === this) {
        var poolNames = _ambiguousData.map(function(item) { return item.pool_name; });
        _addIgnoredAmbiguous(_ambiguousProjectId, poolNames);
        this.style.display = 'none';
      }
    });
  }
});

// × 按钮调用
function dismissAmbiguousModal() {
  var ambModal = document.getElementById('ambiguous-modal');
  if (ambModal) {
    var poolNames = _ambiguousData.map(function(item) { return item.pool_name; });
    _addIgnoredAmbiguous(_ambiguousProjectId, poolNames);
    ambModal.style.display = 'none';
  }
}

function dismissUnfocusedAlert() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) return;
  // 将当前显示的新未关注人员持久化到忽略列表
  if (_quickAddNames && _quickAddNames.length) {
    _addIgnored(pid, _quickAddNames);
  }
  document.getElementById('unfocused-alert').style.display = 'none';
}

document.getElementById('project-select').addEventListener('change', async function() {
  const pid = this.value;
  if (!pid) {
    document.getElementById('analysis-welcome').style.display = 'none';
    document.getElementById('analysis-empty').style.display = 'flex';
    document.getElementById('analysis-loaded').style.display = 'none';
    document.getElementById('unfocused-alert').style.display = 'none';
    return;
  }
  document.getElementById('analysis-welcome').style.display = 'none';
  document.getElementById('analysis-empty').style.display = 'none';
  await loadAnalysisData(pid);
});

document.getElementById('btn-export').addEventListener('click', () => {
  const pid = getSelectedProjectId('#project-select');
  if (!pid) return alert('请先选择项目');
  const a = document.createElement('a');
  a.href = '/api/export/' + pid;
  a.download = 'bug_export_' + pid + '.csv';
  a.click();
});

var _personFilter = 'all';

document.getElementById('person-search').addEventListener('input', function() {
  filterPersonList(this.value.toLowerCase());
});

document.addEventListener('click', function(e) {
  if (e.target.classList.contains('person-filter-tag')) {
    document.querySelectorAll('.person-filter-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    _personFilter = e.target.dataset.pfilter || 'all';
    var q = document.getElementById('person-search').value.toLowerCase();
    filterPersonList(q);
  }
});

function filterPersonList(query) {
  document.querySelectorAll('#person-list .person-row').forEach(function(row) {
    var name = row.dataset.name || '';
    var nameMatch = name.includes(query);
    if (!nameMatch) { row.style.display = 'none'; return; }
    if (_personFilter === 'all') { row.style.display = ''; return; }
    var rowBugs = []; try { rowBugs = JSON.parse(row.dataset.bugs || '[]'); } catch(_) {}
    if (_personFilter === 'active') {
      row.style.display = rowBugs.some(function(b) { return (b.status || '').indexOf('激活') !== -1; }) ? '' : 'none';
    } else if (_personFilter === 'hi-sev') {
      row.style.display = rowBugs.some(function(b) { var s = b.severity || ''; return s === 'S' || s === 'A'; }) ? '' : 'none';
    } else if (_personFilter === 'many') {
      row.style.display = rowBugs.length >= 5 ? '' : 'none';
    }
  });
}

// 筛选标签
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('severity-tag')) {
    document.querySelectorAll('.severity-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    filterBugTable();
  }
  if (e.target.classList.contains('status-tag')) {
    document.querySelectorAll('.status-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    filterBugTable();
  }
});

function filterBugTable() {
  const sev = document.querySelector('.severity-tag.active')?.dataset.sev || 'all';
  const status = document.querySelector('.status-tag.active')?.dataset.status || 'all';
  document.querySelectorAll('#bug-tbody tr').forEach(row => {
    const rsev = row.dataset.severity || '';
    const rstatus = row.dataset.status || '';
    const sevMatch = sev === 'all' || rsev === sev;
    const statusMatch = status === 'all' || rstatus.indexOf(status) !== -1;
    row.style.display = (sevMatch && statusMatch) ? '' : 'none';
  });
}

async function loadAnalysisData(projectId) {
  // 加载服务端忽略列表（自动合并 localStorage 遗留数据）
  await _loadIgnoredData(projectId);

  document.getElementById('analysis-welcome').style.display = 'none';
  document.getElementById('analysis-empty').style.display = 'none';
  const container = document.getElementById('analysis-loaded');
  container.style.display = 'flex';

  try {
    const data = await API.analyze.load(projectId);
    _currentPersons = data.persons || [];
    renderPersonList(_currentPersons);

    // COC人员激活 BUG 总数
    var focusActive = 0;
    _currentPersons.forEach(function(p) {
      if (p.focus) focusActive += (p.active || 0);
    });
    var summaryEl = document.getElementById('focus-active-summary');
    if (summaryEl) summaryEl.textContent = 'COC人员 · 激活 BUG: ' + focusActive;

    // 未COC人员提示 — 已忽略过的永不再提醒，仅显示新出现的
    var unfocused = data.unfocused_persons || [];
    var ignored = _getIgnored(projectId);
    var newUnfocused = unfocused.filter(function(name) {
      return ignored.indexOf(name) === -1;
    });
    var alertEl = document.getElementById('unfocused-alert');
    if (newUnfocused.length > 0) {
      document.getElementById('unfocused-names').textContent = newUnfocused.join('、');
      _quickAddNames = newUnfocused;
      alertEl.style.display = 'flex';
    } else {
      alertEl.style.display = 'none';
    }

    // 自动匹配全局关注池
    if (unfocused.length > 0) {
      var focusedNames = data.persons.filter(function(p) { return p.focus; }).map(function(p) { return p.name; });
      API.post('/focus-pool/auto-match', { project_id: projectId, unfocused: unfocused, focused: focusedNames }).then(function(r) {
        var needReload = false;
        if (r.auto_focused && r.auto_focused.length > 0) {
          needReload = true;
        }
        if (r.ambiguous && r.ambiguous.length > 0) {
          showAmbiguousModal(projectId, r.ambiguous);
        }
        if (needReload) loadAnalysisData(projectId);
      }).catch(function() {});
    }

    if (data.persons && data.persons.length > 0) {
      selectPerson(data.persons[0].name, data.persons[0].bugs || []);
    }
    const statusEl = document.getElementById('data-status');
    var fileDate = data.file_date || '--';
    // 数据过期横幅
    var staleAlert = document.getElementById('stale-alert');
    if (data.stale) {
      staleAlert.style.display = 'flex';
      document.getElementById('stale-date').textContent = fileDate;
      statusEl.innerHTML = '<span class="status-dot amber"></span> ' + fileDate + ' · <a href="#" class="status-refresh-link" style="color:var(--link-cobalt); font-weight:600; text-decoration:none;">点击刷新</a> <span id="refresh-progress" style="font-size:11px; color:var(--silver);"></span>';
    } else {
      staleAlert.style.display = 'none';
      statusEl.innerHTML = '<span class="status-dot green"></span> ' + fileDate + ' · <a href="#" class="status-refresh-link" style="color:var(--link-cobalt); font-weight:600; text-decoration:none;">点击刷新</a> <span id="refresh-progress" style="font-size:11px; color:var(--silver);"></span>';
    }
    statusEl.style.cursor = 'default';
  } catch (e) {
    document.getElementById('analysis-empty').style.display = 'flex';
    container.style.display = 'none';
    document.getElementById('unfocused-alert').style.display = 'none';
    document.getElementById('stale-alert').style.display = 'none';
    document.getElementById('data-status').textContent = '加载失败';
    console.error(e);
  }
}

function refreshCurrentProject() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) return;
  var link = document.getElementById('status-refresh-link');
  var progress = document.getElementById('refresh-progress');
  if (link) { link.textContent = '刷新中...'; link.style.pointerEvents = 'none'; }
  if (progress) progress.textContent = '正在连接...';
  var es = new EventSource('/api/import/' + pid + '/stream');
  es.addEventListener('progress', function(e) {
    if (progress) {
      try { var d = JSON.parse(e.data); progress.textContent = d.message || ''; } catch (_) {}
    }
  });
  es.addEventListener('complete', function(e) {
    es.close();
    if (link) { link.textContent = '点击刷新'; link.style.pointerEvents = 'auto'; }
    if (progress) progress.textContent = '';
    loadAnalysisData(pid);
  });
  es.addEventListener('error', function(e) {
    es.close();
    if (link) { link.textContent = '点击刷新'; link.style.pointerEvents = 'auto'; }
    if (progress) progress.textContent = '';
    if (e.data) {
      try { var d = JSON.parse(e.data); alert(d.message || '刷新失败'); } catch (_) { alert('刷新失败'); }
    }
  });
  es.onerror = function() {
    if (es.readyState === EventSource.CLOSED) {
      if (link) { link.textContent = '点击刷新'; link.style.pointerEvents = 'auto'; }
      if (progress) progress.textContent = '';
    }
  };
}

function renderPersonList(persons) {
  const list = document.getElementById('person-list');
  const focusNames = persons.filter(p => p.focus).map(p => p.name);
  const others = persons.filter(p => !p.focus);

  let html = '';
  if (focusNames.length > 0) {
    html += '<div class="section-label" style="padding:8px 16px 4px;">关注 &middot; ' + focusNames.length + '</div>';
    persons.filter(p => p.focus).forEach(p => {
      html += personRowHtml(p);
    });
  }
  if (others.length > 0) {
    const foldId = 'fold-others';
    html += '<div id="' + foldId + '-header" style="padding:10px 16px; font-size:11px; font-weight:500; color:var(--silver); cursor:pointer; border-top:1px solid var(--border-lavender); letter-spacing:0.3px; text-transform:uppercase;" onclick="toggleFold(\'' + foldId + '\')">其他人员 &middot; ' + others.length + '</div>';
    html += '<div id="' + foldId + '" style="display:none;">';
    others.forEach(p => {
      html += personRowHtml(p);
    });
    html += '</div>';
  }
  list.innerHTML = html || '<div style="padding:16px; color:var(--silver); text-align:center; font-size:13px;">暂无数据</div>';

  list.querySelectorAll('.person-row').forEach(row => {
    row.addEventListener('click', function() {
      list.querySelectorAll('.person-row').forEach(r => r.classList.remove('selected'));
      this.classList.add('selected');
      var bugs = []; try { bugs = JSON.parse(this.dataset.bugs || '[]'); } catch(_) { bugs = []; }
      selectPerson(this.dataset.name, bugs);
    });
  });
}

function personRowHtml(p) {
  const newBadge = p.new_count > 0 ? ' <span class="badge badge-new">+' + p.new_count + '</span>' : '';
  return '<div class="person-row" data-name="' + escHtml(p.name) + '" data-bugs=\'' + JSON.stringify(p.bugs || []).replace(/'/g, '&#39;') + '\'>' +
    '<div style="display:flex; justify-content:space-between; align-items:center;">' +
    '<span style="font-weight:500;">' + escHtml(p.name) + '</span>' +
    '<span class="person-meta" style="font-size:12px; color:var(--silver);">' + p.total + '</span>' +
    '</div>' +
    '<div class="person-meta" style="font-size:11px; color:var(--silver); margin-top:2px;">' +
    'S ' + (p.S || 0) + ' &middot; A ' + (p.A || 0) + ' &middot; B ' + (p.B || 0) + ' &middot; C ' + (p.C || 0) + newBadge +
    '</div></div>';
}

function selectPerson(name, bugs) {
  _selectedPersonName = name;
  var footer = document.getElementById('focus-active-summary');
  if (footer) {
    var p = _currentPersons.find(function(p) { return p.name === name; });
    var activeCount = p ? (p.active || 0) : 0;
    var totalActive = _currentPersons.filter(function(p) { return p.focus; }).reduce(function(s, p) { return s + (p.active || 0); }, 0);
    footer.innerHTML = '<span>COC人员 · 激活 BUG: ' + totalActive + '</span>' +
      '<span style="margin:0 8px; color:var(--border-lavender);">|</span>' +
      '<span>' + escHtml(name) + ' · 激活 ' + activeCount + '</span>' +
      '<span style="flex:1;"></span>' +
      '<a href="#" id="btn-urge-single-person" style="font-size:12px; color:var(--link-cobalt); text-decoration:none; font-weight:500;">催办此人</a>';
    document.getElementById('btn-urge-single-person').addEventListener('click', function(e) {
      e.preventDefault();
      openUrgeModal('single');
    });
  }
  const tbody = document.getElementById('bug-tbody');
  if (!bugs.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--silver); padding:32px; font-size:13px;">该人员暂无 BUG</td></tr>';
    return;
  }
  tbody.innerHTML = bugs.map(b => {
    var isNew = b.is_new ? ' class="new"' : '';
    var newMark = b.is_new ? ' <span class="badge badge-new" style="font-size:10px;">新增</span>' : '';
    var overdueDays = getOverdueDays(b.deadline);
    var overdueMark = overdueDays ? ' <span class="badge badge-overdue" style="font-size:10px;">延期' + overdueDays + '天</span>' : '';
    return '<tr' + isNew + ' data-id="' + (b.id || '0') + '" data-title="' + (b.title || '').replace(/"/g, '&quot;') + '" data-severity="' + (b.severity || '') + '" data-status="' + (b.status || '') + '">' +
      '<td><a class="bug-id-link" href="https://zd.bicv.com/bug-view-' + b.id + '.html" target="_blank">#' + b.id + '</a></td>' +
      '<td>' + escHtml(b.title || '') + newMark + overdueMark + '</td>' +
      '<td><span class="badge" style="' + severityBadge(b.severity) + '">' + (b.severity || '-') + '</span></td>' +
      '<td>' + escHtml(b.status || '') + '</td>' +
      '</tr>';
  }).join('');
  filterBugTable();
  applySort();
}

// ========== BUG 表格排序 ==========
var _sortCol = null;
var _sortDir = 1; // 1=asc, -1=desc

function sortByCol(rows, col) {
  var sevMap = { S: 4, A: 3, B: 2, C: 1 };
  var statusMap = { '激活': 4, '已解决': 3, '已关闭': 2 };
  return rows.sort(function(a, b) {
    var va, vb;
    if (col === 'id') {
      va = parseInt(a.dataset.id) || 0;
      vb = parseInt(b.dataset.id) || 0;
    } else if (col === 'title') {
      va = (a.dataset.title || '').toLowerCase();
      vb = (b.dataset.title || '').toLowerCase();
    } else if (col === 'severity') {
      va = sevMap[a.dataset.severity] || 0;
      vb = sevMap[b.dataset.severity] || 0;
    } else if (col === 'status') {
      va = statusMap[a.dataset.status] || 0;
      vb = statusMap[b.dataset.status] || 0;
    }
    if (va < vb) return -1 * _sortDir;
    if (va > vb) return 1 * _sortDir;
    return 0;
  });
}

function applySort() {
  if (!_sortCol) return;
  var tbody = document.getElementById('bug-tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  if (!rows.length) return;
  sortByCol(rows, _sortCol);
  rows.forEach(function(r) { tbody.appendChild(r); });
}

document.addEventListener('click', function(e) {
  if (e.target.closest('.sort-th')) {
    var th = e.target.closest('.sort-th');
    var col = th.dataset.col;
    document.querySelectorAll('.sort-th').forEach(function(t) { t.classList.remove('asc', 'desc'); });
    if (_sortCol === col) {
      _sortDir = -_sortDir;
    } else {
      _sortCol = col;
      _sortDir = 1;
    }
    th.classList.add(_sortDir > 0 ? 'asc' : 'desc');
    th.querySelector('.sort-arrow').textContent = _sortDir > 0 ? '▲' : '▼';
    applySort();
  }
});

function toggleFold(id) {
  const el = document.getElementById(id);
  if (el.style.display === 'none') {
    el.style.display = '';
  } else {
    el.style.display = 'none';
  }
}

function severityBadge(sev) {
  const map = {
    S: { bg: '#d93025', color: '#fff' },
    A: { bg: '#000000', color: '#fff' },
    B: { bg: '#555860', color: '#fff' },
    C: { bg: '#b0b4ba', color: '#fff' },
  };
  const s = map[sev] || { bg: '#b0b4ba', color: '#fff' };
  return 'background:' + s.bg + '; color:' + s.color + ';';
}

// ========== 批量下载页数据获取 ==========
async function renderBatchList() {
  try {
    const data = await API.projects.list();
    const projects = data.projects || [];
    if (!projects.length) {
      document.getElementById('batch-empty').style.display = 'flex';
      document.getElementById('batch-focus-list').innerHTML = '';
      document.getElementById('batch-normal-list').innerHTML = '';
      return;
    }
    document.getElementById('batch-empty').style.display = 'none';
    const focus = projects.filter(p => p.focus);
    const normal = projects.filter(p => !p.focus);

    document.getElementById('batch-focus-list').innerHTML = focus.map(p => batchCard(p)).join('');
    document.getElementById('batch-normal-list').innerHTML = normal.map(p => batchCard(p)).join('');
  } catch (e) {
    console.error(e);
  }
}

function batchCard(p) {
  return '<div class="project-card">' +
    '<input type="checkbox" class="batch-check" data-id="' + p.id + '" checked style="accent-color:var(--near-black);">' +
    '<span style="flex:1; font-weight:500;">' + escHtml(p.name) + '</span>' +
    '<span style="font-size:12px; color:var(--silver);" class="batch-status">等待中</span>' +
    '</div>';
}

// ========== 工具函数 ==========
function getOverdueDays(deadlineStr) {
  if (!deadlineStr) return null;
  var m = deadlineStr.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (!m) return null;
  var dl = new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]));
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  dl.setHours(0, 0, 0, 0);
  var diff = Math.floor((today - dl) / 86400000);
  return diff > 0 ? diff : null;
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

// ========== COC人员管理模态窗口 ==========
var _focusModalProjectId = null;
var _focusModalPersons = [];
var _focusQuickAddMode = false;
var _quickAddNames = [];

document.getElementById('btn-focus-manage').addEventListener('click', function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  openFocusModal(pid);
});

document.getElementById('btn-focus-modal-close').addEventListener('click', closeFocusModal);
document.getElementById('btn-focus-modal-cancel').addEventListener('click', closeFocusModal);

document.getElementById('focus-modal').addEventListener('click', function(e) {
  if (e.target === this) closeFocusModal();
});

document.getElementById('focus-modal-search').addEventListener('input', function() {
  renderFocusModalList(this.value.toLowerCase());
});

document.getElementById('btn-focus-modal-save').addEventListener('click', async function() {
  var checks = document.querySelectorAll('#focus-modal-list input[type=checkbox]');
  var selected = [];
  checks.forEach(function(cb) { if (cb.checked) selected.push(cb.dataset.name); });
  var projectId = _focusModalProjectId;
  try {
    if (_focusQuickAddMode) {
      // 快速添加模式：合并到现有关注列表
      var existing = await API.focus.get(projectId);
      var merged = (existing.persons || []).slice();
      selected.forEach(function(name) {
        if (merged.indexOf(name) === -1) merged.push(name);
      });
      await API.focus.update(projectId, merged);
    } else {
      await API.focus.update(projectId, selected);
    }
    closeFocusModal();
    // 刷新人员列表
    var pid = getSelectedProjectId('#project-select');
    if (pid && pid === projectId) {
      await loadAnalysisData(pid);
    }
  } catch (e) {
    alert('保存关注列表失败');
    console.error(e);
  }
});

async function openFocusModal(projectId) {
  if (!projectId) {
    projectId = getSelectedProjectId('#project-select');
    if (!projectId) { alert('请先选择项目'); return; }
  }
  _focusModalProjectId = projectId;
  document.getElementById('focus-modal').style.display = 'flex';
  document.getElementById('focus-modal-search').value = '';

  try {
    var focusData = await API.focus.get(projectId);
    var focusList = focusData.persons || [];
    // 获取当前分析数据中的人员
    var pid = getSelectedProjectId('#project-select');
    if (pid === projectId) {
      var rows = document.querySelectorAll('#person-list .person-row');
      _focusModalPersons = [];
      rows.forEach(function(row) {
        _focusModalPersons.push(row.dataset.name);
      });
    } else {
      // 不在当前分析页，从 API 加载
      var data = await API.analyze.load(projectId);
      _focusModalPersons = (data.persons || []).map(function(p) { return p.name; });
    }
    // 标记已关注
    _focusModalPersons = _focusModalPersons.map(function(name) {
      return { name: name, checked: focusList.indexOf(name) !== -1 };
    });
    // 关注名单中有但当前数据中没有的人也要显示
    focusList.forEach(function(name) {
      if (_focusModalPersons.every(function(p) { return p.name !== name; })) {
        _focusModalPersons.push({ name: name, checked: true });
      }
    });
    renderFocusModalList('');
  } catch (e) {
    console.error('加载关注列表失败:', e);
  }
}

function openUnfocusedQuickAdd(projectId) {
  if (!projectId) {
    projectId = getSelectedProjectId('#project-select');
    if (!projectId) { alert('请先选择项目'); return; }
  }
  _focusModalProjectId = projectId;
  _focusQuickAddMode = true;
  document.getElementById('focus-modal-title').textContent = '新增人员关注';
  document.getElementById('focus-modal').style.display = 'flex';
  document.getElementById('focus-modal-search').value = '';
  _focusModalPersons = _quickAddNames.map(function(name) {
    return { name: name, checked: false };
  });
  renderFocusModalList('');
}

function renderFocusModalList(query) {
  var list = document.getElementById('focus-modal-list');
  if (!_focusModalPersons.length) {
    list.innerHTML = '<div style="padding:16px; text-align:center; color:var(--silver); font-size:13px;">暂无数据</div>';
    return;
  }
  // 渲染前从当前 DOM 读回勾选状态，避免搜索过滤重渲染丢失
  var domChecks = list.querySelectorAll('input[type=checkbox]');
  domChecks.forEach(function(cb) {
    var name = cb.dataset.name;
    var p = _focusModalPersons.find(function(x) { return x.name === name; });
    if (p) p.checked = cb.checked;
  });
  // 已勾选（关注）人员排前面
  var sorted = _focusModalPersons.slice().sort(function(a, b) { return (b.checked ? 1 : 0) - (a.checked ? 1 : 0); });
  list.innerHTML = sorted.map(function(p) {
    var hidden = query && p.name.toLowerCase().indexOf(query) === -1;
    return '<label style="display:' + (hidden ? 'none' : 'flex') + '; align-items:center; gap:8px; padding:8px 0; cursor:pointer; font-size:13px; border-bottom:1px solid var(--border-lavender);">' +
      '<input type="checkbox" data-name="' + escHtml(p.name) + '" ' + (p.checked ? 'checked' : '') + ' style="accent-color:var(--near-black);">' +
      '<span>' + escHtml(p.name) + '</span>' +
      '</label>';
  }).join('');
}

function closeFocusModal() {
  document.getElementById('focus-modal').style.display = 'none';
  document.getElementById('focus-modal-title').textContent = '管理COC人员';
  _focusModalProjectId = null;
  _focusModalPersons = [];
  _focusQuickAddMode = false;
}

// ========== 图表模块 ==========
var CHART_COLORS = {
  S: { bg: 'rgba(217,48,37,0.85)', border: '#d93025' },
  A: { bg: 'rgba(28,32,36,0.85)', border: '#1c2024' },
  B: { bg: 'rgba(85,88,96,0.85)', border: '#555860' },
  C: { bg: 'rgba(176,180,186,0.85)', border: '#b0b4ba' },
};
var _barChart = null;
var _pieChart = null;
var _currentPersons = [];

// 自定义数据标签插件，所有图表默认显示数值方便截图
var dataLabelPlugin = {
  id: 'dataLabels',
  afterDatasetsDraw: function(chart) {
    if (chart.options.plugins && chart.options.plugins.dataLabels === false) return;
    var ctx = chart.ctx;
    var type = chart.config.type;

    if (type === 'bar') {
      // 水平柱状图：在每条堆积柱末端显示总数
      var datasets = chart.data.datasets;
      var meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data) return;
      meta.data.forEach(function(bar, i) {
        var total = 0;
        datasets.forEach(function(ds) { total += (ds.data[i] || 0); });
        if (total === 0) return;
        ctx.save();
        ctx.font = 'bold 11px Inter, -apple-system, sans-serif';
        ctx.fillStyle = '#1c2024';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(total, bar.x + 6, bar.y);
        ctx.restore();
      });
    } else if (type === 'pie' || type === 'doughnut') {
      // 环形图：引导线 + 外部文字标签
      var metaPie = chart.getDatasetMeta(0);
      if (!metaPie || !metaPie.data) return;
      var ds = chart.data.datasets[0];
      var data = ds.data;
      var sevData = ds.severity || [];
      var bgColors = ds.backgroundColor;
      var firstArc = metaPie.data[0];
      if (!firstArc) return;
      var outerR = firstArc.outerRadius;
      // 按角度排序，让标签分布更均匀
      var indexed = metaPie.data.map(function(arc, i) { return { arc: arc, i: i }; });
      indexed.sort(function(a, b) {
        var aAng = (a.arc.startAngle + a.arc.endAngle) / 2;
        var bAng = (b.arc.startAngle + b.arc.endAngle) / 2;
        return aAng - bAng;
      });
      indexed.forEach(function(item) {
        var arc = item.arc;
        var i = item.i;
        var value = data[i];
        if (value === 0) return;
        var label = chart.data.labels[i];
        var shortName = label.length > 6 ? label.substring(0, 6) + '..' : label;
        var midAngle = (arc.startAngle + arc.endAngle) / 2;
        var cosA = Math.cos(midAngle);
        var sinA = Math.sin(midAngle);
        var isRight = cosA >= 0;
        var color = bgColors[i % bgColors.length];

        // 引导线三点
        var x0 = arc.x + cosA * outerR;
        var y0 = arc.y + sinA * outerR;
        var x1 = arc.x + cosA * (outerR + 16);
        var y1 = arc.y + sinA * (outerR + 16);
        var x2 = x1 + (isRight ? 26 : -26);
        var y2 = y1;

        ctx.save();
        // 引导线
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.stroke();
        // 扇区边缘小圆点
        ctx.beginPath();
        ctx.arc(x0, y0, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // 文字标签
        var textX = x2 + (isRight ? 5 : -5);
        var textY = y2;
        ctx.textAlign = isRight ? 'left' : 'right';
        ctx.textBaseline = 'middle';

        ctx.font = 'bold 10px Inter, -apple-system, sans-serif';
        ctx.fillStyle = '#1c2024';
        ctx.fillText(shortName + ' ' + value, textX, textY - 7);

        if (sevData[i]) {
          var parts = ['S','A','B','C'].filter(function(s){return sevData[i][s]>0;}).map(function(s){return s+sevData[i][s];});
          if (parts.length > 0) {
            ctx.font = '9px Inter, -apple-system, sans-serif';
            ctx.fillStyle = '#60646c';
            ctx.fillText(parts.join(' '), textX, textY + 7);
          }
        }
        ctx.restore();
      });
    } else if (type === 'line') {
      // 折线图：每个数据点上方显示数值
      var metaLine = chart.getDatasetMeta(0);
      if (!metaLine || !metaLine.data) return;
      chart.data.datasets.forEach(function(ds, dsIdx) {
        var metaDs = chart.getDatasetMeta(dsIdx);
        if (!metaDs || !metaDs.data) return;
        metaDs.data.forEach(function(point, i) {
          var val = ds.data[i];
          if (val === null || val === undefined || val === 0) return;
          ctx.save();
          ctx.font = 'bold 11px Inter, -apple-system, sans-serif';
          ctx.fillStyle = ds.borderColor || '#1c2024';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(val, point.x, point.y - 6);
          ctx.restore();
        });
      });
    }
  }
};

// 在 Chart 默认全局注册插件（如果 Chart 已加载）
if (typeof Chart !== 'undefined' && Chart.register) {
  Chart.register(dataLabelPlugin);
}

// 柱状图
document.getElementById('btn-chart-bar').addEventListener('click', function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  document.getElementById('chart-bar-modal').style.display = 'flex';
  document.getElementById('chart-bar-filter').value = 'focus';
  renderBarChart();
});

document.getElementById('btn-chart-bar-close').addEventListener('click', function() {
  document.getElementById('chart-bar-modal').style.display = 'none';
  if (_barChart) { _barChart.destroy(); _barChart = null; }
});

document.getElementById('chart-bar-modal').addEventListener('click', function(e) {
  if (e.target === this) {
    this.style.display = 'none';
    if (_barChart) { _barChart.destroy(); _barChart = null; }
  }
});

document.getElementById('chart-bar-filter').addEventListener('change', renderBarChart);

function getChartData(filter) {
  if (!_currentPersons || !_currentPersons.length) { alert('请先选择项目并加载数据'); return null; }
  var persons = _currentPersons;
  if (filter === 'focus') persons = persons.filter(function(p) { return p.focus; });
  persons.sort(function(a, b) { return b.total - a.total; });

  var labels = persons.map(function(p) { return p.name; });
  var datasets = ['S', 'A', 'B', 'C'].map(function(sev) {
    return {
      label: sev,
      data: persons.map(function(p) { return p[sev] || 0; }),
      backgroundColor: CHART_COLORS[sev].bg,
      borderColor: CHART_COLORS[sev].border,
      borderWidth: 1,
    };
  });

  return { labels: labels, datasets: datasets };
}

function renderBarChart() {
  var filter = document.getElementById('chart-bar-filter').value;
  var data = getChartData(filter);
  if (!data) return;
  var canvas = document.getElementById('chart-bar-canvas');
  var container = canvas.parentElement;
  canvas.height = Math.max(400, data.labels.length * 30);
  var ctx = canvas.getContext('2d');
  if (_barChart) _barChart.destroy();

  _barChart = new Chart(ctx, {
    type: 'bar',
    data: data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      scales: {
        x: {
          stacked: true,
          beginAtZero: true,
          ticks: { font: { size: 11 }, color: '#60646c', precision: 0 },
          grid: { color: 'rgba(0,0,0,0.04)' },
          title: { display: true, text: 'BUG 数量', font: { size: 11 }, color: '#60646c' },
        },
        y: {
          stacked: true,
          ticks: { font: { size: 11 }, color: '#60646c' },
          grid: { display: false },
        },
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 11 }, usePointStyle: true, padding: 16, color: '#60646c' },
        },
      },
    },
  });
}

// 饼状图
document.getElementById('btn-chart-pie').addEventListener('click', function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  document.getElementById('chart-pie-modal').style.display = 'flex';
  document.getElementById('chart-pie-filter').value = 'focus';
  renderPieChart();
});

document.getElementById('btn-chart-pie-close').addEventListener('click', function() {
  document.getElementById('chart-pie-modal').style.display = 'none';
  if (_pieChart) { _pieChart.destroy(); _pieChart = null; }
});

document.getElementById('chart-pie-modal').addEventListener('click', function(e) {
  if (e.target === this) {
    this.style.display = 'none';
    if (_pieChart) { _pieChart.destroy(); _pieChart = null; }
  }
});

document.getElementById('chart-pie-filter').addEventListener('change', renderPieChart);

function renderPieChart() {
  if (!_currentPersons || !_currentPersons.length) { alert('请先选择项目并加载数据'); return; }
  var filter = document.getElementById('chart-pie-filter').value;
  var persons = _currentPersons;
  if (filter === 'focus') persons = persons.filter(function(p) { return p.focus; });
  persons = persons.filter(function(p) { return p.total > 0; });
  persons.sort(function(a, b) { return b.total - a.total; });

  var ctx = document.getElementById('chart-pie-canvas').getContext('2d');
  if (_pieChart) _pieChart.destroy();

  var bgColors = [
    '#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899',
    '#f97316', '#14b8a6', '#6366f1', '#84cc16', '#d946ef', '#0ea5e9', '#e11d48',
    '#65a30d', '#0891b2', '#c026d3', '#0284c7', '#a3e635', '#7c3aed',
    '#ea580c', '#2563eb', '#16a34a', '#db2777', '#ca8a04', '#9333ea',
  ];

  _pieChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: persons.map(function(p) { var n = p.name.replace(/[^一-鿿·]/g, ''); return n || p.name; }),
      datasets: [{
        data: persons.map(function(p) { return p.total; }),
        backgroundColor: bgColors,
        borderColor: '#fff',
        borderWidth: 2,
        hoverBorderWidth: 3,
        severity: persons.map(function(p) { return { S: p.S, A: p.A, B: p.B, C: p.C }; }),
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '40%',
      layout: { padding: { top: 70, bottom: 70, left: 140, right: 140 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              var p = persons[ctx.dataIndex];
              var n = p.name.replace(/[^一-鿿·]/g, '') || p.name;
              var parts = ['S', 'A', 'B', 'C'].map(function(s) { return p[s] > 0 ? s + ':' + p[s] : null; }).filter(Boolean);
              return n + ' 共 ' + p.total + ' Bug  (' + parts.join(' ') + ')';
            },
          },
        },
      },
    },
  });

  var canvas = document.getElementById('chart-pie-canvas');
  var cnt = persons.length;
  canvas.style.height = Math.max(850, cnt * 24) + 'px';
  canvas.style.width = Math.max(1100, cnt * 26) + 'px';
}

// ========== 趋势图 ==========
var _trendChart = null;
var _trendData = null;

document.addEventListener('DOMContentLoaded', function() {
  var trendBtn = document.getElementById('btn-chart-trend');
  if (trendBtn) {
    trendBtn.addEventListener('click', function() {
      var pid = getSelectedProjectId('#project-select');
      if (!pid) { alert('请先选择项目'); return; }
      openTrendModal(pid);
    });
  }

  var trendCloseBtn = document.getElementById('btn-chart-trend-close');
  if (trendCloseBtn) {
    trendCloseBtn.addEventListener('click', closeTrendModal);
  }

  var trendOverlay = document.getElementById('chart-trend-modal');
  if (trendOverlay) {
    trendOverlay.addEventListener('click', function(e) {
      if (e.target === this) closeTrendModal();
    });
  }
});

// 人员/数据筛选标签
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('trend-person-tag')) {
    document.querySelectorAll('.trend-person-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    updateTrendPersonCheckboxes(e.target.dataset.trendPerson);
    renderTrendChart();
  }
  if (e.target.classList.contains('trend-data-tag')) {
    document.querySelectorAll('.trend-data-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    renderTrendChart();
  }
  if (e.target.classList.contains('trend-view-tag')) {
    document.querySelectorAll('.trend-view-tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    renderTrendChart();
  }
});

document.getElementById('trend-person-search').addEventListener('input', function() {
  updateTrendPersonCheckboxes();
  renderTrendChart();
});

async function openTrendModal(projectId) {
  document.getElementById('chart-trend-modal').style.display = 'flex';
  document.querySelector('.trend-person-tag[data-trend-person="focus"]').classList.add('active');
  document.querySelector('.trend-person-tag[data-trend-person="all"]').classList.remove('active');
  document.querySelector('.trend-data-tag[data-trend-data="total"]').classList.add('active');
  document.querySelector('.trend-data-tag[data-trend-data="active"]').classList.remove('active');
  document.querySelector('.trend-view-tag[data-trend-view="sum"]').classList.add('active');
  document.querySelector('.trend-view-tag[data-trend-view="single"]').classList.remove('active');
  document.getElementById('trend-person-search').value = '';

  try {
    var data = await API.trend.get(projectId);
    _trendData = data;
    updateTrendPersonCheckboxes('focus');
    renderTrendChart();
    if (!data || !data.records || data.records.length === 0) {
      document.getElementById('trend-person-checkboxes').innerHTML = '<span style="color:var(--silver); padding:4px 0;">暂无趋势数据，请先导入数据</span>';
    }
  } catch (e) {
    console.error('Trend chart error:', e);
    document.getElementById('trend-person-checkboxes').innerHTML = '<span style="color:var(--rose); padding:4px 0;">加载失败: ' + (e.message || '未知错误') + '</span>';
    if (_trendChart) { _trendChart.destroy(); _trendChart = null; }
  }
}

function closeTrendModal() {
  document.getElementById('chart-trend-modal').style.display = 'none';
  if (_trendChart) { _trendChart.destroy(); _trendChart = null; }
  _trendData = null;
}

function updateTrendPersonCheckboxes(filterOverride) {
  if (!_trendData || !_trendData.records || _trendData.records.length === 0) return;

  var filter = filterOverride || document.querySelector('.trend-person-tag.active')?.dataset.trendPerson || 'focus';
  var query = document.getElementById('trend-person-search').value.toLowerCase();

  var allNames = new Set();
  _trendData.records.forEach(function(rec) {
    (rec.persons || []).forEach(function(p) { allNames.add(p.name); });
  });

  var focusNames = new Set();
  if (typeof _currentPersons !== 'undefined') {
    _currentPersons.forEach(function(p) {
      if (p.focus) focusNames.add(p.name);
    });
  }

  var checkedMap = {};
  // filterOverride 传入时重置勾选（全部→全选，关注→仅关注），搜索时不重置
  if (filterOverride) {
    var namesArr = Array.from(allNames);
    namesArr.forEach(function(name) {
      checkedMap[name] = filter === 'all' ? true : focusNames.has(name);
    });
  } else {
    var container = document.getElementById('trend-person-checkboxes');
    container.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
      checkedMap[cb.value] = cb.checked;
    });
  }

  var html = '';
  var names = Array.from(allNames).sort();
  names.forEach(function(name) {
    var matchesSearch = !query || name.toLowerCase().indexOf(query) !== -1;
    var matchesFilter = filter === 'all' || focusNames.has(name);
    var visible = matchesSearch && matchesFilter;
    if (!(name in checkedMap)) checkedMap[name] = (filter === 'focus' ? focusNames.has(name) : true);
    var checked = checkedMap[name] ? ' checked' : '';
    html += '<label class="trend-person-label" style="' + (visible ? '' : 'display:none;') + '">' +
      '<input type="checkbox" value="' + escHtml(name) + '"' + checked + ' onchange="renderTrendChart()"> ' +
      escHtml(name) + '</label>';
  });
  document.getElementById('trend-person-checkboxes').innerHTML = html;
}

function trendValue(person, type) {
  if (!person) return 0;
  if (type === 'rate') {
    var resolved = (person.resolved || 0) + (person.closed || 0);
    var total = person.total || 1;
    return Math.round(resolved / total * 100);
  }
  return person[type] || 0;
}

function renderTrendChart() {
  if (_trendChart) { _trendChart.destroy(); _trendChart = null; }
  if (!_trendData || !_trendData.records || _trendData.records.length === 0) return;

  var dataType = document.querySelector('.trend-data-tag.active')?.dataset.trendData || 'total';
  var isRate = dataType === 'rate';

  var checkedNames = [];
  document.querySelectorAll('#trend-person-checkboxes input[type="checkbox"]:checked').forEach(function(cb) {
    checkedNames.push(cb.value);
  });

  // 更新底部统计文本
  var latestRecord = _trendData.records[_trendData.records.length - 1];
  var checkedTotal = 0; var checkedRate = 0;
  (latestRecord.persons || []).forEach(function(p) {
    if (checkedNames.indexOf(p.name) !== -1) {
      checkedTotal += (p.total || 0);
      checkedRate += (p.resolved || 0) + (p.closed || 0);
    }
  });
  var totalEl = document.getElementById('trend-checked-total');
  if (totalEl) {
    if (isRate) {
      var ratePct = checkedTotal > 0 ? Math.round(checkedRate / checkedTotal * 100) : 0;
      totalEl.textContent = checkedNames.length ? ratePct + '%' : '';
    } else {
      totalEl.textContent = checkedNames.length ? checkedTotal + ' BUG' : '';
    }
  }

  if (checkedNames.length === 0) return;

  var dates = _trendData.records.map(function(r) { return r.date; });

  var COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
    '#06b6d4', '#f97316', '#6366f1', '#14b8a6', '#e11d48', '#64748b',
    '#0ea5e9', '#d946ef', '#22c55e', '#eab308',
  ];

  var viewMode = document.querySelector('.trend-view-tag.active')?.dataset.trendView || 'sum';

  var datasets;
  if (viewMode === 'sum') {
    var sumData = _trendData.records.map(function(rec) {
      var sum = 0; var sumResolved = 0; var sumTotal = 0;
      (rec.persons || []).forEach(function(p) {
        if (checkedNames.indexOf(p.name) !== -1) {
          sumTotal += (p.total || 0);
          sumResolved += (p.resolved || 0) + (p.closed || 0);
          sum += trendValue(p, dataType);
        }
      });
      // 合计视图下解决率用总计计算
      if (isRate) return sumTotal > 0 ? Math.round(sumResolved / sumTotal * 100) : 0;
      return sum;
    });
    datasets = [{
      label: checkedNames.length + '人合计',
      data: sumData,
      borderColor: '#1c2024',
      backgroundColor: 'rgba(28,32,36,0.08)',
      borderWidth: 2.5,
      borderDash: [],
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: '#1c2024',
      tension: 0.3,
      spanGaps: true,
    }];
  } else {
    datasets = checkedNames.map(function(name, idx) {
      var data = _trendData.records.map(function(rec) {
        var person = (rec.persons || []).find(function(p) { return p.name === name; });
        return trendValue(person, dataType);
      });
      return {
        label: name,
        data: data,
        borderColor: COLORS[idx % COLORS.length],
        backgroundColor: COLORS[idx % COLORS.length] + '20',
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.3,
        spanGaps: true,
      };
    });
  }

  var ctx = document.getElementById('chart-trend-canvas').getContext('2d');
  _trendChart = new Chart(ctx, {
    type: 'line',
    data: { labels: dates, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, boxHeight: 12, padding: 16, usePointStyle: true, pointStyle: 'circle', font: { size: 11 } } },
        tooltip: { callbacks: { label: function(ctx) { var suffix = isRate ? '%' : ' BUG'; return ctx.dataset.label + ': ' + ctx.parsed.y + suffix; } } }
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, max: isRate ? 100 : undefined, ticks: { stepSize: 1, callback: isRate ? function(v) { return v + '%'; } : undefined } }
      },
    },
  });
}

// ========== 设置页加载 ==========
function loadConfigPage() {
  try {
    API.get('/cache-info').then(function(data) {
      document.getElementById('config-cache-info').textContent = data.file_count + ' 个文件 · ' + data.total_mb + ' MB';
    }).catch(function() {
      document.getElementById('config-cache-info').textContent = '加载失败';
    });
    API.cookie.get().then(function(data) {
      if (data.has_cookie) {
        document.getElementById('config-cookie-result').textContent = '已配置';
        document.getElementById('config-cookie-result').style.color = 'var(--green)';
      } else {
        document.getElementById('config-cookie-result').textContent = '未配置';
        document.getElementById('config-cookie-result').style.color = 'var(--red)';
      }
    }).catch(function() {});
    API.get('/config').then(function(data) {
      var input = document.getElementById('config-expiration');
      if (input) input.value = data.expiration_hours;
      var schedEnabled = document.getElementById('config-schedule-enabled');
      if (schedEnabled) schedEnabled.checked = data.schedule_enabled;
      var schedHour = document.getElementById('config-schedule-hour');
      if (schedHour) schedHour.value = data.schedule_hour;
      // 加载催办偏好
      if (data.urge_style) _urgeStyle = data.urge_style;
      if (data.urge_custom_prompt !== undefined) _urgeCustomPrompt = data.urge_custom_prompt || '';
    }).catch(function() {});
    // 加载 AI 配置
    API.get('/ai/config').then(function(data) {
      var baseUrl = document.getElementById('config-ai-base-url');
      var apiKey = document.getElementById('config-ai-api-key');
      var model = document.getElementById('config-ai-model');
      if (baseUrl) baseUrl.value = data.base_url || '';
      if (apiKey) apiKey.value = data.api_key || '';
      if (model) model.value = data.model || '';
    }).catch(function() {});
    // 加载全局关注池统计
    API.get('/focus-pool').then(function(data) {
      document.getElementById('config-pool-info').textContent = data.count + ' 人在池中';
    }).catch(function() {
      document.getElementById('config-pool-info').textContent = '加载失败';
    });
  } catch (e) { console.error(e); }
}

// 设置页 Cookie 保存
document.addEventListener('DOMContentLoaded', function() {
  var saveBtn = document.getElementById('btn-config-save-cookie');
  var verifyBtn = document.getElementById('btn-config-verify-cookie');
  var cleanupBtn = document.getElementById('btn-config-cleanup');

  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var cookie = document.getElementById('config-cookie').value.trim();
      if (!cookie) { alert('请输入 Cookie'); return; }
      try {
        await API.cookie.update(cookie);
        document.getElementById('config-cookie').value = '';
        document.getElementById('config-cookie-result').textContent = '已保存';
        document.getElementById('config-cookie-result').style.color = 'var(--green)';
      } catch (e) { alert('保存失败'); console.error(e); }
    });
  }

  if (verifyBtn) {
    verifyBtn.addEventListener('click', async function() {
      var input = document.getElementById('config-cookie');
      var resultEl = document.getElementById('config-cookie-result');
      var cookie = input.value.trim();
      verifyBtn.disabled = true;
      verifyBtn.textContent = '检测中...';
      resultEl.textContent = '';
      try {
        var res = await API.cookie.verify(cookie);
        if (res.valid) {
          resultEl.textContent = res.message;
          resultEl.style.color = 'var(--green)';
          if (cookie) {
            await API.cookie.update(cookie);
            input.value = '';
          }
        } else {
          resultEl.textContent = res.message;
          resultEl.style.color = 'var(--red)';
        }
      } catch (e) {
        resultEl.textContent = '检测请求失败';
        resultEl.style.color = 'var(--red)';
      } finally {
        verifyBtn.disabled = false;
        verifyBtn.textContent = '检测';
      }
    });
  }

  if (cleanupBtn) {
    cleanupBtn.addEventListener('click', async function() {
      cleanupBtn.disabled = true;
      cleanupBtn.textContent = '清理中...';
      try {
        var data = await API.cleanup();
        alert('已清理 ' + data.deleted + ' 个文件，释放 ' + data.freed_mb + ' MB');
        API.get('/cache-info').then(function(d) {
          document.getElementById('config-cache-info').textContent = d.file_count + ' 个文件 · ' + d.total_mb + ' MB';
        }).catch(function() {});
      } catch (e) { alert('清理失败'); } finally {
        cleanupBtn.disabled = false;
        cleanupBtn.textContent = '清理旧文件';
      }
    });
  }

  var restartBtn = document.getElementById('btn-config-restart');
  if (restartBtn) {
    restartBtn.addEventListener('click', async function() {
      var resultEl = document.getElementById('config-restart-result');
      restartBtn.disabled = true;
      restartBtn.textContent = '重启中...';
      resultEl.textContent = '服务将在 2 秒后重新启动';
      resultEl.style.color = 'var(--green)';
      try {
        await API.post('/restart', {});
      } catch (e) {
        // 正常 — 重启时连接会断开
      }
    });
  }

  var expirationSaveBtn = document.getElementById('btn-config-save-expiration');
  if (expirationSaveBtn) {
    expirationSaveBtn.addEventListener('click', async function() {
      var input = document.getElementById('config-expiration');
      var resultEl = document.getElementById('config-expiration-result');
      var hours = parseInt(input.value, 10);
      if (isNaN(hours) || hours < 1 || hours > 720) {
        resultEl.textContent = '请输入 1-720 之间的整数';
        resultEl.style.color = 'var(--red)';
        return;
      }
      try {
        await API.put('/config', { expiration_hours: hours });
        resultEl.textContent = '已保存 · ' + hours + ' 小时';
        resultEl.style.color = 'var(--green)';
      } catch (e) {
        resultEl.textContent = '保存失败';
        resultEl.style.color = 'var(--red)';
      }
    });
  }

  var scheduleSaveBtn = document.getElementById('btn-config-save-schedule');
  if (scheduleSaveBtn) {
    scheduleSaveBtn.addEventListener('click', async function() {
      var enabledEl = document.getElementById('config-schedule-enabled');
      var hourEl = document.getElementById('config-schedule-hour');
      var resultEl = document.getElementById('config-schedule-result');
      var enabled = enabledEl ? enabledEl.checked : false;
      var hour = parseInt(hourEl ? hourEl.value : '9', 10);
      if (isNaN(hour) || hour < 0 || hour > 23) {
        resultEl.textContent = '请输入 0-23 之间的小时数';
        resultEl.style.color = 'var(--red)';
        return;
      }
      try {
        await API.put('/config', { schedule_enabled: enabled, schedule_hour: hour });
        resultEl.textContent = enabled ? '已保存 · 每天 ' + hour + ':00 自动下载' : '已关闭定时下载';
        resultEl.style.color = 'var(--green)';
      } catch (e) {
        resultEl.textContent = '保存失败';
        resultEl.style.color = 'var(--red)';
      }
    });
  }

  // AI 配置保存
  var aiSaveBtn = document.getElementById('btn-config-save-ai');
  if (aiSaveBtn) {
    aiSaveBtn.addEventListener('click', async function() {
      var baseUrl = document.getElementById('config-ai-base-url').value.trim();
      var apiKey = document.getElementById('config-ai-api-key').value.trim();
      var model = document.getElementById('config-ai-model').value.trim();
      var resultEl = document.getElementById('config-ai-result');
      try {
        await API.put('/ai/config', { base_url: baseUrl, api_key: apiKey, model: model });
        resultEl.textContent = '已保存';
        resultEl.style.color = 'var(--green)';
      } catch (e) {
        resultEl.textContent = '保存失败';
        resultEl.style.color = 'var(--red)';
      }
    });
  }

  // AI 连接检测
  var aiTestBtn = document.getElementById('btn-config-test-ai');
  if (aiTestBtn) {
    aiTestBtn.addEventListener('click', async function() {
      var resultEl = document.getElementById('config-ai-result');
      aiTestBtn.disabled = true;
      aiTestBtn.textContent = '检测中...';
      resultEl.textContent = '';
      try {
        var res = await API.post('/ai/test', {});
        if (res.ok) {
          resultEl.textContent = '连接成功: ' + res.message;
          resultEl.style.color = 'var(--green)';
        } else {
          resultEl.textContent = res.message;
          resultEl.style.color = 'var(--red)';
        }
      } catch (e) {
        resultEl.textContent = '检测请求失败';
        resultEl.style.color = 'var(--red)';
      } finally {
        aiTestBtn.disabled = false;
        aiTestBtn.textContent = '检测';
      }
    });
  }

  // 全局关注池导入
  var importPoolBtn = document.getElementById('btn-config-import-pool');
  if (importPoolBtn) {
    importPoolBtn.addEventListener('click', async function() {
      var fileInput = document.getElementById('config-pool-file');
      var file = fileInput ? fileInput.files[0] : null;
      var resultEl = document.getElementById('config-pool-result');
      var infoEl = document.getElementById('config-pool-info');
      if (!file) {
        resultEl.textContent = '请先选择文件';
        resultEl.style.color = 'var(--red)';
        return;
      }
      importPoolBtn.disabled = true;
      importPoolBtn.textContent = '导入中...';
      resultEl.textContent = '';
      try {
        var formData = new FormData();
        formData.append('file', file);
        var res = await API.upload('/focus-pool/import', formData);
        resultEl.textContent = '导入完成 · 新增 ' + res.added + ' 人 · 池中共 ' + res.total + ' 人';
        resultEl.style.color = 'var(--green)';
        if (infoEl) infoEl.textContent = res.total + ' 人在池中';
        fileInput.value = '';
      } catch (e) {
        resultEl.textContent = '导入失败: ' + (e.message || e);
        resultEl.style.color = 'var(--red)';
      } finally {
        importPoolBtn.disabled = false;
        importPoolBtn.textContent = '导入';
      }
    });
  }
});

// 欢迎页按钮 — 跳转到数据下载页
document.addEventListener('DOMContentLoaded', function() {
  var welcomeBtn = document.getElementById('btn-welcome-batch');
  if (welcomeBtn) {
    welcomeBtn.addEventListener('click', function() {
      navigateTo('batch');
    });
  }
});

// 事件委托：状态栏刷新链接（避免动态元素重复绑定）
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('status-refresh-link')) {
    e.preventDefault();
    refreshCurrentProject();
  }
});

// ========== 邮件报告 ==========
var _emailTrendChart = null;
var _emailHTML = '';
var _emailTrendData = null;

// ========== 一键催办 ==========
var _selectedPersonName = '';
var _urgeScope = 'all';
var _urgeStyle = 'formal';
var _urgeCustomPrompt = '';

function isActive(st) {
  if (!st) return true;
  var s = st.toLowerCase();
  return s.indexOf('closed') === -1 && s.indexOf('已关闭') === -1 && s.indexOf('resolved') === -1 && s.indexOf('已解决') === -1;
}

function getUrgeTargets(scope) {
  if (scope === 'single' && _selectedPersonName) {
    return _currentPersons.filter(function(p) { return p.name === _selectedPersonName && (p.active || 0) > 0; });
  }
  var t = _currentPersons.filter(function(p) { return p.focus && (p.active || 0) > 0; });
  t.sort(function(a, b) { return (b.active || 0) - (a.active || 0); });
  return t;
}

function generateUrgeText(scope) {
  var projectName = '';
  var sel = document.getElementById('project-select');
  if (sel) { var opt = sel.selectedOptions[0]; projectName = opt ? opt.textContent : ''; }

  var targets = getUrgeTargets(scope);
  if (!targets.length) return '没有激活 BUG';

  var lines = ['【' + projectName + '】', ''];

  targets.forEach(function(p) {
    var activeBugs = (p.bugs || []).filter(function(b) { return isActive(b.status); });
    activeBugs.sort(function(a, b) {
      var order = { S: 0, A: 1, B: 2, C: 3 };
      return (order[a.severity] || 9) - (order[b.severity] || 9);
    });

    var sCount = 0, aCount = 0;
    activeBugs.forEach(function(b) { if (b.severity === 'S') sCount++; if (b.severity === 'A') aCount++; });
    var hi = [];
    if (sCount > 0) hi.push('S级' + sCount + '个');
    if (aCount > 0) hi.push('A级' + aCount + '个');
    var hiStr = hi.length ? '，其中' + hi.join('、') : '';

    lines.push('@' + p.name + '：有 ' + activeBugs.length + ' 个激活BUG' + hiStr);
    activeBugs.forEach(function(b) {
      var sevTag = '[' + (b.severity || '-') + ']';
      lines.push('  ' + sevTag + ' #' + b.id + ' ' + (b.title || ''));
      lines.push('  https://zd.bicv.com/bug-view-' + b.id + '.html');
    });
    lines.push('');
  });
  return lines.join('\n');
}

async function generateUrgeWithAI(scope) {
  var projectName = '';
  var sel = document.getElementById('project-select');
  if (sel) { var opt = sel.selectedOptions[0]; projectName = opt ? opt.textContent : ''; }

  var targets = getUrgeTargets(scope);
  if (!targets.length) return { text: '没有激活 BUG', source: 'none' };

  // 实时读取输入框的值（而非依赖 blur 事件）
  var extraInput = document.getElementById('urge-extra-prompt');
  var extra = extraInput ? extraInput.value.trim() : _urgeCustomPrompt;

  try {
    var res = await API.post('/urge/generate', {
      targets: targets,
      project_name: projectName,
      style: _urgeStyle,
      extra_prompt: extra
    });
    if (res.source === 'ai' && res.text) return { text: res.text, source: 'ai' };
    // 降级到模板
    return { text: generateUrgeText(scope), source: 'fallback' };
  } catch (e) {
    return { text: generateUrgeText(scope), source: 'fallback' };
  }
}

function openUrgeModal(scope) {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  if (!_currentPersons || !_currentPersons.length) { alert('请先加载数据'); return; }

  _urgeScope = scope;
  var titleEl = document.getElementById('urge-modal-title');
  var btnAll = document.getElementById('btn-urge-scope-all');
  var btnSingle = document.getElementById('btn-urge-scope-single');
  var textarea = document.getElementById('urge-text-preview');
  var aiStatus = document.getElementById('urge-ai-status');
  var sourceHint = document.getElementById('urge-source-hint');
  var regenBtn = document.getElementById('btn-urge-regenerate');
  var extraInput = document.getElementById('urge-extra-prompt');

  // 设置范围按钮
  if (scope === 'single' && _selectedPersonName) {
    titleEl.textContent = '催办 · ' + _selectedPersonName;
    btnSingle.style.background = 'var(--near-black)';
    btnSingle.style.color = '#fff';
    btnSingle.style.borderColor = 'transparent';
    btnAll.style.background = 'transparent';
    btnAll.style.color = 'var(--slate)';
    btnAll.style.borderColor = 'var(--input-border)';
    btnSingle.textContent = _selectedPersonName;
  } else {
    titleEl.textContent = '催办 · 全部关注';
    btnAll.style.background = 'var(--near-black)';
    btnAll.style.color = '#fff';
    btnAll.style.borderColor = 'transparent';
    btnSingle.style.background = 'transparent';
    btnSingle.style.color = 'var(--slate)';
    btnSingle.style.borderColor = 'var(--input-border)';
    btnSingle.textContent = _selectedPersonName ? '仅 ' + _selectedPersonName : '当前人员';
  }

  // 设置当前风格按钮
  document.querySelectorAll('.urge-style-btn').forEach(function(btn) {
    if (btn.dataset.style === _urgeStyle) {
      btn.style.background = 'var(--near-black)';
      btn.style.color = '#fff';
      btn.style.borderColor = 'transparent';
    } else {
      btn.style.background = 'transparent';
      btn.style.color = 'var(--slate)';
      btn.style.borderColor = 'var(--input-border)';
    }
  });

  // 设置额外提示词
  if (extraInput) extraInput.value = _urgeCustomPrompt;

  document.getElementById('urge-modal').style.display = 'flex';

  // 加载中状态
  textarea.value = '正在生成...';
  textarea.style.color = 'var(--silver)';
  if (aiStatus) aiStatus.style.display = 'inline';
  if (sourceHint) sourceHint.textContent = '';
  if (regenBtn) regenBtn.style.display = 'none';

  generateUrgeWithAI(scope).then(function(result) {
    textarea.value = result.text;
    textarea.style.color = '';
    if (aiStatus) aiStatus.style.display = 'none';
    if (sourceHint) {
      sourceHint.textContent = result.source === 'ai' ? 'AI 生成' : '模板生成（AI 不可用）';
    }
    if (regenBtn) regenBtn.style.display = 'inline-block';
  });
}

// 基础按钮事件
document.getElementById('btn-urge-reminder').addEventListener('click', function() {
  openUrgeModal('all');
});

document.getElementById('btn-urge-modal-close').addEventListener('click', function() {
  document.getElementById('urge-modal').style.display = 'none';
});
document.getElementById('btn-urge-modal-close2').addEventListener('click', function() {
  document.getElementById('urge-modal').style.display = 'none';
});
document.getElementById('urge-modal').addEventListener('click', function(e) {
  if (e.target === this) document.getElementById('urge-modal').style.display = 'none';
});

// 范围切换
document.getElementById('btn-urge-scope-all').addEventListener('click', function() {
  openUrgeModal('all');
});
document.getElementById('btn-urge-scope-single').addEventListener('click', function() {
  if (!_selectedPersonName) { alert('请先在左侧选择人员'); return; }
  openUrgeModal('single');
});

// 风格切换
document.querySelectorAll('.urge-style-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    _urgeStyle = this.dataset.style;
    document.querySelectorAll('.urge-style-btn').forEach(function(b) {
      b.style.background = 'transparent';
      b.style.color = 'var(--slate)';
      b.style.borderColor = 'var(--input-border)';
    });
    this.style.background = 'var(--near-black)';
    this.style.color = '#fff';
    this.style.borderColor = 'transparent';
    // 仅保存偏好，不自动重新生成（用户可点"重新生成"按钮）
    API.put('/config', { urge_style: _urgeStyle }).catch(function() {});
  });
});

// 额外提示词失焦保存
var extraPromptInput = document.getElementById('urge-extra-prompt');
if (extraPromptInput) {
  extraPromptInput.addEventListener('change', function() {
    _urgeCustomPrompt = this.value;
    API.put('/config', { urge_custom_prompt: _urgeCustomPrompt }).catch(function() {});
  });
}

// 重新生成
document.getElementById('btn-urge-regenerate').addEventListener('click', function() {
  openUrgeModal(_urgeScope);
});

// 复制
document.getElementById('btn-urge-copy').addEventListener('click', function() {
  var text = document.getElementById('urge-text-preview').value;
  var btn = this;
  var orig = btn.textContent;
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = '已复制';
    setTimeout(function() { btn.textContent = orig; }, 2000);
  }).catch(function() {
    prompt('请手动复制（Ctrl+C）：', text);
    btn.textContent = orig;
  });
});

document.getElementById('btn-email-report').addEventListener('click', async function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  if (!_currentPersons || !_currentPersons.length) { alert('请先加载数据'); return; }

  document.getElementById('email-report-modal').style.display = 'flex';
  switchEmailTab('html');

  try { _emailTrendData = await API.trend.get(pid); } catch(e) { _emailTrendData = null; }
  _emailHTML = generateEmailHTML(pid);
  document.getElementById('email-html-preview').innerHTML = _emailHTML;
});

function switchEmailTab(tab) {
  document.querySelectorAll('.email-tab-btn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.querySelector('.email-tab-btn[data-email-tab="' + tab + '"]');
  if (btn) btn.classList.add('active');
  document.querySelectorAll('.email-tab-content').forEach(function(c) { c.style.display = 'none'; });
  var content = document.getElementById('email-tab-' + tab);
  if (content) content.style.display = 'flex';

  if (tab === 'trend') setTimeout(renderEmailTrendChart, 100);
}

document.addEventListener('click', function(e) {
  if (!e.target.classList.contains('email-tab-btn')) return;
  switchEmailTab(e.target.dataset.emailTab);
});

document.getElementById('btn-email-modal-close').addEventListener('click', closeEmailModal);
document.getElementById('email-report-modal').addEventListener('click', function(e) {
  if (e.target === this) closeEmailModal();
});

function closeEmailModal() {
  document.getElementById('email-report-modal').style.display = 'none';
  if (_emailTrendChart) { _emailTrendChart.destroy(); _emailTrendChart = null; }
  _emailTrendData = null;
}

// ========== 复制 HTML 到剪贴板 ==========
document.getElementById('btn-copy-email-html').addEventListener('click', async function() {
  var btn = this;
  var origText = btn.textContent;
  try {
    var plainText = _emailHTML.replace(/<[^>]*>/g, '\n').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/\n{3,}/g, '\n\n').trim();
    var blobHTML = new Blob([_emailHTML], { type: 'text/html' });
    var blobText = new Blob([plainText], { type: 'text/plain' });
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': blobHTML,
      'text/plain': blobText
    })]);
    btn.textContent = '已复制';
  } catch (e) {
    // 降级为纯文本
    try {
      var txt = _emailHTML.replace(/<[^>]*>/g, '\n').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/\n{3,}/g, '\n\n').trim();
      await navigator.clipboard.writeText(txt);
      btn.textContent = '已复制';
    } catch (e2) {
      btn.textContent = '失败';
    }
  }
  setTimeout(function() { btn.textContent = origText; }, 2000);
});

// ========== 邮件 HTML 生成 ==========
function generateEmailHTML(projectId) {
  var projectName = '';
  var sel = document.getElementById('project-select');
  if (sel) {
    var opt = sel.selectedOptions[0];
    projectName = opt ? opt.textContent : '';
  }

  var focusPersons = _currentPersons.filter(function(p) { return p.focus; });
  // 有激活BUG的排在前面（按激活数降序），0激活的排在最后
  focusPersons.sort(function(a, b) {
    var aActive = a.active || 0;
    var bActive = b.active || 0;
    if (aActive > 0 && bActive === 0) return -1;
    if (aActive === 0 && bActive > 0) return 1;
    return bActive - aActive;
  });

  // 环比数据已移除

  var totalActive = 0;
  var totalS = 0;
  var totalA = 0;
  var totalNew = 0;
  focusPersons.forEach(function(p) {
    totalActive += p.active || 0;
    totalS += p.S || 0;
    totalA += p.A || 0;
    totalNew += p.new_count || 0;
  });
  // 激活环比变化已移除

  var maxActive = 0;
  focusPersons.forEach(function(p) { if (p.active > maxActive) maxActive = p.active; });

  // 高危 BUG 列表
  var hiBugs = [];
  focusPersons.forEach(function(p) {
    (p.bugs || []).forEach(function(b) {
      var sev = b.severity || '';
      var st = b.status || '';
      if ((sev === 'S' || sev === 'A') && st.indexOf('关闭') === -1 && st.indexOf('closed') === -1) {
        hiBugs.push({ name: p.name, id: b.id, title: b.title, severity: sev, isNew: b.is_new });
      }
    });
  });
    var dateStr = new Date().toISOString().slice(0, 10);

  var html = '<div style="max-width:600px;font-family:-apple-system,BlinkMacSystemFont,\'Microsoft YaHei\',\'PingFang SC\',sans-serif;color:#1c2024;line-height:1.6;">';

  // 标题栏
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;" cellpadding="0" cellspacing="0" border="0"><tr>';
  html += '<td style="padding:16px 0 12px 0;border-bottom:3px solid #1e40af;">';
  html += '<div style="font-size:20px;font-weight:700;color:#1e40af;letter-spacing:-0.3px;">' + escHtml(projectName) + '</div>';
  html += '<div style="font-size:12px;color:#4b5563;margin-top:2px;">BUG 报告 &middot; ' + dateStr + '</div>';
  html += '</td></tr></table>';

  // 总览卡片
  var totalB = focusPersons.reduce(function(s,p){return s+(p.B||0);},0);
  var totalC = focusPersons.reduce(function(s,p){return s+(p.C||0);},0);
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;background:#f8fafc;border-left:3px solid #1e40af;" cellpadding="0" cellspacing="0" border="0">';

  // 第一行：关键指标
  html += '<tr>';
  html += '<td style="padding:18px 14px 8px 14px;text-align:center;">';
  html += '<div style="font-size:10px;color:#4b5563;letter-spacing:1px;margin-bottom:2px;">激活 BUG</div>';
  html += '<div style="font-size:28px;font-weight:700;color:#1e40af;line-height:1;">' + totalActive + '</div>';
  html += '</td>';
  html += '</tr>';

  // 第二行：严重级别分布
  html += '<tr>';
  html += '<td colspan="2" style="padding:4px 14px 14px 14px;text-align:center;">';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#1e40af;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">S ' + totalS + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#3b82f6;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">A ' + totalA + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#64748b;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">B ' + totalB + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#6b7280;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">C ' + totalC + '</span>';
  html += '</td>';
  html += '</tr>';

  html += '</table>';

  // 人员表格
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;" cellpadding="0" cellspacing="0" border="0">';
  html += '<thead><tr style="border-bottom:2px solid #1e40af;">';
  html += '<th style="text-align:left;padding:8px 10px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;">人员</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;width:42px;">激活</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;width:38px;">S</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;width:38px;">A</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;width:38px;">B</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;text-transform:uppercase;width:38px;">C</th>';
  html += '</tr></thead><tbody>';

  focusPersons.forEach(function(p, idx) {
    var barPct = maxActive > 0 ? Math.round((p.active || 0) / maxActive * 100) : 0;
    var rowBg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';

    html += '<tr style="background:' + rowBg + ';">';
    html += '<td style="padding:9px 10px;font-weight:600;font-size:13px;border-bottom:1px solid #eef0f2;">' + escHtml(p.name) + '</td>';
    html += '<td style="text-align:center;padding:9px 4px;font-weight:600;font-size:13px;border-bottom:1px solid #eef0f2;">' + (p.active || 0) + '</td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#1e40af;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.S || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#3b82f6;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.A || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#64748b;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.B || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#6b7280;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.C || 0) + '</span></td>';
    html += '</tr>';
    html += '<tr style="background:' + rowBg + ';"><td colspan="6" style="padding:0 10px 6px 10px;border-bottom:1px solid #eef0f2;">';
    html += '<div style="height:3px;background:#eef0f2;border-radius:0 2px 2px 0;">';
    html += '<div style="height:100%;width:' + barPct + '%;background:#2563eb;border-radius:0 2px 2px 0;min-width:' + (barPct > 0 ? '2px' : '0') + ';"></div>';
    html += '</div></td></tr>';
  });
  html += '</tbody></table>';

  // 高危 BUG 清单
  if (hiBugs.length > 0) {
    html += '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;" cellpadding="0" cellspacing="0" border="0">';
    html += '<tr><td style="padding:10px 14px;background:#eff6ff;border-left:3px solid #1e40af;">';
    html += '<span style="font-size:13px;font-weight:700;color:#1e40af;">高危 BUG</span>';
    html += '<span style="font-size:11px;color:#64748b;margin-left:6px;">S / A 级未关闭 &middot; ' + hiBugs.length + ' 个</span>';
    html += '</td></tr></table>';
    html += '<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:24px;" cellpadding="0" cellspacing="0" border="0">';
    hiBugs.forEach(function(b, idx) {
      var sevBg = b.severity === 'S' ? '#eff6ff' : '#f8fafc';
      var sevColor = b.severity === 'S' ? '#1e40af' : '#3b82f6';
      var newBadge = b.isNew ? ' <span style="display:inline-block;background:#dbeafe;color:#1e40af;font-size:9px;font-weight:600;padding:0 5px;border-radius:2px;line-height:16px;margin-left:4px;">NEW</span>' : '';
      html += '<tr style="background:' + sevBg + ';">';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #e0e7ff;white-space:nowrap;width:80px;">';
      html += '<a href="https://zd.bicv.com/bug-view-' + b.id + '.html" style="color:#2563eb;text-decoration:none;font-weight:500;font-size:12px;" target="_blank">#' + b.id + '</a>';
      html += '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #e0e7ff;font-size:12px;">' + escHtml(b.title) + newBadge + '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #e0e7ff;text-align:center;width:40px;">';
      html += '<span style="display:inline-block;width:20px;height:20px;line-height:20px;background:' + sevColor + ';color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + b.severity + '</span>';
      html += '</td>';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #e0e7ff;font-size:12px;color:#64748b;width:60px;white-space:nowrap;">' + escHtml(b.name) + '</td>';
      html += '</tr>';
    });
    html += '</table>';
  }

  // 脚注
  html += '<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0" border="0"><tr>';
  html += '<td style="padding-top:12px;border-top:1px solid #e5e7eb;font-size:10px;color:#6b7280;">';
  html += '禅道 BUG 分析 &middot; COC人员 &middot; ' + dateStr;
  html += '</td></tr></table>';

  html += '</div>';
  return html;
}

// ========== 周报 ==========
var _weeklyHTML = '';

document.getElementById('btn-weekly-report').addEventListener('click', async function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  if (!_currentPersons || !_currentPersons.length) { alert('请先加载数据'); return; }

  document.getElementById('weekly-report-modal').style.display = 'flex';

  try { _emailTrendData = await API.trend.get(pid); } catch(e) { _emailTrendData = null; }
  var newIds = [];
  try { var cmp = await API.analyze.compare(pid); newIds = cmp.new_ids || []; } catch(e) {}
  _weeklyHTML = generateWeeklyHTML(pid, newIds);
  document.getElementById('weekly-html-preview').innerHTML = _weeklyHTML;
});

document.getElementById('btn-weekly-modal-close').addEventListener('click', closeWeeklyModal);
document.getElementById('weekly-report-modal').addEventListener('click', function(e) {
  if (e.target === this) closeWeeklyModal();
});

function closeWeeklyModal() {
  document.getElementById('weekly-report-modal').style.display = 'none';
  _weeklyHTML = '';
}

function generateWeeklyHTML(projectId, newBugIds) {
  var projectName = '';
  var sel = document.getElementById('project-select');
  if (sel) { var opt = sel.selectedOptions[0]; projectName = opt ? opt.textContent : ''; }

  var focusPersons = _currentPersons.filter(function(p) { return p.focus; });
  focusPersons.sort(function(a, b) {
    var aA = a.active || 0; var bA = b.active || 0;
    if (aA > 0 && bA === 0) return -1;
    if (aA === 0 && bA > 0) return 1;
    return bA - aA;
  });

  // 日期范围
  var startDate = '', endDate = new Date().toISOString().slice(0, 10);
  if (_emailTrendData && _emailTrendData.records && _emailTrendData.records.length > 0) {
    var recent = _emailTrendData.records.slice(-7);
    startDate = recent[0].date;
    endDate = recent[recent.length - 1].date;
  }

  // 本周新增 BUG 列表
  var newBugSet = new Set(newBugIds || []);
  var newBugs = [];
  focusPersons.forEach(function(p) {
    (p.bugs || []).forEach(function(b) {
      if (newBugSet.has(String(b.id))) newBugs.push({ name: p.name, id: b.id, title: b.title, severity: b.severity });
    });
  });

  // 环比数据已移除

  var totalActive = focusPersons.reduce(function(s, p) { return s + (p.active || 0); }, 0);
  var totalS = focusPersons.reduce(function(s, p) { return s + (p.S || 0); }, 0);
  var totalA = focusPersons.reduce(function(s, p) { return s + (p.A || 0); }, 0);
  var totalB = focusPersons.reduce(function(s, p) { return s + (p.B || 0); }, 0);
  var totalC = focusPersons.reduce(function(s, p) { return s + (p.C || 0); }, 0);
  var maxActive = 0;
  focusPersons.forEach(function(p) { if ((p.active || 0) > maxActive) maxActive = p.active || 0; });

  var html = '<div style="max-width:600px;font-family:-apple-system,BlinkMacSystemFont,\'Microsoft YaHei\',\'PingFang SC\',sans-serif;color:#1c2024;line-height:1.6;">';

  // 标题栏
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;" cellpadding="0" cellspacing="0" border="0"><tr>';
  html += '<td style="padding:16px 0 12px 0;border-bottom:3px solid #1e40af;">';
  html += '<div style="font-size:20px;font-weight:700;color:#1e40af;letter-spacing:-0.3px;">' + escHtml(projectName) + '</div>';
  html += '<div style="font-size:12px;color:#4b5563;margin-top:2px;">周报 &middot; ' + startDate + ' ~ ' + endDate + '</div>';
  html += '</td></tr></table>';

  // 总览卡片
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;background:#f8fafc;border-left:3px solid #1e40af;" cellpadding="0" cellspacing="0" border="0">';
  html += '<tr>';
  html += '<td style="width:50%;padding:18px 14px 8px 14px;text-align:center;">';
  html += '<div style="font-size:10px;color:#4b5563;letter-spacing:1px;margin-bottom:2px;">激活 BUG</div>';
  html += '<div style="font-size:28px;font-weight:700;color:#1e40af;line-height:1;">' + totalActive + '</div>';
  html += '</td>';
  html += '<td style="width:50%;padding:18px 14px 8px 14px;text-align:center;">';
  html += '<div style="font-size:10px;color:#4b5563;letter-spacing:1px;margin-bottom:2px;">本周新增</div>';
  html += '<div style="font-size:28px;font-weight:700;color:#3b82f6;line-height:1;">' + (newBugs.length || 0) + '</div>';
  html += '</td>';
  html += '</tr>';
  html += '<tr>';
  html += '<td colspan="2" style="padding:4px 14px 14px 14px;text-align:center;">';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#1e40af;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">S ' + totalS + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#3b82f6;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">A ' + totalA + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#64748b;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">B ' + totalB + '</span>';
  html += '<span style="display:inline-block;min-width:40px;height:22px;line-height:22px;background:#6b7280;color:#fff;border-radius:3px;font-size:11px;font-weight:600;margin:0 4px;">C ' + totalC + '</span>';
  html += '</td></tr></table>';

  // 人员表格
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;" cellpadding="0" cellspacing="0" border="0">';
  html += '<thead><tr style="border-bottom:2px solid #1e40af;">';
  html += '<th style="text-align:left;padding:8px 10px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;">人员</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;width:42px;">激活</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;width:38px;">S</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;width:38px;">A</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;width:38px;">B</th>';
  html += '<th style="text-align:center;padding:8px 4px;font-size:10px;color:#4b5563;font-weight:600;letter-spacing:1px;width:38px;">C</th>';
  html += '</tr></thead><tbody>';

  focusPersons.forEach(function(p, idx) {
    var barPct = maxActive > 0 ? Math.round((p.active || 0) / maxActive * 100) : 0;
    var rowBg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';

    html += '<tr style="background:' + rowBg + ';">';
    html += '<td style="padding:9px 10px;font-weight:600;font-size:13px;border-bottom:1px solid #eef0f2;">' + escHtml(p.name) + '</td>';
    html += '<td style="text-align:center;padding:9px 4px;font-weight:600;font-size:13px;border-bottom:1px solid #eef0f2;">' + (p.active || 0) + '</td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#1e40af;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.S || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#3b82f6;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.A || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#64748b;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.B || 0) + '</span></td>';
    html += '<td style="text-align:center;padding:9px 4px;border-bottom:1px solid #eef0f2;"><span style="display:inline-block;min-width:22px;height:20px;line-height:20px;background:#6b7280;color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + (p.C || 0) + '</span></td>';
    html += '</tr>';
    html += '<tr style="background:' + rowBg + ';"><td colspan="6" style="padding:0 10px 6px 10px;border-bottom:1px solid #eef0f2;">';
    html += '<div style="height:3px;background:#eef0f2;border-radius:0 2px 2px 0;">';
    html += '<div style="height:100%;width:' + barPct + '%;background:#2563eb;border-radius:0 2px 2px 0;min-width:' + (barPct > 0 ? '2px' : '0') + ';"></div>';
    html += '</div></td></tr>';
  });
  html += '</tbody></table>';

  // 本周新增 BUG 清单
  if (newBugs.length > 0) {
    html += '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;" cellpadding="0" cellspacing="0" border="0">';
    html += '<tr><td style="padding:10px 14px;background:#eff6ff;border-left:3px solid #1e40af;">';
    html += '<span style="font-size:13px;font-weight:700;color:#1e40af;">本周新增 BUG</span>';
    html += '<span style="font-size:11px;color:#64748b;margin-left:6px;">' + newBugs.length + ' 个</span>';
    html += '</td></tr></table>';
    html += '<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:24px;" cellpadding="0" cellspacing="0" border="0">';
    newBugs.forEach(function(b, idx) {
      var sevColor = b.severity === 'S' ? '#1e40af' : (b.severity === 'A' ? '#3b82f6' : (b.severity === 'B' ? '#64748b' : '#6b7280'));
      var rowBg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';
      html += '<tr style="background:' + rowBg + ';">';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #eef0f2;width:80px;">';
      html += '<a href="https://zd.bicv.com/bug-view-' + b.id + '.html" style="color:#2563eb;text-decoration:none;font-weight:500;font-size:12px;" target="_blank">#' + b.id + '</a>';
      html += '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #eef0f2;font-size:12px;">' + escHtml(b.title) + '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #eef0f2;text-align:center;width:40px;">';
      html += '<span style="display:inline-block;width:20px;height:20px;line-height:20px;background:' + sevColor + ';color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + b.severity + '</span>';
      html += '</td>';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #eef0f2;font-size:12px;color:#64748b;width:60px;">' + escHtml(b.name) + '</td>';
      html += '</tr>';
    });
    html += '</table>';
  }

  // 高危 BUG 清单
  var hiBugs = [];
  focusPersons.forEach(function(p) {
    (p.bugs || []).forEach(function(b) {
      var sev = b.severity || '';
      var st = b.status || '';
      if ((sev === 'S' || sev === 'A') && st.indexOf('关闭') === -1 && st.indexOf('closed') === -1 && st.indexOf('已解决') === -1 && st.indexOf('resolved') === -1) {
        hiBugs.push({ name: p.name, id: b.id, title: b.title, severity: sev, isNew: newBugSet.has(String(b.id)) });
      }
    });
  });
  if (hiBugs.length > 0) {
    html += '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;" cellpadding="0" cellspacing="0" border="0">';
    html += '<tr><td style="padding:10px 14px;background:#eff6ff;border-left:3px solid #1e40af;">';
    html += '<span style="font-size:13px;font-weight:700;color:#1e40af;">高危 BUG</span>';
    html += '<span style="font-size:11px;color:#64748b;margin-left:6px;">S / A 级激活 &middot; ' + hiBugs.length + ' 个</span>';
    html += '</td></tr></table>';
    html += '<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:24px;" cellpadding="0" cellspacing="0" border="0">';
    hiBugs.forEach(function(b, idx) {
      var sevBg = b.severity === 'S' ? '#eff6ff' : '#f8fafc';
      var sevColor = b.severity === 'S' ? '#1e40af' : '#3b82f6';
      var newBadge = b.isNew ? ' <span style="display:inline-block;background:#dbeafe;color:#1e40af;font-size:9px;font-weight:600;padding:0 5px;border-radius:2px;line-height:16px;margin-left:4px;">NEW</span>' : '';
      var rowBg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';
      html += '<tr style="background:' + rowBg + ';">';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #e0e7ff;width:80px;">';
      html += '<a href="https://zd.bicv.com/bug-view-' + b.id + '.html" style="color:#2563eb;text-decoration:none;font-weight:500;font-size:12px;" target="_blank">#' + b.id + '</a>';
      html += '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #e0e7ff;font-size:12px;">' + escHtml(b.title) + newBadge + '</td>';
      html += '<td style="padding:7px 8px;border-bottom:1px solid #e0e7ff;text-align:center;width:40px;">';
      html += '<span style="display:inline-block;width:20px;height:20px;line-height:20px;background:' + sevColor + ';color:#fff;border-radius:3px;font-size:11px;font-weight:600;">' + b.severity + '</span>';
      html += '</td>';
      html += '<td style="padding:7px 10px;border-bottom:1px solid #e0e7ff;font-size:12px;color:#64748b;width:60px;">' + escHtml(b.name) + '</td>';
      html += '</tr>';
    });
    html += '</table>';
  }

  // 脚注
  html += '<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0" border="0"><tr>';
  html += '<td style="padding-top:12px;border-top:1px solid #e5e7eb;font-size:10px;color:#6b7280;">';
  html += '禅道 BUG 分析 &middot; 周报 &middot; ' + startDate + ' ~ ' + endDate;
  html += '</td></tr></table>';

  html += '</div>';
  return html;
}

// 周报复制
document.getElementById('btn-copy-weekly-html').addEventListener('click', function() {
  var btn = this;
  var orig = btn.textContent;
  try {
    var plainText = _weeklyHTML.replace(/<[^>]*>/g, '\n').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/\n{3,}/g, '\n\n').trim();
    var blobHTML = new Blob([_weeklyHTML], { type: 'text/html' });
    var blobText = new Blob([plainText], { type: 'text/plain' });
    navigator.clipboard.write([new ClipboardItem({
      'text/html': blobHTML,
      'text/plain': blobText
    })]).then(function() {
      btn.textContent = '已复制';
      setTimeout(function() { btn.textContent = orig; }, 2000);
    }).catch(function() {
      navigator.clipboard.writeText(plainText).then(function() {
        btn.textContent = '已复制';
        setTimeout(function() { btn.textContent = orig; }, 2000);
      }).catch(function() {
        alert('复制失败');
        btn.textContent = orig;
      });
    });
  } catch (e) {
    alert('复制失败');
    btn.textContent = orig;
  }
});

// 周报下载
document.getElementById('btn-download-weekly-html').addEventListener('click', function() {
  var btn = this;
  var orig = btn.textContent;
  var projectName = '';
  var sel = document.getElementById('project-select');
  if (sel) { var opt = sel.selectedOptions[0]; projectName = opt ? opt.textContent.replace(/[\\/:*?"<>|]/g, '_') : 'report'; }
  var fullHTML = '<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>' + projectName + ' 周报</title></head><body style="margin:0;padding:16px;background:#f5f5f5;">' + _weeklyHTML + '</body></html>';
  var blob = new Blob([fullHTML], { type: 'text/html' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = projectName + '_周报_' + new Date().toISOString().slice(0, 10) + '.html';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  btn.textContent = '已下载';
  setTimeout(function() { btn.textContent = orig; }, 2000);
});

// ========== 邮件趋势图 ==========
function renderEmailTrendChart() {
  if (_emailTrendChart) { _emailTrendChart.destroy(); _emailTrendChart = null; }
  if (!_emailTrendData || !_emailTrendData.records || _emailTrendData.records.length === 0) return;

  var focusNames = [];
  _currentPersons.forEach(function(p) {
    if (p.focus) focusNames.push(p.name);
  });
  if (!focusNames.length) return;

  var dates = _emailTrendData.records.map(function(r) { return r.date.replace(/^\d{4}-/, ''); });

  // 每个日期，COC人员的激活数合计
  var activeData = _emailTrendData.records.map(function(rec) {
    var sum = 0;
    (rec.persons || []).forEach(function(p) {
      if (focusNames.indexOf(p.name) !== -1) sum += (p.active || 0);
    });
    return sum;
  });

  var canvas = document.getElementById('email-trend-canvas');
  canvas.width = 700;
  canvas.height = 380;
  var ctx = canvas.getContext('2d');

  _emailTrendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [{
        label: '激活 BUG 数量',
        data: activeData,
        borderColor: '#d93025',
        backgroundColor: 'rgba(217,48,37,0.08)',
        borderWidth: 3,
        pointRadius: 5,
        pointBackgroundColor: '#d93025',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointHoverRadius: 7,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: false,
      plugins: {
        dataLabels: false,
        legend: { display: false },
        title: {
          display: true,
          text: 'COC人员激活 BUG 趋势',
          font: { size: 16, weight: '700' },
          color: '#1c2024',
          padding: { bottom: 16 },
        },
      },
      scales: {
        x: {
          ticks: { font: { size: 12 }, color: '#60646c', maxRotation: 30 },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          ticks: { font: { size: 12 }, color: '#60646c', precision: 0, stepSize: 1 },
          grid: { color: 'rgba(0,0,0,0.06)' },
        },
      },
    },
    plugins: [{
      id: 'emailTrendLabels',
      afterDatasetsDraw: function(chart) {
        var meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data || meta.data.length < 2) return;
        var ctx = chart.ctx;
        var points = meta.data;
        // 只在首尾标注
        [0, points.length - 1].forEach(function(idx) {
          var pt = points[idx];
          var val = chart.data.datasets[0].data[idx];
          if (val === null || val === undefined) return;
          ctx.save();
          ctx.font = 'bold 14px -apple-system, sans-serif';
          ctx.fillStyle = '#d93025';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(val, pt.x, pt.y - 10);
          ctx.restore();
        });
      },
    }],
  });
}

// ========== 下载图表 PNG ==========
document.getElementById('btn-download-trend-png').addEventListener('click', function() {
  var canvas = document.getElementById('email-trend-canvas');
  if (!canvas.toDataURL) return;
  var link = document.createElement('a');
  link.download = 'bug_trend_chart.png';
  link.href = canvas.toDataURL('image/png');
  link.click();
});

// ========== 初始化 ==========
// 定时任务通知轮询
function pollScheduleResult() {
  API.get('/schedule/last-result').then(function(result) {
    if (!result || !result.time) return;
    // 服务端持久化的关闭标记，跨重启可靠
    if (result.dismissed_time && result.dismissed_time >= result.time) return;

    var banner = document.getElementById('schedule-notify-banner');
    var textEl = document.getElementById('schedule-notify-text');
    if (!banner || !textEl) return;

    var okCount = result.ok_count || 0;
    var failCount = result.fail_count || 0;
    var results = result.results || [];
    var parts = ['定时下载完成: ' + okCount + ' 成功'];
    if (failCount > 0) parts.push(failCount + ' 失败');
    if (results.length > 0) {
      parts.push('(' + results.map(function(r) { return r.name || r.project_id; }).join(', ') + ')');
    }
    textEl.textContent = parts.join(' · ');

    if (failCount > 0) {
      banner.style.background = '#fef3c7';
      banner.style.borderColor = '#f59e0b';
    } else {
      banner.style.background = '#e8f0fe';
      banner.style.borderColor = '#c4d7f2';
    }
    banner.style.display = 'flex';
  }).catch(function() {});
}

function dismissScheduleNotify() {
  document.getElementById('schedule-notify-banner').style.display = 'none';
  API.post('/schedule/dismiss').catch(function() {});
}

// Cookie 预警
function checkCookieWarn() {
  API.get('/cookie/status').then(function(status) {
    var banner = document.getElementById('cookie-warn-banner');
    var textEl = document.getElementById('cookie-warn-text');
    var actionsEl = document.getElementById('cookie-warn-actions');
    if (!banner || !textEl) return;

    if (!status.has_cookie) {
      textEl.textContent = '尚未配置 Cookie，无法下载 BUG 数据。请前往设置页配置。';
      actionsEl.innerHTML = '<button class="btn btn-primary btn-sm" onclick="navigateTo(\'config\');return false;">前往设置</button>';
      if (!status.dismissed_at) banner.style.display = 'flex';
    } else if (status.valid === false && status.last_checked) {
      textEl.textContent = 'Cookie 已失效 (' + (status.message || '请更新') + ')，数据下载将失败。';
      actionsEl.innerHTML = '<button class="btn btn-primary btn-sm" onclick="navigateTo(\'config\');return false;">更新 Cookie</button>';
      if (!status.dismissed_at) banner.style.display = 'flex';
    } else if (status.valid === null && !status.last_checked) {
      if ((location.hash || '').replace('#', '') === 'batch') {
        textEl.textContent = 'Cookie 尚未验证，建议先检测是否有效。';
        actionsEl.innerHTML = '<button class="btn btn-secondary btn-sm" onclick="navigateTo(\'config\');return false;">去检测</button>';
        banner.style.background = '#fef3c7';
        banner.style.borderColor = '#f59e0b';
        if (!status.dismissed_at) banner.style.display = 'flex';
      }
    } else {
      banner.style.display = 'none';
    }
  }).catch(function() {});
}

function dismissCookieWarn() {
  document.getElementById('cookie-warn-banner').style.display = 'none';
  API.post('/cookie/dismiss').catch(function() {});
}

// 批量下载完成后跳转到指定项目分析页
function gotoAnalysis(projectId) {
  var sel = document.getElementById('project-select');
  if (sel) sel.value = projectId;
  navigateTo('analysis');
}

document.addEventListener('DOMContentLoaded', async () => {
  // URL hash 路由：恢复上次页面
  const hash = (location.hash || '').replace('#', '');
  const validPages = ['analysis', 'batch', 'settings', 'config'];
  if (hash && validPages.includes(hash)) {
    navigateTo(hash);
  }

  await populateProjectSelects();

  // 启动定时下载通知轮询（每 60 秒）
  pollScheduleResult();
  setInterval(pollScheduleResult, 60000);

  // 检查 cookie 状态（在下载页时提示）
  checkCookieWarn();

  // 只在数据分析页（或无 hash）时尝试恢复上次项目
  const currentHash = (location.hash || '').replace('#', '');
  if (!currentHash || currentHash === 'analysis') {
    try {
      const state = await API.get('/analyze/last-state');
      if (state && state.last_project_id) {
        // 有历史记录 — 静默恢复，不显示欢迎页
        document.getElementById('project-select').value = state.last_project_id;
        await loadAnalysisData(state.last_project_id);
      } else {
        // 首次访问，无历史记录 — 显示欢迎页
        document.getElementById('analysis-welcome').style.display = 'flex';
        document.getElementById('analysis-empty').style.display = 'none';
        document.getElementById('analysis-loaded').style.display = 'none';
      }
    } catch (e) {
      // 后端未就绪 — 显示欢迎页
      document.getElementById('analysis-welcome').style.display = 'flex';
      document.getElementById('analysis-empty').style.display = 'none';
      document.getElementById('analysis-loaded').style.display = 'none';
    }
  }
});
