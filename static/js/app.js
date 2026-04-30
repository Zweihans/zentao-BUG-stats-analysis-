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
// 按项目持久化"已提醒过"的未关注人员（sessionStorage：刷新不丢失，关浏览器自动清）
function _unfocusedSeenKey(projectId) { return 'unfocused_seen_' + projectId; }
function _getUnfocusedSeen(projectId) {
  try { return JSON.parse(sessionStorage.getItem(_unfocusedSeenKey(projectId)) || '[]'); } catch (e) { return []; }
}
function _setUnfocusedSeen(projectId, names) {
  try { sessionStorage.setItem(_unfocusedSeenKey(projectId), JSON.stringify(names)); } catch (e) {}
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

document.getElementById('person-search').addEventListener('input', function() {
  filterPersonList(this.value.toLowerCase());
});

function filterPersonList(query) {
  document.querySelectorAll('#person-list .person-row').forEach(row => {
    const name = row.dataset.name || '';
    row.style.display = name.includes(query) ? '' : 'none';
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
  document.getElementById('analysis-welcome').style.display = 'none';
  document.getElementById('analysis-empty').style.display = 'none';
  const container = document.getElementById('analysis-loaded');
  container.style.display = 'flex';

  try {
    const data = await API.analyze.load(projectId);
    _currentPersons = data.persons || [];
    renderPersonList(_currentPersons);

    // 已关注人员激活 BUG 总数
    var focusActive = 0;
    _currentPersons.forEach(function(p) {
      if (p.focus) focusActive += (p.active || 0);
    });
    var summaryEl = document.getElementById('focus-active-summary');
    if (summaryEl) summaryEl.textContent = '已关注人员 · 激活 BUG: ' + focusActive;

    // 未关注人员提示 — 每个项目只提醒一次，新导入后有新增人员才提醒
    var unfocused = data.unfocused_persons || [];
    var seen = _getUnfocusedSeen(projectId);
    var newUnfocused = unfocused.filter(function(name) {
      return seen.indexOf(name) === -1;
    });
    _setUnfocusedSeen(projectId, unfocused);
    var alertEl = document.getElementById('unfocused-alert');
    if (newUnfocused.length > 0) {
      document.getElementById('unfocused-names').textContent = newUnfocused.join('、');
      _quickAddNames = newUnfocused;
      alertEl.style.display = 'flex';
    } else {
      alertEl.style.display = 'none';
    }

    if (data.persons && data.persons.length > 0) {
      selectPerson(data.persons[0].name, data.persons[0].bugs || []);
    }
    const statusEl = document.getElementById('data-status');
    var fileDate = data.file_date || '--';
    if (data.stale) {
      statusEl.innerHTML = '<span class="status-dot amber"></span> 数据更新于 ' + fileDate + ' · <a href="#" style="color:var(--link-cobalt); font-weight:600; text-decoration:none;" id="status-refresh-link">点击刷新</a> <span id="refresh-progress" style="font-size:11px; color:var(--silver);"></span>';
    } else {
      statusEl.innerHTML = '<span class="status-dot green"></span> ' + fileDate + ' · <a href="#" style="color:var(--link-cobalt); font-weight:600; text-decoration:none;" id="status-refresh-link">点击刷新</a> <span id="refresh-progress" style="font-size:11px; color:var(--silver);"></span>';
    }
    statusEl.style.cursor = 'default';
    statusEl.onclick = null;
    document.getElementById('status-refresh-link').addEventListener('click', function(e) {
      e.preventDefault();
      refreshCurrentProject();
    });
  } catch (e) {
    document.getElementById('analysis-empty').style.display = 'flex';
    container.style.display = 'none';
    document.getElementById('unfocused-alert').style.display = 'none';
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
      selectPerson(this.dataset.name, JSON.parse(this.dataset.bugs || '[]'));
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
  const tbody = document.getElementById('bug-tbody');
  if (!bugs.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--silver); padding:32px; font-size:13px;">该人员暂无 BUG</td></tr>';
    return;
  }
  tbody.innerHTML = bugs.map(b => {
    const isNew = b.is_new ? ' class="new"' : '';
    const newMark = b.is_new ? ' <span class="badge badge-new" style="font-size:10px;">新增</span>' : '';
    return '<tr' + isNew + ' data-severity="' + (b.severity || '') + '" data-status="' + (b.status || '') + '">' +
      '<td><a class="bug-id-link" href="https://zd.bicv.com/bug-view-' + b.id + '.html" target="_blank">#' + b.id + '</a></td>' +
      '<td>' + escHtml(b.title || '') + newMark + '</td>' +
      '<td><span class="badge" style="' + severityBadge(b.severity) + '">' + (b.severity || '-') + '</span></td>' +
      '<td>' + escHtml(b.status || '') + '</td>' +
      '</tr>';
  }).join('');
  filterBugTable();
}

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
function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

// ========== 关注人员管理模态窗口 ==========
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
  list.innerHTML = _focusModalPersons.map(function(p) {
    var hidden = query && p.name.toLowerCase().indexOf(query) === -1;
    return '<label style="display:' + (hidden ? 'none' : 'flex') + '; align-items:center; gap:8px; padding:8px 0; cursor:pointer; font-size:13px; border-bottom:1px solid var(--border-lavender);">' +
      '<input type="checkbox" data-name="' + escHtml(p.name) + '" ' + (p.checked ? 'checked' : '') + ' style="accent-color:var(--near-black);">' +
      '<span>' + escHtml(p.name) + '</span>' +
      '</label>';
  }).join('');
}

function closeFocusModal() {
  document.getElementById('focus-modal').style.display = 'none';
  document.getElementById('focus-modal-title').textContent = '管理关注人员';
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

// 柱状图
document.getElementById('btn-chart-bar').addEventListener('click', function() {
  var pid = getSelectedProjectId('#project-select');
  if (!pid) { alert('请先选择项目'); return; }
  document.getElementById('chart-bar-modal').style.display = 'flex';
  document.getElementById('chart-bar-filter').value = 'all';
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
  var canvas = document.getElementById('chart-bar-canvas');
  var container = canvas.parentElement;
  canvas.height = Math.max(300, data.labels.length * 28);
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
  document.getElementById('chart-pie-filter').value = 'all';
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
  var filter = document.getElementById('chart-pie-filter').value;
  var persons = _currentPersons;
  if (filter === 'focus') persons = persons.filter(function(p) { return p.focus; });
  persons = persons.filter(function(p) { return p.total > 0; });
  persons.sort(function(a, b) { return b.total - a.total; });

  var ctx = document.getElementById('chart-pie-canvas').getContext('2d');
  if (_pieChart) _pieChart.destroy();

  var bgColors = [
    '#1c2024', '#363a3f', '#555860', '#777a82', '#999da4', '#b0b4ba',
    '#c4c7cc', '#d3d5d9', '#e0e1e6', '#40444a', '#6a6e75', '#898d94',
  ];

  _pieChart = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: persons.map(function(p) { return p.name; }),
      datasets: [{
        data: persons.map(function(p) { return p.total; }),
        backgroundColor: bgColors.slice(0, persons.length),
        borderColor: '#fff',
        borderWidth: 1.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { font: { size: 10 }, padding: 12, color: '#60646c', usePointStyle: true },
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              var p = persons[ctx.dataIndex];
              var parts = ['S', 'A', 'B', 'C'].map(function(s) { return p[s] > 0 ? s + ':' + p[s] : null; }).filter(Boolean);
              return p.name + ' 共 ' + p.total + ' Bug  (' + parts.join(' ') + ')';
            },
          },
        },
      },
    },
  });

  // 下方文字列表
  document.getElementById('chart-pie-labels').innerHTML = persons.map(function(p) {
    var parts = ['S', 'A', 'B', 'C'].map(function(s) { return p[s] > 0 ? s + ':' + p[s] : null; }).filter(Boolean);
    return '<div style="padding:2px 0;">' + escHtml(p.name + '  ' + p.total + ' Bug  (' + parts.join(' ') + ')') + '</div>';
  }).join('');
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
  if (filter === 'focus' && typeof _currentPersons !== 'undefined') {
    _currentPersons.forEach(function(p) {
      if (p.focus) focusNames.add(p.name);
    });
  }

  var checkedMap = {};
  var container = document.getElementById('trend-person-checkboxes');
  container.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
    checkedMap[cb.value] = cb.checked;
  });

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
  container.innerHTML = html;
}

