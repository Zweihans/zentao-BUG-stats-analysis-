/** API 请求封装 */
const API = {
  base: '/api',

  async request(method, path, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(this.base + path, opts);
    return res.json();
  },

  get(path)    { return this.request('GET', path); },
  post(path, b) { return this.request('POST', path, b); },
  put(path, b)  { return this.request('PUT', path, b); },
  del(path)     { return this.request('DELETE', path); },

  // 项目
  projects: {
    list()    { return API.get('/projects'); },
    add(p)    { return API.post('/projects', p); },
    update(i,p) { return API.put('/projects/' + i, p); },
    remove(i) { return API.del('/projects/' + i); },
  },

  // 导入
  import: {
    start(projectId) { return API.post('/import/' + projectId); },
    stream(projectId, onProgress, onComplete, onError) {
      const url = '/api/import/' + projectId + '/stream';
      const es = new EventSource(url);
      es.addEventListener('progress', e => onProgress(JSON.parse(e.data)));
      es.addEventListener('complete', e => { es.close(); onComplete(JSON.parse(e.data)); });
      es.addEventListener('error', e => { es.close(); if (onError) onError(e); });
      return es; // caller can .close() to cancel
    },
  },

  // 分析
  analyze: {
    load(projectId)       { return API.get('/analyze/' + projectId); },
    loadFile(projectId, filePath) { return API.post('/analyze', { project_id: projectId, file_path: filePath }); },
    compare(projectId)    { return API.post('/compare', { project_id: projectId }); },
  },

  // 关注人员
  focus: {
    get(projectId)         { return API.get('/focus/' + (projectId || 'default')); },
    update(projectId, list) { return API.put('/focus/' + (projectId || 'default'), { persons: list }); },
  },

  // 其他
  cookie: {
    get()     { return API.get('/cookie'); },
    update(c) { return API.put('/cookie', { cookie: c }); },
    verify(c) { return API.post('/cookie/verify', { cookie: c || '' }); },
  },
  export: {
    csv(projectId) { window.location.href = '/api/export/' + projectId; },
  },
  cleanup() { return API.post('/cleanup'); },
};
