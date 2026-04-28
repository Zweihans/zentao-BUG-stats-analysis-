/** 禅道BUG分析工具 - 应用逻辑 */

// ========== 路由 ==========
function navigateTo(pageName) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + pageName).classList.add('active');

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.querySelector('[data-page="' + pageName + '"]');
  if (nav) nav.classList.add('active');

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
var _previousUnfocused = [];

document.getElementById('project-select').addEventListener('change', async function() {
  const pid = this.value;
  if (!pid) {
    document.getElementById('analysis-empty').style.display = 'flex';
    document.getElementById('analysis-loaded').style.display = 'none';
    document.getElementById('unfocused-alert').style.display = 'none';
    _previousUnfocused = [];
    return;
  }
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
  document.getElementById('analysis-empty').style.display = 'none';
  const container = document.getElementById('analysis-loaded');
  container.style.display = 'flex';

  try {
    const data = await API.analyze.load(projectId);
    _currentPersons = data.persons || [];
    renderPersonList(_currentPersons);

    // 未关注人员提示 — 只提醒新增的
    var unfocused = data.unfocused_persons || [];
    var newUnfocused = unfocused.filter(function(name) {
      return _previousUnfocused.indexOf(name) === -1;
    });
    _previousUnfocused = unfocused;
    var alertEl = document.getElementById('unfocused-alert');
    if (newUnfocused.length > 0) {
      document.getElementById('unfocused-names').textContent = newUnfocused.join('、');
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
    await API.focus.update(projectId, selected);
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

function renderFocusModalList(query) {
  var list = document.getElementById('focus-modal-list');
  // 始终渲染全部人员，搜索时仅隐藏不匹配的行，避免丢失勾选状态
  if (!_focusModalPersons.length) {
    list.innerHTML = '<div style="padding:16px; text-align:center; color:var(--silver); font-size:13px;">暂无数据</div>';
    return;
  }
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
  _focusModalProjectId = null;
  _focusModalPersons = [];
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

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', async () => {
  await populateProjectSelects();
  // 打开即看：自动加载上次项目
  try {
    const state = await API.get('/analyze/last-state');
    if (state && state.last_project_id) {
      document.getElementById('project-select').value = state.last_project_id;
      await loadAnalysisData(state.last_project_id);
    }
  } catch (e) {
    console.log('加载上次状态失败');
  }
});
