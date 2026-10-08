"""Single-page web UI for the Camelot DJ Sorter."""

WEB_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Camelot DJ Sorter</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='15' fill='%2322d3ee'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%230d0f17'/%3E%3C/svg%3E">
<style>
  :root {
    --bg: #0d0f17; --panel: #161a29; --card: #1e2438; --border: #2b3553;
    --text: #f1f5f9; --dim: #94a3b8; --accent: #22d3ee; --green: #34d399;
    --red: #f87171; --yellow: #fbbf24; --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: radial-gradient(circle at top right, #1e1b4b, var(--bg) 60%) fixed;
         color: var(--text); min-height: 100vh; padding: 24px; font-size: 14px; }
  .container { max-width: 1200px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center;
           margin-bottom: 24px; padding-bottom: 18px; border-bottom: 1px solid var(--border); gap: 16px; }
  h1 { font-size: 22px; letter-spacing: -0.4px; }
  .subtitle { color: var(--dim); font-size: 13px; margin-top: 2px; }
  .badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px;
           font-size: 12px; font-weight: 600; border: 1px solid; white-space: nowrap; }
  .badge.ok { color: var(--green); border-color: rgba(52,211,153,.4); background: rgba(52,211,153,.12); }
  .badge.demo { color: var(--yellow); border-color: rgba(251,191,36,.4); background: rgba(251,191,36,.12); }
  .badge .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  .controls { padding: 18px; display: grid; grid-template-columns: 2fr 1.4fr 1.6fr auto; gap: 14px;
              align-items: end; margin-bottom: 16px; }
  .field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: var(--dim); }
  select, button { height: 42px; border-radius: 8px; font: inherit; }
  select { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 0 12px;
           width: 100%; outline: none; }
  select:focus { border-color: var(--accent); }
  select:disabled { opacity: .5; }
  .btn { border: 1px solid var(--border); background: var(--card); color: var(--text); padding: 0 16px;
         font-weight: 600; cursor: pointer; white-space: nowrap; }
  .btn:hover:not(:disabled) { background: var(--border); }
  .btn.primary { background: linear-gradient(135deg, #22d3ee, #3b82f6); border: none; color: #04111f; font-weight: 700; }
  .btn.primary:hover:not(:disabled) { filter: brightness(1.1); }
  .btn:disabled { opacity: .5; cursor: default; }
  .btn.small { height: 30px; padding: 0 10px; font-size: 12px; }
  .btn-row { display: flex; gap: 8px; }

  .notice { border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; display: none; line-height: 1.5; }
  .notice.show { display: block; }
  .notice.error { background: rgba(248,113,113,.12); border: 1px solid rgba(248,113,113,.4); color: #fecaca; }
  .notice.success { background: rgba(52,211,153,.12); border: 1px solid rgba(52,211,153,.4); color: #a7f3d0; }
  .notice.info { background: rgba(34,211,238,.08); border: 1px solid rgba(34,211,238,.3); color: #cffafe; }
  .notice.warn { background: rgba(251,191,36,.08); border: 1px solid rgba(251,191,36,.35); color: #fde68a; }

  .progress { padding: 16px 18px; margin-bottom: 16px; display: none; }
  .progress.show { display: block; }
  .bar { height: 6px; background: var(--card); border-radius: 3px; overflow: hidden; margin-top: 10px; }
  .bar > div { height: 100%; width: 0; background: linear-gradient(90deg, #22d3ee, #3b82f6); transition: width .2s; }
  .bar.indeterminate > div { width: 30%; animation: slide 1.1s infinite ease-in-out; }
  @keyframes slide { 0% { margin-left: -30%; } 100% { margin-left: 100%; } }
  .progress-text { color: var(--dim); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .empty { text-align: center; color: var(--dim); padding: 60px 20px; line-height: 1.7; }
  .empty strong { color: var(--text); font-size: 16px; display: block; margin-bottom: 6px; }

  .overview { display: grid; grid-template-columns: 1fr 220px; gap: 16px; margin-bottom: 16px; }
  .metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .metric { padding: 14px 16px; }
  .metric .t { font-size: 11px; color: var(--dim); text-transform: uppercase; font-weight: 700; letter-spacing: .4px; }
  .metric .v { font-size: 26px; font-weight: 800; margin: 4px 0 2px; }
  .metric .s { font-size: 12px; color: var(--dim); }
  .wheel-card { padding: 10px; display: flex; flex-direction: column; align-items: center; }
  .wheel-card .t { font-size: 11px; color: var(--dim); text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }

  .section { margin-bottom: 16px; overflow: hidden; }
  .section-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px;
                  border-bottom: 1px solid var(--border); gap: 12px; }
  .section-head h2 { font-size: 15px; }
  .section-head .meta { color: var(--dim); font-size: 13px; }
  .sugg { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 12px 18px;
          border-bottom: 1px solid rgba(255,255,255,.05); }
  .sugg:last-child { border-bottom: none; }
  .sugg .why { color: #cbd5e1; font-size: 13px; margin-top: 3px; }
  .sugg .tip { color: var(--dim); font-size: 12px; margin-top: 2px; }
  .sugg-section { border-color: rgba(248,113,113,.35); }
  .sugg-section .section-head h2 { color: var(--red); }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 10px 14px; font-size: 11px; text-transform: uppercase; color: var(--dim);
       background: rgba(0,0,0,.2); border-bottom: 1px solid var(--border); font-weight: 700; }
  td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.05); vertical-align: middle; }
  tr.flagged td { background: rgba(248,113,113,.06); }
  tr.unknown td { opacity: .75; }
  .num { color: var(--dim); font-weight: 700; width: 36px; }
  .title { font-weight: 600; }
  .artist { color: var(--dim); font-size: 12px; margin-top: 2px; }
  .src { font-size: 11px; color: #64748b; }
  .pill { display: inline-block; min-width: 42px; text-align: center; padding: 3px 8px; border-radius: 6px;
          font-weight: 800; font-size: 12px; letter-spacing: .4px; }
  .pill.none { background: #334155; color: #cbd5e1; }
  .trans { font-size: 12px; font-weight: 600; white-space: nowrap; }
  .trans.smooth { color: var(--green); } .trans.rough { color: var(--red); } .trans.unknown { color: var(--dim); }
  .x { background: none; border: 1px solid transparent; color: var(--dim); cursor: pointer; border-radius: 6px;
       height: 28px; padding: 0 8px; font-size: 12px; }
  .x:hover { color: var(--red); border-color: rgba(248,113,113,.4); }

  .export-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 18px;
                background: var(--card); border-top: 1px solid var(--border); position: sticky; bottom: 0; }
  .export-bar strong { color: var(--accent); }
  .removed-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 18px;
                  border-bottom: 1px solid rgba(255,255,255,.05); color: var(--dim); }
  .hidden { display: none !important; }
  @media (max-width: 900px) {
    .controls { grid-template-columns: 1fr 1fr; }
    .overview { grid-template-columns: 1fr; }
    .col-std, .col-src { display: none; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>Camelot DJ Sorter</h1>
      <div class="subtitle">Calculate keys, order your Apple Music playlist for harmonic mixing, and save it as a new “… sorted” playlist.</div>
    </div>
    <span id="mode-badge" class="badge ok"><span class="dot"></span><span id="mode-text">Connecting…</span></span>
  </header>

  <div class="panel controls">
    <div class="field">
      <label for="playlist">Playlist</label>
      <select id="playlist"><option>Loading playlists…</option></select>
    </div>
    <div class="field">
      <label for="strategy">Flow</label>
      <select id="strategy">
        <option value="gradual_build">Build energy (step up the wheel)</option>
        <option value="balanced">Smoothest overall</option>
      </select>
    </div>
    <div class="field">
      <label for="start">Start with</label>
      <select id="start" disabled><option value="">Best opener (automatic)</option></select>
    </div>
    <div class="btn-row">
      <button id="analyze" class="btn primary">Analyze &amp; Sort</button>
      <button id="refresh" class="btn" title="Reload playlists and re-read tracks from Music">↻</button>
    </div>
  </div>

  <div id="ffmpeg-notice" class="notice warn"></div>
  <div id="error" class="notice error"></div>
  <div id="success" class="notice success"></div>

  <div id="progress" class="panel progress">
    <div class="progress-text" id="progress-text">Working…</div>
    <div class="bar indeterminate" id="bar"><div></div></div>
  </div>

  <div id="empty" class="panel empty">
    <strong>Pick a playlist and press Analyze &amp; Sort</strong>
    Keys are read from each song's Comments/Grouping (where Mixed In Key and Rekordbox put them),<br>
    from tags inside the audio file, or calculated from the audio of downloaded, non-DRM files.<br>
    Your original playlist is never changed.
  </div>

  <div id="results" class="hidden">
    <div class="overview">
      <div class="metrics">
        <div class="panel metric"><div class="t">Smooth mixes</div><div class="v" id="m-smooth" style="color:var(--green)">–</div><div class="s" id="m-smooth-s"></div></div>
        <div class="panel metric"><div class="t">Key clashes</div><div class="v" id="m-clash" style="color:var(--red)">–</div><div class="s">transitions that won't blend</div></div>
        <div class="panel metric"><div class="t">Friction reduced</div><div class="v" id="m-improve" style="color:var(--accent)">–</div><div class="s" id="m-improve-s"></div></div>
        <div class="panel metric"><div class="t">Suggested removals</div><div class="v" id="m-remove" style="color:var(--yellow)">–</div><div class="s">songs that don't fit</div></div>
      </div>
      <div class="panel wheel-card"><div class="t">Keys in playlist</div><svg id="wheel" width="190" height="190" viewBox="-100 -100 200 200"></svg></div>
    </div>

    <div id="unknown-notice" class="notice info"></div>

    <div id="sugg-section" class="panel section sugg-section hidden">
      <div class="section-head">
        <h2>Suggested removals</h2>
        <button id="remove-all" class="btn small">Remove all suggested</button>
      </div>
      <div id="sugg-list"></div>
    </div>

    <div class="panel section">
      <div class="section-head">
        <h2>Sorted order</h2>
        <span class="meta" id="track-meta"></span>
      </div>
      <table>
        <thead><tr><th>#</th><th>Song</th><th>Key</th><th class="col-std">Musical key</th><th>BPM</th><th class="col-src">Key source</th><th>Mix into next</th><th></th></tr></thead>
        <tbody id="tracks"></tbody>
      </table>
      <div class="export-bar">
        <div>Will create <strong id="new-name"></strong> in Apple Music with <span id="export-count"></span> songs.</div>
        <button id="export" class="btn primary">Create sorted playlist</button>
      </div>
    </div>

    <div id="removed-section" class="panel section hidden">
      <div class="section-head">
        <h2>Removed from the sorted playlist</h2>
        <button id="restore-all" class="btn small">Restore all</button>
      </div>
      <div id="removed-list"></div>
    </div>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const KEY_COLORS = ['#0077b6','#0096c7','#00b4d8','#48cae4','#52b788','#74c69d','#ffd166','#f39c12','#e76f51','#e63946','#b5179e','#7209b7'];
const DARK_TEXT = new Set([3,4,5,6,7,8]);

let state = { result: null, excluded: new Set(), playlistId: null, busy: false };

function pill(k) {
  if (!k) return '<span class="pill none" title="Key unknown">?</span>';
  const bg = KEY_COLORS[k.number - 1], fg = DARK_TEXT.has(k.number) ? '#000' : '#fff';
  return `<span class="pill" style="background:${bg};color:${fg}" title="${esc(k.standard_name)}">${esc(k.camelot)}</span>`;
}

function show(id, html) { const el = $(id); if (html === null || html === undefined || html === '') { el.classList.remove('show'); el.innerHTML = ''; } else { el.innerHTML = html; el.classList.add('show'); } }

async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) };
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new Error('Lost connection to the app. Is it still running in Terminal?'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function setBusy(busy, label) {
  state.busy = busy;
  ['analyze','refresh','export','playlist','strategy','remove-all','restore-all'].forEach(id => { if ($(id)) $(id).disabled = busy; });
  $('start').disabled = busy || !state.result;
  document.querySelectorAll('.x, .sugg button, .removed-item button').forEach(b => b.disabled = busy);
  $('progress').classList.toggle('show', busy);
  if (busy) { $('progress-text').textContent = label || 'Working…'; $('bar').classList.add('indeterminate'); $('bar').firstElementChild.style.width = ''; }
}

let pollTimer = null;
function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const p = await api('/api/progress');
      if (!state.busy) return;
      if (p.total > 0) {
        $('bar').classList.remove('indeterminate');
        $('bar').firstElementChild.style.width = `${Math.round(100 * p.done / p.total)}%`;
        $('progress-text').textContent = `${p.done} / ${p.total} · ${p.current || ''}`;
      } else if (p.current) {
        $('progress-text').textContent = p.current;
      }
    } catch (e) {}
  }, 400);
}
function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = null; }

async function loadStatus() {
  try {
    const s = await api('/api/status');
    const demo = s.mode === 'demo';
    $('mode-badge').className = 'badge ' + (demo ? 'demo' : 'ok');
    $('mode-text').textContent = demo ? 'Demo library (not connected to Music)' : 'Connected to Music';
    show('ffmpeg-notice', s.ffmpeg ? '' : '<strong>ffmpeg not found.</strong> Keys can still be read from Comments/Grouping and tags, but audio analysis is off. Install it with <code>brew install ffmpeg</code> and restart the app.');
  } catch (e) { show('error', esc(e.message)); }
}

async function loadPlaylists() {
  const sel = $('playlist');
  const previous = sel.value;
  sel.innerHTML = '<option>Loading playlists…</option>';
  try {
    const data = await api('/api/playlists');
    const lists = data.playlists.filter(p => p.track_count > 0);
    if (!lists.length) { sel.innerHTML = '<option value="">No playlists with songs found</option>'; return; }
    sel.innerHTML = lists.map(p => `<option value="${esc(p.id)}">${esc(p.name)} (${p.track_count})${p.smart ? ' · smart' : ''}</option>`).join('');
    if (lists.some(p => p.id === previous)) sel.value = previous;
    show('error', '');
  } catch (e) {
    sel.innerHTML = '<option value="">Could not load playlists</option>';
    show('error', esc(e.message));
  }
}

async function analyze({ refresh = false, keepStart = true } = {}) {
  const playlistId = $('playlist').value;
  if (!playlistId) return;
  if (playlistId !== state.playlistId) { state.excluded.clear(); keepStart = false; state.result = null; }
  state.playlistId = playlistId;
  show('error', ''); show('success', '');
  setBusy(true, refresh || !state.result ? 'Reading playlist from Music…' : 'Sorting…');
  startPolling();
  try {
    const data = await api('/api/analyze', {
      playlist_id: playlistId, strategy: $('strategy').value, refresh,
      exclude_ids: [...state.excluded], start_id: keepStart ? $('start').value : '',
    });
    state.result = data;
    render(data);
  } catch (e) {
    show('error', esc(e.message));
  } finally {
    stopPolling();
    setBusy(false);
  }
}

function renderStartOptions(data) {
  const sel = $('start'); const current = sel.value;
  const songs = data.sorted_songs.filter(s => s.resolved_key);
  sel.innerHTML = '<option value="">Best opener (automatic)</option>' +
    songs.map(s => `<option value="${esc(s.id)}">${esc(s.resolved_key.camelot)} · ${esc(s.artist)} – ${esc(s.title)}</option>`).join('');
  if (songs.some(s => s.id === current)) sel.value = current;
}

function renderWheel(songs) {
  const counts = {};
  songs.forEach(s => { if (s.resolved_key) counts[s.resolved_key.camelot] = (counts[s.resolved_key.camelot] || 0) + 1; });
  const max = Math.max(1, ...Object.values(counts));
  const seg = (r0, r1, i) => {
    const a0 = (i * 30 - 105) * Math.PI / 180, a1 = ((i + 1) * 30 - 105) * Math.PI / 180;
    const p = (r, a) => `${(r * Math.cos(a)).toFixed(2)} ${(r * Math.sin(a)).toFixed(2)}`;
    return `M ${p(r1, a0)} A ${r1} ${r1} 0 0 1 ${p(r1, a1)} L ${p(r0, a1)} A ${r0} ${r0} 0 0 0 ${p(r0, a0)} Z`;
  };
  let svg = '';
  for (let i = 0; i < 12; i++) {
    const n = i + 1, mid = (i * 30 - 90) * Math.PI / 180;
    [['B', 62, 96], ['A', 30, 62]].forEach(([letter, r0, r1]) => {
      const c = counts[`${n}${letter}`] || 0;
      const op = c ? 0.35 + 0.65 * c / max : 0.08;
      svg += `<path d="${seg(r0, r1, i)}" fill="${KEY_COLORS[i]}" fill-opacity="${op}" stroke="#0d0f17" stroke-width="1.5"><title>${n}${letter}: ${c} song${c === 1 ? '' : 's'}</title></path>`;
      const r = (r0 + r1) / 2;
      svg += `<text x="${(r * Math.cos(mid)).toFixed(1)}" y="${(r * Math.sin(mid)).toFixed(1)}" text-anchor="middle" dominant-baseline="central" font-size="${letter === 'B' ? 10 : 9}" font-weight="700" fill="${c ? '#fff' : '#475569'}" pointer-events="none">${n}${letter}</text>`;
    });
  }
  $('wheel').innerHTML = svg;
}

function render(data) {
  $('empty').classList.add('hidden');
  $('results').classList.remove('hidden');
  const s = data.summary;

  $('m-smooth').textContent = s.scored_transitions ? `${s.smooth_transitions}/${s.scored_transitions}` : '–';
  $('m-smooth-s').textContent = 'transitions that blend well';
  $('m-clash').textContent = s.rough_transitions;
  $('m-improve').textContent = `${Math.round(s.improvement_percent)}%`;
  $('m-improve-s').textContent = `vs. original order (${s.initial_penalty} → ${s.final_penalty})`;
  $('m-remove').textContent = data.suggestions.length;
  renderWheel(data.sorted_songs);
  renderStartOptions(data);

  const unknown = data.sorted_songs.filter(x => !x.resolved_key);
  show('unknown-notice', unknown.length ? `<strong>${unknown.length} song${unknown.length > 1 ? 's have' : ' has'} no known key</strong> and ${unknown.length > 1 ? 'were' : 'was'} placed at the end. ` +
    `Streaming and DRM-protected songs can't be analyzed. Fix this by adding the key (e.g. <code>8A</code> or <code>Am</code>) to the song's Comments in Music, ` +
    `or by analyzing it with Mixed In Key / Rekordbox, then press ↻.` : '');

  const flagged = new Set(data.suggestions.map(x => x.song.id));
  $('sugg-section').classList.toggle('hidden', !data.suggestions.length);
  $('sugg-list').innerHTML = data.suggestions.map(x => `
    <div class="sugg">
      <div>
        <div class="title">${pill(x.song.resolved_key)} &nbsp;${esc(x.song.artist)} – ${esc(x.song.title)}</div>
        <div class="why">${esc(x.reason)}</div>
        <div class="tip">${esc(x.alternative_suggestion)}</div>
      </div>
      <button class="btn small" data-remove="${esc(x.song.id)}">Remove</button>
    </div>`).join('');

  $('tracks').innerHTML = data.sorted_songs.map((song, i) => {
    const t = data.transitions[i];
    let trans = '<span class="trans unknown">— end of set</span>';
    if (t) trans = `<span class="trans ${t.is_unknown ? 'unknown' : (t.is_smooth ? 'smooth' : 'rough')}">↓ ${esc(t.description)}</span>`;
    const k = song.resolved_key;
    const source = { metadata: 'Tag', file_tag: 'File tag', audio_analysis: `Audio · ${Math.round(song.confidence * 100)}%`, unknown: 'Unknown' }[song.key_source] || esc(song.key_source);
    const cls = flagged.has(song.id) ? 'flagged' : (k ? '' : 'unknown');
    return `<tr class="${cls}">
      <td class="num">${i + 1}</td>
      <td><div class="title">${esc(song.title)}</div><div class="artist">${esc(song.artist)}</div></td>
      <td>${pill(k)}</td>
      <td class="col-std" style="color:var(--dim)">${k ? esc(k.standard_name) : '—'}</td>
      <td style="color:var(--dim)">${song.bpm > 0 ? Math.round(song.bpm) : '—'}</td>
      <td class="col-src"><span class="src" title="${esc(song.key_note)}">${source}</span></td>
      <td>${trans}</td>
      <td><button class="x" data-remove="${esc(song.id)}" title="Leave this song out of the sorted playlist">✕</button></td>
    </tr>`;
  }).join('');

  $('track-meta').textContent = `${data.sorted_songs.length} songs` + (data.excluded_songs.length ? ` · ${data.excluded_songs.length} removed` : '');
  $('new-name').textContent = `“${data.new_playlist_name}”`;
  $('export-count').textContent = data.sorted_songs.length;

  $('removed-section').classList.toggle('hidden', !data.excluded_songs.length);
  $('removed-list').innerHTML = data.excluded_songs.map(x => `
    <div class="removed-item"><span>${pill(x.resolved_key)} &nbsp;${esc(x.artist)} – ${esc(x.title)}</span>
    <button class="btn small" data-restore="${esc(x.id)}">Restore</button></div>`).join('');
}

async function exportPlaylist() {
  if (!state.result) return;
  show('error', ''); show('success', '');
  setBusy(true, 'Creating playlist in Music…');
  try {
    const r = await api('/api/export', { playlist_id: state.result.playlist.id, ordered_ids: state.result.sorted_songs.map(s => s.id) });
    let msg = `✓ Created <strong>“${esc(r.name)}”</strong> in Apple Music with ${r.added} songs in harmonic order.`;
    if (r.replaced) msg += ' The previous sorted copy was replaced.';
    if (r.added < r.requested) msg += ` ${r.requested - r.added} song(s) could not be added (they may no longer be available).`;
    show('success', msg);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    loadPlaylists();
  } catch (e) {
    show('error', esc(e.message));
  } finally { setBusy(false); }
}

document.addEventListener('click', (e) => {
  const rm = e.target.closest('[data-remove]'), rs = e.target.closest('[data-restore]');
  if (state.busy) return;
  if (rm) { state.excluded.add(rm.dataset.remove); if ($('start').value === rm.dataset.remove) $('start').value = ''; analyze(); }
  if (rs) { state.excluded.delete(rs.dataset.restore); analyze(); }
});
$('analyze').addEventListener('click', () => analyze());
$('refresh').addEventListener('click', async () => { await loadPlaylists(); if (state.result) analyze({ refresh: true }); });
$('strategy').addEventListener('change', () => { if (state.result) analyze(); });
$('start').addEventListener('change', () => { if (state.result) analyze(); });
$('playlist').addEventListener('change', () => {
  state.result = null; state.excluded.clear();
  $('start').innerHTML = '<option value="">Best opener (automatic)</option>'; $('start').disabled = true;
  $('results').classList.add('hidden'); $('empty').classList.remove('hidden'); show('success', ''); show('error', '');
});
$('remove-all').addEventListener('click', () => { if (!state.result) return; state.result.suggestions.forEach(x => state.excluded.add(x.song.id)); analyze(); });
$('restore-all').addEventListener('click', () => { state.excluded.clear(); analyze(); });
$('export').addEventListener('click', exportPlaylist);

loadStatus();
loadPlaylists();
</script>
</body>
</html>
"""
