'use strict';
const $ = id => document.getElementById(id);
let token = '', state = null, connected = false, posting = false, stopped = false;
let latestJob = null, timer = null, refreshing = false, announcedJob = '';
const labels = {start:'启动服务', stop:'停止服务', load:'加载模型', unload:'释放内存', chat:'测试模型'};
const bytes = value => (Number(value || 0) / 1024 ** 3).toFixed(1) + ' GiB';
function notice(message, error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); }
async function api(path, payload) {
  const response = await fetch(path, {cache:'no-store', signal:AbortSignal.timeout(15000),
    ...(payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Atlas-Token':token}, body:JSON.stringify(payload)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败，请刷新后重试。');
  return result;
}
function busy() { return posting || !!state?.active_job || latestJob?.state === 'running'; }
function controls() {
  const locked = !connected || busy() || stopped;
  const online = !!state?.online;
  const model = $('model').value;
  $('start').disabled = locked || online || !state?.can_start;
  $('stop').disabled = locked || !online || !state?.managed;
  $('model').disabled = locked || !online || !state?.models?.length;
  $('context').disabled = locked;
  $('load').disabled = locked || !online || !model;
  const selected = state?.models?.find(m => m.name === model);
  $('unload').disabled = locked || !online || !state?.loaded?.some(m => m.name === model || (selected?.digest && m.digest === selected.digest));
  $('send').disabled = locked || !online || !model || !$('prompt').value.trim();
  $('prompt').disabled = locked;
  $('example').disabled = locked;
  $('exit').disabled = !connected || busy() || stopped;
  $('copy').disabled = !model;
}
function selectedModel() {
  const model = state?.models?.find(m => m.name === $('model').value);
  $('model-meta').textContent = model ? [bytes(model.size), model.details?.parameter_size, model.details?.quantization_level].filter(Boolean).join(' · ') : '服务在线后才能读取本机模型。';
  // Quote names for PowerShell; never interpolate these into an executable command on the server.
  const name = $('model').value || 'qwen3.5-coding:4b';
  $('command').textContent = "claude --model '" + name.replaceAll("'", "''") + "'";
  controls();
}
function renderStatus(data) {
  state = data; connected = true;
  $('connection').textContent = '● 控制台已连接';
  $('service-state').textContent = data.online ? '在线' : '未启动';
  $('service-detail').textContent = data.online ? 'Ollama ' + data.version : '点击下方启动服务';
  $('service-help').textContent = !data.can_start ? '未找到 Ollama，请先安装或在启动脚本中指定路径。' : !data.online ? '启动服务后，模型列表会自动出现。' : data.managed ? '服务由本控制台启动，可以在此停止。停止会结束此服务的所有请求。' : '服务由其他程序启动。可以加载和测试模型；完全停止请从 Ollama 托盘菜单退出。';
  const loaded = data.loaded || [];
  const memory = loaded.reduce((sum, m) => sum + (m.size || 0), 0);
  const vram = loaded.reduce((sum, m) => sum + (m.size_vram || 0), 0);
  const partial = data.online && data.error;
  $('memory-state').textContent = partial ? '读取失败' : bytes(memory);
  $('memory-detail').textContent = partial ? '请稍后刷新' : `${loaded.length} 个模型已加载 · 含显存分配`;
  $('vram-state').textContent = partial ? '—' : bytes(vram);
  $('vram-detail').textContent = partial ? '状态暂不可用' : !loaded.length ? '模型尚未加载' : vram === 0 ? '当前模型使用 CPU / 系统内存' : '来自 Ollama 的模型显存分配';
  const previous = $('model').value;
  const names = data.models.map(m => m.name);
  const currentNames = [...$('model').options].map(m => m.value);
  if (JSON.stringify(names) !== JSON.stringify(currentNames)) {
    $('model').replaceChildren();
    for (const name of names) $('model').add(new Option(name, name));
    if (!names.length) $('model').add(new Option(data.online ? '没有已安装模型' : '启动服务后读取模型', ''));
    $('model').value = names.includes(previous) ? previous : names.includes('qwen3.5-coding:4b') ? 'qwen3.5-coding:4b' : names[0] || '';
  }
  $('loaded').replaceChildren();
  if (!loaded.length) { const p = document.createElement('p'); p.textContent = partial ? '模型状态读取失败，请刷新。' : data.online ? '当前没有模型驻留内存。' : '服务未启动。'; $('loaded').append(p); }
  for (const item of loaded) {
    const row = document.createElement('div'); row.className = 'loaded-item';
    const name = document.createElement('strong'); name.textContent = item.name;
    const description = document.createElement('span');
    description.textContent = `${bytes(item.size)} · 显存 ${bytes(item.size_vram)} · 上下文 ${item.context_length || '未知'}`;
    row.append(name, description); $('loaded').append(row);
  }
  $('gpu-detail').textContent = data.gpu.length ? data.gpu.map(g => `${g.name}：显存 ${g.used_mb} / ${g.total_mb} MiB，GPU 利用率 ${g.utilization}%`).join('；') : '未检测到 NVIDIA 显卡监测接口。模型显存分配仍以 Ollama 返回值为准。';
  $('updated').textContent = '状态更新于 ' + new Date().toLocaleTimeString('zh-CN') + ' · 每 2 秒自动刷新';
  selectedModel();
}
function renderJob(job) {
  latestJob = job;
  const elapsed = Math.max(0, Math.round((job.finished || Date.now()/1000) - job.started));
  $('job-state').textContent = `${labels[job.action]} · ${job.phase} · ${elapsed}s`;
  if (job.action === 'chat') {
    $('empty').hidden = true; $('response').hidden = false;
    $('response').textContent = job.content || (job.state === 'running' ? '模型正在加载或处理问题，请稍候…' : '未收到模型正文。');
    if (job.metrics) { const m=job.metrics; $('result-meta').textContent = `耗时 ${m.seconds}s · ${m.tokens} token · ${m.tokens_per_second ?? '—'} token/s${m.truncated ? ' · 已到输出上限' : ''}`; }
    else $('result-meta').textContent = job.state === 'running' ? 'CPU 推理可能需要几分钟；正在读取真实输出。' : job.message;
  }
  if (job.state !== 'running' && announcedJob !== job.id) { announcedJob = job.id; notice(job.message, job.state === 'error'); }
  controls();
}
async function refresh() {
  if (refreshing || stopped) return;
  refreshing = true;
  try {
    if (!token) token = (await api('/api/session')).token;
    renderStatus(await api('/api/status'));
    if (state.active_job) renderJob(state.active_job);
    else if (latestJob?.state === 'running') renderJob(await api('/api/jobs/' + latestJob.id));
    else if (!latestJob && !posting) notice(state.error && state.online ? state.error : state.online ? '已连接本机 Ollama。可以加载模型，或直接发送测试问题。' : 'Ollama 尚未启动。点击“启动 Ollama”开始使用。', !!(state.error && state.online));
  } catch (error) {
    connected = false;
    $('connection').textContent = '○ 控制台连接中断';
    for (const id of ['service-state','memory-state','vram-state']) $(id).textContent = '未知';
    $('updated').textContent = '未能刷新；下方列表为上次读取结果';
    notice('无法连接本地控制台。请重新运行 Start-Console.cmd；若服务刚重启，请刷新页面。', true);
  } finally {
    refreshing = false; controls();
    clearTimeout(timer); if (!stopped) timer = setTimeout(refresh, 2000);
  }
}
async function action(name) {
  if (busy() || !connected) return;
  posting = true; controls(); notice('正在' + labels[name] + '…');
  try {
    const job = await api('/api/actions/' + name, {model:$('model').value, context:Number($('context').value), prompt:$('prompt').value});
    renderJob(job);
  } catch(error) { notice(error.message, true); }
  finally { posting = false; controls(); refresh(); }
}
for (const name of ['start','stop','load','unload']) $(name).addEventListener('click', () => action(name));
$('send').addEventListener('click', () => action('chat'));
$('model').addEventListener('change', selectedModel);
$('prompt').addEventListener('input', controls);
$('prompt').addEventListener('keydown', e => { if (e.ctrlKey && e.key === 'Enter' && !$('send').disabled) action('chat'); });
$('example').addEventListener('click', () => { $('prompt').value = '用 Python 编写一个函数，对字符串列表去重，保留首次出现的顺序。给出函数和一个使用示例，回答简洁。'; controls(); $('prompt').focus(); });
$('refresh').addEventListener('click', () => refresh());
$('copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText($('command').textContent); notice('命令已复制。在 CC Switch 中选好本地供应商后，到项目终端粘贴运行。'); }
  catch { const range=document.createRange(); range.selectNodeContents($('command')); const selection=getSelection(); selection.removeAllRanges(); selection.addRange(range); notice('命令已选中，请按 Ctrl+C 复制。'); }
});
$('exit').addEventListener('click', async () => {
  if (!confirm('退出控制台？由它启动的 Ollama 服务也会停止。')) return;
  try { await api('/api/exit', {}); stopped=true; connected=false; clearTimeout(timer); controls(); $('connection').textContent='控制台已退出'; notice('控制台已退出。下次双击 Start-Console.cmd 即可重新打开。'); }
  catch(error) { notice(error.message, true); }
});
refresh();
