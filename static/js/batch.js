/** 批量下载页逻辑 */

let batchEventSource = null;
let batchStartTime = 0;
let batchCurrentProgress = 0;

document.getElementById('btn-start-batch').addEventListener('click', async () => {
  const checked = document.querySelectorAll('.batch-check:checked');
  if (!checked.length) { alert('请选择要下载的项目'); return; }
  const ids = Array.from(checked).map(cb => cb.dataset.id).join(',');
  await startBatchDownload(ids);
});

document.getElementById('btn-cancel-batch').addEventListener('click', () => {
  cancelBatch();
});

// ========== 页面初始化 ==========
function loadBatchPage() {
  renderBatchList().catch(function(e) {
    console.error('批量页加载失败:', e);
    document.getElementById('batch-empty').style.display = 'flex';
    document.getElementById('batch-empty').querySelector('.title').textContent = '加载失败';
    document.getElementById('batch-empty').querySelector('.desc').textContent = '请检查后端服务是否正常运行';
  });
}

async function startBatchDownload(ids) {
  const startBtn = document.getElementById('btn-start-batch');
  const cancelBtn = document.getElementById('btn-cancel-batch');
  const progressEl = document.getElementById('batch-progress');

  startBtn.style.display = 'none';
  cancelBtn.style.display = 'inline-flex';
  progressEl.style.display = '';
  batchStartTime = Date.now();

  const idList = ids.split(',');
  const total = idList.length;

  document.querySelectorAll('.batch-status').forEach(s => { s.textContent = '等待中'; s.style.color = 'var(--silver)'; });
  document.getElementById('batch-progress-bar').style.width = '0%';
  document.getElementById('batch-progress-text').textContent = '0/' + total;
  document.getElementById('batch-eta').textContent = '--';

  batchEventSource = new EventSource('/api/batch/stream?ids=' + encodeURIComponent(ids));

  batchEventSource.addEventListener('progress', (e) => {
    const d = JSON.parse(e.data);
    batchCurrentProgress = d.percent || 0;
    updateProjectStatus(d.project, '下载中 ' + batchCurrentProgress + '%', 'var(--link-cobalt)');
    const overall = d.overall || { done: 0, total: total };
    // 将当前项目的内部进度折算进总体进度
    var effectiveDone = overall.done + batchCurrentProgress / 100;
    updateBatchProgress(effectiveDone, overall.total);
  });

  batchEventSource.addEventListener('complete', (e) => {
    const d = JSON.parse(e.data);
    updateProjectStatus(d.project, '完成', 'var(--green)');
  });

  batchEventSource.addEventListener('error', (e) => {
    let msg = '下载失败';
    try { const d = JSON.parse(e.data); msg = d.message || msg; } catch (_) {}
    stopBatchUI(msg);
    if (batchEventSource) { batchEventSource.close(); batchEventSource = null; }
  });

  batchEventSource.addEventListener('project_done', (e) => {
    const d = JSON.parse(e.data);
    if (d.status === 'error') {
      updateProjectStatus(d.project, (d.message || '失败'), 'var(--red)');
    }
  });

  batchEventSource.addEventListener('batch_complete', (e) => {
    const d = JSON.parse(e.data);
    updateBatchProgress(d.total, d.total);

    const results = d.results || [];
    const okCount = results.filter(function(r) { return r.status === 'ok'; }).length;
    const errCount = results.filter(function(r) { return r.status === 'error'; }).length;
    if (errCount > 0 && okCount > 0) {
      document.getElementById('batch-eta').textContent = okCount + ' 成功 / ' + errCount + ' 失败';
    } else if (errCount > 0) {
      document.getElementById('batch-eta').textContent = '全部失败';
      document.getElementById('batch-eta').style.color = 'var(--red)';
      alert('批量下载全部失败，请检查 Cookie 是否有效');
    } else {
      document.getElementById('batch-eta').textContent = '全部完成!';
    }

    results.forEach(function(r) {
      if (r.status === 'ok') {
        updateProjectStatus(r.project, '完成', 'var(--green)');
      } else {
        updateProjectStatus(r.project, (r.message || '失败'), 'var(--red)');
      }
    });

    startBtn.style.display = 'inline-flex';
    cancelBtn.style.display = 'none';
    batchEventSource.close();
    batchEventSource = null;
  });

  batchEventSource.onerror = () => {
    if (batchEventSource && batchEventSource.readyState === EventSource.CLOSED) {
      stopBatchUI('连接已断开');
    }
  };
}

function stopBatchUI(message) {
  document.getElementById('batch-progress').style.display = 'none';
  document.getElementById('btn-start-batch').style.display = 'inline-flex';
  document.getElementById('btn-cancel-batch').style.display = 'none';
  document.getElementById('batch-eta').textContent = message;
  document.getElementById('batch-eta').style.color = 'var(--red)';
  alert(message);
}

function updateProjectStatus(projectId, text, color) {
  const cb = document.querySelector('.batch-check[data-id="' + projectId + '"]');
  if (!cb) return;
  const status = cb.closest('.project-card').querySelector('.batch-status');
  if (status) {
    status.textContent = text;
    status.style.color = color;
  }
}

function updateBatchProgress(done, total) {
  const pct = total > 0 ? Math.round(done / total * 100) : 0;
  document.getElementById('batch-progress-bar').style.width = pct + '%';
  document.getElementById('batch-progress-text').textContent = Math.floor(done) + '/' + total;

  if (done > 0 && done < total) {
    const elapsed = (Date.now() - batchStartTime) / 1000;
    const rate = done / elapsed;
    const remaining = (total - done) / rate;
    if (remaining < 60) {
      document.getElementById('batch-eta').textContent = '约 ' + Math.round(remaining) + ' 秒';
    } else {
      document.getElementById('batch-eta').textContent = '约 ' + Math.round(remaining / 60) + ' 分钟';
    }
  } else if (done <= 0) {
    document.getElementById('batch-eta').textContent = '正在连接...';
  }
}

function cancelBatch() {
  if (batchEventSource) {
    batchEventSource.close();
    batchEventSource = null;
  }
  document.getElementById('batch-progress').style.display = 'none';
  document.getElementById('btn-start-batch').style.display = 'inline-flex';
  document.getElementById('btn-cancel-batch').style.display = 'none';
  document.querySelectorAll('.batch-status').forEach(s => { s.textContent = '等待中'; s.style.color = 'var(--silver)'; });
}
