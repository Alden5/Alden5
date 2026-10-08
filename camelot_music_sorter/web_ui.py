"""
HTML & CSS & Vanilla JS single-page web UI for Camelot DJ Apple Music Sorter.
Features:
- Dark DJ-themed modern interface (neon accents, Camelot color coding)
- Playlist selector & refresh
- Interactive Camelot wheel legend & visual cues
- Initial vs Sorted comparison
- Transition flow indicators (Smooth vs Clash)
- Removal suggestions card with musical explanations and action to filter
- 'Create Sorted Playlist in Apple Music' one-click button with feedback
"""

WEB_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Camelot DJ - Apple Music Playlist Sorter</title>
  <style>
    :root {
      --bg-primary: #0d0f17;
      --bg-secondary: #161a29;
      --bg-card: #1e2438;
      --accent: #00f2fe;
      --accent-purple: #9d4edd;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-yellow: #f59e0b;
      --text-main: #f8fafc;
      --text-dim: #94a3b8;
      --border-color: #2b3553;
      --radius: 12px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: radial-gradient(circle at top right, #1e1b4b, var(--bg-primary) 60%);
      color: var(--text-main);
      min-height: 100vh;
      padding: 24px;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border-color);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .logo-badge {
      width: 52px;
      height: 52px;
      background: linear-gradient(135deg, var(--accent), var(--accent-purple));
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      font-weight: 800;
      box-shadow: 0 4px 20px rgba(0, 242, 254, 0.4);
    }

    h1 {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }

    .subtitle {
      color: var(--text-dim);
      font-size: 13px;
      margin-top: 2px;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: #34d399;
      box-shadow: 0 0 8px #34d399;
    }

    /* Controls row */
    .controls-panel {
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 20px;
      display: grid;
      grid-template-columns: 2fr 1.5fr auto auto;
      gap: 16px;
      align-items: flex-end;
      margin-bottom: 24px;
    }

    .field-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    label {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-dim);
    }

    select, input, button {
      height: 44px;
      border-radius: 8px;
      font-size: 14px;
      font-family: inherit;
    }

    select, input {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0 14px;
      outline: none;
      transition: border 0.2s;
    }

    select:focus, input:focus {
      border-color: var(--accent);
    }

    button.btn-primary {
      background: linear-gradient(135deg, #00f2fe, #4facfe);
      border: none;
      color: #0b1120;
      font-weight: 700;
      padding: 0 24px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: transform 0.1s, box-shadow 0.2s;
    }

    button.btn-primary:hover {
      box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4);
      transform: translateY(-1px);
    }

    button.btn-secondary {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      font-weight: 600;
      padding: 0 16px;
      cursor: pointer;
    }

    button.btn-secondary:hover {
      background: var(--border-color);
    }

    /* Metrics dashboard */
    .metrics-bar {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }

    .metric-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .metric-title {
      font-size: 12px;
      color: var(--text-dim);
      text-transform: uppercase;
      font-weight: 600;
    }

    .metric-value {
      font-size: 26px;
      font-weight: 800;
    }

    .metric-sub {
      font-size: 12px;
      color: var(--text-dim);
    }

    /* Outliers & Suggestions Banner */
    .suggestions-container {
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 24px;
      display: none;
    }

    .suggestions-container.active {
      display: block;
    }

    .suggestions-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .suggestions-title {
      font-size: 16px;
      font-weight: 700;
      color: #f87171;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .suggestion-item {
      background: var(--bg-card);
      border-left: 4px solid var(--accent-red);
      border-radius: 6px;
      padding: 14px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .sug-info strong {
      color: var(--text-main);
      font-size: 15px;
    }

    .sug-reason {
      color: #cbd5e1;
      font-size: 13px;
      margin-top: 4px;
    }

    /* Main track list */
    .tracks-panel {
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      overflow: hidden;
      margin-bottom: 30px;
    }

    .tracks-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 24px;
      border-bottom: 1px solid var(--border-color);
      background: var(--bg-secondary);
    }

    .tracks-table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    .tracks-table th {
      padding: 12px 20px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--text-dim);
      background: rgba(0,0,0,0.2);
      border-bottom: 1px solid var(--border-color);
    }

    .tracks-table td {
      padding: 14px 20px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 14px;
      vertical-align: middle;
    }

    .track-num {
      color: var(--text-dim);
      font-weight: 700;
      width: 40px;
    }

    .track-title {
      font-weight: 600;
      color: #fff;
    }

    .track-artist {
      color: var(--text-dim);
      font-size: 13px;
    }

    /* Camelot badges */
    .camelot-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 800;
      font-size: 13px;
      letter-spacing: 0.5px;
    }

    /* Specific Camelot colors */
    .k-1 { background: #0077b6; color: #fff; }
    .k-2 { background: #0096c7; color: #fff; }
    .k-3 { background: #00b4d8; color: #000; }
    .k-4 { background: #48cae4; color: #000; }
    .k-5 { background: #52b788; color: #000; }
    .k-6 { background: #74c69d; color: #000; }
    .k-7 { background: #ffd166; color: #000; }
    .k-8 { background: #f39c12; color: #000; }
    .k-9 { background: #e76f51; color: #fff; }
    .k-10 { background: #e63946; color: #fff; }
    .k-11 { background: #b5179e; color: #fff; }
    .k-12 { background: #7209b7; color: #fff; }

    .transition-row {
      background: rgba(0,0,0,0.3);
    }

    .transition-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 0;
    }

    .trans-smooth { color: #34d399; }
    .trans-energy { color: #38bdf8; }
    .trans-rough { color: #f87171; }

    /* Action bar */
    .action-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 24px;
      background: var(--bg-card);
      border-top: 1px solid var(--border-color);
    }

    .export-alert {
      display: none;
      padding: 12px 18px;
      border-radius: 8px;
      font-size: 14px;
      margin-top: 16px;
    }
    .export-alert.success {
      display: block;
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid #10b981;
      color: #34d399;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <div class="logo-badge">🎛️</div>
        <div>
          <h1>Camelot DJ Sorter for Apple Music</h1>
          <div class="subtitle">Harmonic Key Analysis &middot; Optimal DJ Transitions &middot; Outlier Suggestions</div>
        </div>
      </div>
      <div id="env-badge" class="status-badge">
        <span class="status-dot"></span>
        <span id="platform-status">Ready</span>
      </div>
    </header>

    <div class="controls-panel">
      <div class="field-group">
        <label>Select Apple Music Playlist</label>
        <select id="playlist-select">
          <option value="">Loading playlists...</option>
        </select>
      </div>

      <div class="field-group">
        <label>Harmonic Flow Strategy</label>
        <select id="strategy-select">
          <option value="gradual_build">Energy Ascent (Harmonic Step +1 / Uplift)</option>
          <option value="balanced">Balanced Smooth Flow (Minimal Clash)</option>
        </select>
      </div>

      <div>
        <button id="btn-analyze" class="btn-primary">
          <span>Sort &amp; Analyze</span>
        </button>
      </div>

      <div>
        <button id="btn-refresh" class="btn-secondary" title="Refresh playlists from Music.app">
          &#8635; Refresh
        </button>
      </div>
    </div>

    <!-- Metrics -->
    <div class="metrics-bar" id="metrics-bar" style="display: none;">
      <div class="metric-card">
        <div class="metric-title">Harmonic Improvement</div>
        <div class="metric-value" id="val-improvement" style="color: var(--accent);">+0%</div>
        <div class="metric-sub" id="sub-penalty">Friction reduced</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Smooth DJ Transitions</div>
        <div class="metric-value" id="val-smooth" style="color: var(--accent-green);">0 / 0</div>
        <div class="metric-sub">Harmonic compatible mixes</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Key Clashes</div>
        <div class="metric-value" id="val-clashes" style="color: var(--accent-red);">0</div>
        <div class="metric-sub">Transitions &gt; 3 Camelot steps</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Suggested Removals</div>
        <div class="metric-value" id="val-removals" style="color: var(--accent-yellow);">0</div>
        <div class="metric-sub">Harmonic bottleneck outliers</div>
      </div>
    </div>

    <!-- Suggested Removals Section -->
    <div id="suggestions-box" class="suggestions-container">
      <div class="suggestions-header">
        <div class="suggestions-title">
          <span>⚠️</span> Recommended Songs to Remove from this Mix
        </div>
        <button id="btn-exclude-removals" class="btn-secondary" style="font-size: 12px; height: 32px;">
          Exclude These &amp; Re-sort
        </button>
      </div>
      <div id="suggestions-list"></div>
    </div>

    <!-- Sorted Tracks Table -->
    <div class="tracks-panel" id="tracks-panel" style="display: none;">
      <div class="tracks-panel-header">
        <div style="font-weight: 700; font-size: 16px;">
          Harmonically Sorted Tracklist
        </div>
        <div style="font-size: 13px; color: var(--text-dim);" id="track-count-badge">
          0 tracks
        </div>
      </div>

      <table class="tracks-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Title &amp; Artist</th>
            <th>Camelot Key</th>
            <th>Standard Key</th>
            <th>BPM</th>
            <th>Transition to Next</th>
          </tr>
        </thead>
        <tbody id="tracks-body"></tbody>
      </table>

      <div class="action-bar">
        <div style="font-size: 13px; color: var(--text-dim);">
          Will create playlist: <strong id="new-playlist-preview" style="color: var(--accent);"></strong>
        </div>
        <button id="btn-export" class="btn-primary">
          <span>Apply to Apple Music (Create Playlist)</span>
        </button>
      </div>
    </div>

    <div id="export-feedback" class="export-alert"></div>
  </div>

  <script>
    let currentPlaylists = [];
    let currentSortResult = null;
    let excludedIds = new Set();

    async function loadPlaylists() {
      try {
        const res = await fetch('/api/playlists');
        const data = await res.json();
        currentPlaylists = data.playlists || [];
        document.getElementById('platform-status').textContent = data.is_macos ? 'Connected to Music.app' : 'Emulation Mode (macOS ready)';
        
        const sel = document.getElementById('playlist-select');
        sel.innerHTML = '';
        if (currentPlaylists.length === 0) {
          sel.innerHTML = '<option value="">No playlists found</option>';
          return;
        }

        currentPlaylists.forEach(pl => {
          const opt = document.createElement('option');
          opt.value = pl.name;
          opt.textContent = `${pl.name} (${pl.track_count} tracks)`;
          sel.appendChild(opt);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function analyzeAndSort() {
      const playlistName = document.getElementById('playlist-select').value;
      const strategy = document.getElementById('strategy-select').value;
      if (!playlistName) return;

      document.getElementById('btn-analyze').innerHTML = '<span>Calculating keys...</span>';

      try {
        const res = await fetch('/api/sort', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            playlist: playlistName,
            strategy: strategy,
            exclude_ids: Array.from(excludedIds)
          })
        });

        const data = await res.json();
        currentSortResult = data;
        renderResults(data);
      } catch (e) {
        alert("Failed to analyze: " + e);
      } finally {
        document.getElementById('btn-analyze').innerHTML = '<span>Sort &amp; Analyze</span>';
      }
    }

    function renderResults(data) {
      document.getElementById('metrics-bar').style.display = 'grid';
      document.getElementById('tracks-panel').style.display = 'block';

      // Summary
      const summary = data.summary;
      document.getElementById('val-improvement').textContent = `+${summary.improvement_percent}%`;
      document.getElementById('sub-penalty').textContent = `Score: ${summary.initial_penalty} -> ${summary.final_penalty}`;
      document.getElementById('val-smooth').textContent = `${summary.smooth_transitions} / ${data.transitions.length}`;
      document.getElementById('val-clashes').textContent = `${summary.rough_transitions}`;
      document.getElementById('val-removals').textContent = `${data.suggestions.length}`;

      // Removals
      const sugBox = document.getElementById('suggestions-box');
      const sugList = document.getElementById('suggestions-list');
      sugList.innerHTML = '';
      if (data.suggestions.length > 0) {
        sugBox.classList.add('active');
        data.suggestions.forEach(sug => {
          const item = document.createElement('div');
          item.className = 'suggestion-item';
          item.innerHTML = `
            <div class="sug-info">
              <strong>${sug.song.artist} - ${sug.song.title}</strong>
              <div class="sug-reason">${sug.reason} &bull; <em>${sug.alternative_suggestion}</em></div>
            </div>
            <div>
              <span class="camelot-pill k-${sug.song.resolved_key?.number || 1}">${sug.song.resolved_key?.camelot || '??'}</span>
            </div>
          `;
          sugList.appendChild(item);
        });
      } else {
        sugBox.classList.remove('active');
      }

      // Tracklist table
      const tbody = document.getElementById('tracks-body');
      tbody.innerHTML = '';
      document.getElementById('track-count-badge').textContent = `${data.sorted_songs.length} tracks`;
      document.getElementById('new-playlist-preview').textContent = `${data.playlist_name} sorted`;

      data.sorted_songs.forEach((song, idx) => {
        const tr = document.createElement('tr');
        const kNum = song.resolved_key ? song.resolved_key.number : 1;
        const kStr = song.resolved_key ? song.resolved_key.camelot : 'Unknown';
        const kStd = song.resolved_key ? song.resolved_key.standard_name : 'Unknown';
        
        let transText = '-';
        let transClass = '';
        if (idx < data.transitions.length) {
          const t = data.transitions[idx];
          transClass = t.is_smooth ? 'trans-smooth' : 'trans-rough';
          transText = `<span class="${transClass}">&#8595; ${t.description}</span>`;
        }

        tr.innerHTML = `
          <td class="track-num">${idx + 1}</td>
          <td>
            <div class="track-title">${song.title}</div>
            <div class="track-artist">${song.artist} &middot; <span style="font-size:11px; color:#64748b;">${song.key_source}</span></div>
          </td>
          <td>
            <span class="camelot-pill k-${kNum}">${kStr}</span>
          </td>
          <td style="color: var(--text-dim);">${kStd}</td>
          <td style="color: var(--text-dim);">${song.bpm > 0 ? Math.round(song.bpm) : '--'}</td>
          <td>${transText}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function exportToAppleMusic() {
      if (!currentSortResult) return;
      const btn = document.getElementById('btn-export');
      btn.innerHTML = '<span>Creating in Apple Music...</span>';

      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            original_name: currentSortResult.playlist_name,
            sorted_track_ids: currentSortResult.sorted_songs.map(s => s.id)
          })
        });

        const data = await res.json();
        const alertBox = document.getElementById('export-feedback');
        alertBox.className = 'export-alert success';
        alertBox.innerHTML = `&#10004; Successfully created playlist <strong>"${data.created_playlist}"</strong> in Apple Music with songs arranged in harmonic Camelot order!`;
        window.scrollTo({ top: alertBox.offsetTop - 50, behavior: 'smooth' });
      } catch (e) {
        alert("Failed to export: " + e);
      } finally {
        btn.innerHTML = '<span>Apply to Apple Music (Create Playlist)</span>';
      }
    }

    document.getElementById('btn-analyze').addEventListener('click', () => {
      excludedIds.clear();
      analyzeAndSort();
    });

    document.getElementById('btn-refresh').addEventListener('click', loadPlaylists);
    document.getElementById('btn-export').addEventListener('click', exportToAppleMusic);
    document.getElementById('btn-exclude-removals').addEventListener('click', () => {
      if (currentSortResult && currentSortResult.suggestions) {
        currentSortResult.suggestions.forEach(s => excludedIds.add(s.song.id));
        analyzeAndSort();
      }
    });

    window.addEventListener('DOMContentLoaded', loadPlaylists);
  </script>
</body>
</html>
"""
