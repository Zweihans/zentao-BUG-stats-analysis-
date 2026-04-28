/** 项目管理页逻辑 */

let selectedProjectId = null;

// ========== 项目列表 ==========
async function loadSettingsPage() {
  try {
    const data = await API.projects.list();
    const projects = data.projects || [];
    renderSettingsProjectList(projects);
    if (projects.length && !selectedProjectId) {
      selectSettingsProject(projects[0]);
    }
  } catch (e) {
    console.error(e);
  }
}

function renderSettingsProjectList(projects) {
  const list = document.getElementById('settings-project-list');
  list.innerHTML = projects.map(p => {
    const isSel = p.id === selectedProjectId;
    return '<div class="settings-project-item" data-id="' + p.id + '" style="' +
      'padding:10px 0; border-bottom:1px solid var(--border-lavender); display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;' +
      (isSel ? 'background:var(--cloud-gray); margin:0 -20px; padding-left:20px; padding-right:20px;' : '') + '">' +
      '<span style="flex:1; font-weight:500;">' + escHtml(p.name) + '</span>' +
      '<span style="font-size:11px; color:' + (p.focus ? 'var(--near-black)' : 'var(--silver)') + '; font-weight:' + (p.focus ? '600' : '400') + ';">' + (p.focus ? '关注' : '普通') + '</span>' +
      '</div>';
  }).join('');

  list.querySelectorAll('.settings-project-item').forEach(item => {
    item.addEventListener('click', async () => {
      const pid = item.dataset.id;
      const proj = projects.find(p => p.id === pid);
      if (proj) {
        selectSettingsProject(proj);
        const data = await API.projects.list();
        renderSettingsProjectList(data.projects || []);
      }
    });
  });
}

function selectSettingsProject(project) {
  selectedProjectId = project.id;
  showProjectEditor(project);
}

// ========== 项目编辑器 ==========
function showProjectEditor(project) {
  const editor = document.getElementById('settings-editor');
  editor.innerHTML =
    '<div style="display:flex; flex-direction:column; gap:16px;">' +
    '<h3 style="font-size:14px; font-weight:600; letter-spacing:-0.3px;">编辑项目</h3>' +
    '<label style="font-size:12px; color:var(--slate);">项目名称</label>' +
    '<input type="text" id="edit-name" value="' + escHtml(project.name) + '" style="width:100%;">' +
    '<label style="font-size:12px; color:var(--slate);">禅道 URL</label>' +
    '<input type="text" id="edit-url" value="' + escHtml(project.url || '') + '" style="width:100%;">' +
    '<label style="display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer;">' +
    '<input type="checkbox" id="edit-focus" ' + (project.focus ? 'checked' : '') + ' style="accent-color:var(--near-black);"> 设为关注项目</label>' +
    '<div style="display:flex; gap:8px; margin-top:8px;">' +
    '<button class="btn btn-primary btn-sm" id="btn-save-project">保存</button>' +
    '<button class="btn btn-secondary btn-sm" id="btn-delete-project">删除项目</button>' +
    '</div></div>';

  document.getElementById('btn-save-project').addEventListener('click', () => saveProject(project.id));
  document.getElementById('btn-delete-project').addEventListener('click', () => deleteProject(project.id));
}

async function saveProject(id) {
  const name = document.getElementById('edit-name').value.trim();
  const url = document.getElementById('edit-url').value.trim();
  const focus = document.getElementById('edit-focus').checked;
  if (!name) { alert('项目名称不能为空'); return; }
  try {
    await API.projects.update(id, { name, url, focus });
    await populateProjectSelects();
    const data = await API.projects.list();
    const updated = (data.projects || []).find(p => p.id === id);
    if (updated) {
      selectedProjectId = id;
      renderSettingsProjectList(data.projects || []);
      showProjectEditor(updated);
    }
  } catch (e) {
    alert('保存失败');
    console.error(e);
  }
}

async function deleteProject(id) {
  if (!confirm('确定删除此项目？')) return;
  try {
    await API.projects.remove(id);
    selectedProjectId = null;
    document.getElementById('settings-editor').innerHTML = '<div class="empty-state"><div class="title">选择一个项目</div><div class="desc">从左侧列表选择项目进行编辑</div></div>';
    await populateProjectSelects();
    const data = await API.projects.list();
    renderSettingsProjectList(data.projects || []);
  } catch (e) {
    alert('删除失败');
    console.error(e);
  }
}

// ========== 添加项目 ==========
document.getElementById('btn-add-project').addEventListener('click', () => {
  selectedProjectId = null;
  renderSettingsProjectList([]);
  const editor = document.getElementById('settings-editor');
  editor.innerHTML =
    '<div style="display:flex; flex-direction:column; gap:16px;">' +
    '<h3 style="font-size:14px; font-weight:600; letter-spacing:-0.3px;">添加项目</h3>' +
    '<label style="font-size:12px; color:var(--slate);">项目名称</label>' +
    '<input type="text" id="edit-name" placeholder="例如: C62X-E19" style="width:100%;">' +
    '<label style="font-size:12px; color:var(--slate);">禅道 URL</label>' +
    '<input type="text" id="edit-url" placeholder="https://zd.bicv.com/bug-browse-..." style="width:100%;">' +
    '<label style="display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer;">' +
    '<input type="checkbox" id="edit-focus" style="accent-color:var(--near-black);"> 设为关注项目</label>' +
    '<div style="display:flex; gap:8px; margin-top:8px;">' +
    '<button class="btn btn-primary btn-sm" id="btn-add-confirm">添加</button>' +
    '<button class="btn btn-secondary btn-sm" id="btn-add-cancel">取消</button>' +
    '</div></div>';

  document.getElementById('btn-add-confirm').addEventListener('click', addNewProject);
  document.getElementById('btn-add-cancel').addEventListener('click', () => {
    editor.innerHTML = '<div class="empty-state"><div class="title">选择一个项目</div><div class="desc">从左侧列表选择项目进行编辑</div></div>';
    loadSettingsPage();
  });
});

async function addNewProject() {
  const name = document.getElementById('edit-name').value.trim();
  const url = document.getElementById('edit-url').value.trim();
  const focus = document.getElementById('edit-focus').checked;
  if (!name) { alert('项目名称不能为空'); return; }
  try {
    const result = await API.projects.add({ name, url, focus });
    await populateProjectSelects();
    await loadSettingsPage();
    if (result.project) {
      selectSettingsProject(result.project);
    }
  } catch (e) {
    alert('添加失败');
    console.error(e);
  }
}
