/** 导入页逻辑 */

let importEventSource = null;

// 页面初始化时检查 cookie 状态
async function checkImportPrerequisites() {
  try {
    const cookieCheck = await API.cookie.get();
    const hintEl = document.getElementById('import-cookie-hint');
    const startBtn = document.getElementById('btn-start-import');
    if (!cookieCheck.has_cookie) {
      hintEl.style.display = 'flex';
      startBtn.style.opacity = '0.5';
      startBtn.style.pointerEvents = 'none';
    } else {
      hintEl.style.display = 'none';
      startBtn.style.opacity = '1';
      startBtn.style.pointerEvents = 'auto';
    }
  } catch (e) {
    console.error('Cookie检查失败:', e);
  }
}

document.getElementById('btn-start-import').addEventListener('click', () => {
  const pid = getSelectedProjectId('#import-project');
  if (!pid) { alert('请先选择项目'); return; }
  startImport(pid);
});

document.getElementById('btn-cancel-import').addEventListener('click', () => {
  cancelImport();
});

async function startImport(projectId) {
  const progressEl = document.getElementById('import-progress');
  const logEl = document.getElementById('import-log');
  const completeEl = document.getElementById('import-complete');
  const hintEl = document.getElementById('import-duplicate-hint');
  const startBtn = document.getElementById('btn-start-import');

  // 重置状态
  progressEl.style.display = '';
  completeEl.style.display = 'none';
  hintEl.style.display = 'none';
  logEl.innerHTML = '';
  document.getElementById('import-progress-bar').style.width = '0%';
  document.getElementById('import-progress-text').textContent = '正在连接...';
  startBtn.disabled = true;

  // 检查 cookie
  try {
    const cookieCheck = await API.cookie.get();
    if (!cookieCheck.has_cookie) {
      logEl.innerHTML = '<span style="color:var(--red);">Cookie 未配置</span> '
        + '<a href="#" style="color:var(--link-cobalt);font-size:12px;" onclick="document.querySelector(\'[data-page=settings]\').click();return false;">前往项目管理页面设置</a>';
      document.getElementById('import-progress-text').textContent = '缺少认证信息';
      startBtn.disabled = false;
      return;
    }
  } catch (e) {
    logEl.innerHTML = '<span style="color:var(--red);">无法连接到后端服务</span>';
    startBtn.disabled = false;
    return;
  }

  addLog('[' + new Date().toLocaleTimeString() + '] Cookie 已配置，开始导入');

  // 检查今日是否已下载
  try {
    const analyze = await API.analyze.load(projectId);
    if (analyze.stale === false && analyze.file_date) {
      hintEl.style.display = 'flex';
    }
  } catch (e) { /* ignore */ }

  // 连接 SSE
  const url = '/api/import/' + projectId + '/stream';
  importEventSource = new EventSource(url);

  importEventSource.addEventListener('progress', (e) => {
    const d = JSON.parse(e.data);
    document.getElementById('import-progress-text').textContent = d.message;
    document.getElementById('import-progress-bar').style.width = d.percent + '%';
    addLog('[' + new Date().toLocaleTimeString() + '] ' + d.message);
  });

  importEventSource.addEventListener('complete', (e) => {
    const d = JSON.parse(e.data);
    document.getElementById('import-progress-bar').style.width = '100%';
    document.getElementById('import-progress-text').textContent = '下载完成';
    addLog('[' + new Date().toLocaleTimeString() + '] 文件: ' + d.filename + ' (' + d.size_mb + ' MB)');
    addLog('[' + new Date().toLocaleTimeString() + '] 导入完成!');
    progressEl.querySelector('.spinner').style.display = 'none';
    document.getElementById('btn-cancel-import').style.display = 'none';
    completeEl.style.display = '';
    startBtn.disabled = false;
    importEventSource.close();
    importEventSource = null;
  });

  importEventSource.addEventListener('error', (e) => {
    let msg = '服务器返回错误';
    try { const d = JSON.parse(e.data); msg = d.message || msg; } catch (_) {}
    addLog('<span style="color:var(--red);">[' + new Date().toLocaleTimeString() + '] ' + msg + '</span>');
    stopImportUI('导入失败: ' + msg);
    if (importEventSource) { importEventSource.close(); importEventSource = null; }
  });

  importEventSource.onerror = () => {
    if (importEventSource && importEventSource.readyState === EventSource.CLOSED) {
      stopImportUI('连接已断开');
    }
  };
}

function stopImportUI(message) {
  const progressEl = document.getElementById('import-progress');
  const startBtn = document.getElementById('btn-start-import');
  const spinner = progressEl.querySelector('.spinner');
  if (spinner) spinner.style.display = 'none';
  document.getElementById('btn-cancel-import').style.display = 'none';
  document.getElementById('import-progress-text').textContent = message;
  startBtn.disabled = false;
  alert(message);
}

function cancelImport() {
  if (importEventSource) {
    importEventSource.close();
    importEventSource = null;
  }
  document.getElementById('import-progress').style.display = 'none';
  document.getElementById('btn-start-import').disabled = false;
  document.getElementById('btn-cancel-import').style.display = 'none';
  addLog('[' + new Date().toLocaleTimeString() + '] 已取消');
}

function addLog(msg) {
  const logEl = document.getElementById('import-log');
  logEl.innerHTML += '<div>' + msg + '</div>';
  logEl.scrollTop = logEl.scrollHeight;
}