function renderTrendChart() {
  if (_trendChart) { _trendChart.destroy(); _trendChart = null; }
  if (!_trendData || !_trendData.records || _trendData.records.length === 0) return;

  var dataType = document.querySelector('.trend-data-tag.active')?.dataset.trendData || 'total';

  var checkedNames = [];
  document.querySelectorAll('#trend-person-checkboxes input[type="checkbox"]:checked').forEach(function(cb) {
    checkedNames.push(cb.value);
  });

  // 更新勾选人员 BUG 总量（取最新一条记录的数据）
  var latestRecord = _trendData.records[_trendData.records.length - 1];
  var checkedTotal = 0;
  (latestRecord.persons || []).forEach(function(p) {
    if (checkedNames.indexOf(p.name) !== -1) checkedTotal += (p[dataType] || 0);
  });
  var totalEl = document.getElementById('trend-checked-total');
  if (totalEl) totalEl.textContent = checkedNames.length ? checkedTotal + ' BUG' : '';

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
    // 合计视图：一条聚合折线
    var sumData = _trendData.records.map(function(rec) {
      var total = 0;
      (rec.persons || []).forEach(function(p) {
        if (checkedNames.indexOf(p.name) !== -1) total += (p[dataType] || 0);
      });
      return total;
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
    // 单人视图：每人一条折线
    datasets = checkedNames.map(function(name, idx) {
      var data = _trendData.records.map(function(rec) {
        var person = (rec.persons || []).find(function(p) { return p.name === name; });
        if (!person) return null;
        return person[dataType] || 0;
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
        tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y + ' BUG'; } } }
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, ticks: { stepSize: 1 } }
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

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', async () => {
  // URL hash 路由：恢复上次页面
  const hash = (location.hash || '').replace('#', '');
  const validPages = ['analysis', 'batch', 'settings', 'config'];
  if (hash && validPages.includes(hash)) {
    navigateTo(hash);
  }

  await populateProjectSelects();

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
