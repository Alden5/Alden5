"""Single-page web UI for the Camelot DJ Sorter."""

WEB_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Camelot DJ Sorter</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='15' fill='%2322d3ee'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%230b0d14'/%3E%3C/svg%3E">
<style>
  :root {
    --bg: #0b0d14; --side: #10131d; --panel: #151a28; --card: #1b2133; --hover: #222a40; --border: #262f48;
    --text: #eef2f8; --dim: #8e9ab3; --faint: #5b6680; --accent: #22d3ee; --accent2: #6366f1;
    --green: #34d399; --red: #f87171; --yellow: #fbbf24; --manual: #c084fc; --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); font-size: 14px; -webkit-font-smoothing: antialiased; }
  button, input { font: inherit; color: inherit; }
  button { cursor: pointer; }
  button:disabled { cursor: default; opacity: .45; }
  svg.i { width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; flex: none; }
  .hidden { display: none !important; }
  kbd { font: 11px ui-monospace, Menlo, monospace; background: var(--card); border: 1px solid var(--border);
        border-bottom-width: 2px; border-radius: 4px; padding: 0 5px; color: var(--dim); }

  .app { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }

  /* Sidebar */
  aside { background: var(--side); border-right: 1px solid var(--border); position: sticky; top: 0; height: 100vh;
          display: flex; flex-direction: column; min-width: 0; }
  .brand { display: flex; align-items: center; gap: 10px; padding: 20px 18px 14px; }
  .logo { width: 34px; height: 34px; border-radius: 10px; flex: none;
          background: conic-gradient(#0077b6, #00b4d8, #52b788, #ffd166, #f39c12, #e63946, #b5179e, #7209b7, #0077b6);
          position: relative; }
  .logo::after { content: ""; position: absolute; inset: 10px; border-radius: 50%; background: var(--side); }
  .brand h1 { font-size: 15px; letter-spacing: -.2px; }
  .brand .sub { font-size: 11.5px; color: var(--dim); }
  .mode { margin: 0 18px 12px; display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dim); }
  .mode .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); }
  .mode.ok .dot { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .mode.demo .dot { background: var(--yellow); }
  .side-search { margin: 0 14px 8px; position: relative; }
  .side-search input, .filter input { width: 100%; height: 34px; border-radius: 8px; background: var(--card);
          border: 1px solid var(--border); padding: 0 10px 0 32px; outline: none; }
  .side-search input:focus, .filter input:focus { border-color: var(--accent); }
  .side-search svg, .filter svg { position: absolute; left: 10px; top: 9px; color: var(--faint); }
  .side-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 18px 6px;
               font-size: 11px; font-weight: 700; letter-spacing: .6px; text-transform: uppercase; color: var(--faint); }
  .icon-btn { background: none; border: 1px solid transparent; border-radius: 7px; height: 28px; min-width: 28px;
              display: inline-flex; align-items: center; justify-content: center; gap: 6px; color: var(--dim); padding: 0 6px; }
  .icon-btn:hover:not(:disabled) { background: var(--hover); color: var(--text); }
  .pl-list { overflow-y: auto; flex: 1; padding: 0 8px 16px; }
  .pl { width: 100%; display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px;
        background: none; border: none; text-align: left; color: var(--text); }
  .pl:hover { background: var(--hover); }
  .pl.active { background: linear-gradient(90deg, rgba(34,211,238,.16), rgba(99,102,241,.10)); }
  .pl.active .pl-name { color: #fff; }
  .pl-art { width: 32px; height: 32px; border-radius: 7px; flex: none; display: grid; place-items: center;
            font-size: 12px; font-weight: 800; color: rgba(255,255,255,.9); }
  .pl-name { font-weight: 600; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #d6dceb; }
  .pl-meta { font-size: 11.5px; color: var(--faint); }
  .pl-text { min-width: 0; flex: 1; }
  .side-empty { color: var(--faint); font-size: 13px; padding: 12px 12px; line-height: 1.5; }

  /* Main */
  main { min-width: 0; display: flex; flex-direction: column; }
  .busy-line { position: sticky; top: 0; height: 3px; z-index: 30; overflow: hidden; }
  .busy-line > div { height: 100%; width: 30%; background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent);
                     animation: slide 1s infinite ease-in-out; }
  @keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(340%); } }
  .content { padding: 26px 28px 0; flex: 1; display: flex; flex-direction: column; }
  .notice { border-radius: 10px; padding: 11px 14px; margin-bottom: 14px; line-height: 1.5; font-size: 13px; display: none; }
  .notice.show { display: block; }
  .notice.error { background: rgba(248,113,113,.10); border: 1px solid rgba(248,113,113,.35); color: #fecaca; }
  .notice.success { background: rgba(52,211,153,.10); border: 1px solid rgba(52,211,153,.35); color: #a7f3d0; }
  .notice.info { background: rgba(34,211,238,.07); border: 1px solid rgba(34,211,238,.28); color: #cffafe; }
  .notice.warn { background: rgba(251,191,36,.07); border: 1px solid rgba(251,191,36,.3); color: #fde68a; }
  code { font: 12px ui-monospace, Menlo, monospace; background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 4px; }

  .welcome { margin: auto; max-width: 620px; text-align: center; padding: 60px 20px; }
  .welcome h2 { font-size: 26px; letter-spacing: -.5px; margin-bottom: 8px; }
  .welcome p { color: var(--dim); line-height: 1.6; }
  .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 28px; text-align: left; }
  .step { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; }
  .step b { display: block; margin-bottom: 4px; font-size: 13px; }
  .step span { color: var(--dim); font-size: 12.5px; line-height: 1.5; }
  .step .n { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 800;
             background: rgba(34,211,238,.15); color: var(--accent); margin-bottom: 10px; }

  .loading { margin: auto; width: min(460px, 100%); text-align: center; padding: 80px 20px; }
  .loading h3 { font-size: 17px; margin-bottom: 6px; }
  .loading .cur { color: var(--dim); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-height: 18px; }
  .bar { height: 6px; background: var(--card); border-radius: 3px; overflow: hidden; margin: 16px 0 8px; }
  .bar > div { height: 100%; width: 0; background: linear-gradient(90deg, var(--accent), var(--accent2)); transition: width .25s; border-radius: 3px; }
  .bar.indeterminate > div { width: 30%; animation: slide 1.1s infinite ease-in-out; }
  .spinner { width: 42px; height: 42px; margin: 0 auto 18px; border-radius: 50%;
             background: conic-gradient(var(--accent), var(--accent2), transparent 70%); animation: spin 1s linear infinite;
             -webkit-mask: radial-gradient(farthest-side, transparent 70%, #000 72%); mask: radial-gradient(farthest-side, transparent 70%, #000 72%); }
  @keyframes spin { to { transform: rotate(360deg); } }

  .head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
  .head h2 { font-size: 26px; letter-spacing: -.6px; line-height: 1.15; word-break: break-word; }
  .head .meta { color: var(--dim); margin-top: 4px; font-size: 13px; }
  .head .meta b { color: var(--manual); font-weight: 600; }
  .toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .seg { display: inline-flex; background: var(--card); border: 1px solid var(--border); border-radius: 9px; padding: 3px; }
  .seg button { border: none; background: none; height: 28px; padding: 0 12px; border-radius: 6px; color: var(--dim); font-weight: 600; font-size: 13px; }
  .seg button.on { background: var(--hover); color: var(--text); box-shadow: 0 1px 2px rgba(0,0,0,.4); }
  .btn { height: 34px; border-radius: 9px; border: 1px solid var(--border); background: var(--card); padding: 0 13px;
         font-weight: 600; font-size: 13px; display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
  .btn:hover:not(:disabled) { background: var(--hover); }
  .btn.primary { background: linear-gradient(135deg, #22d3ee, #6366f1); border: none; color: #050b18; font-weight: 700; }
  .btn.primary:hover:not(:disabled) { filter: brightness(1.1); }
  .btn.manual { color: var(--manual); border-color: rgba(192,132,252,.35); }
  .btn.sm { height: 28px; padding: 0 10px; font-size: 12px; border-radius: 7px; }

  .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
  .stat { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 13px 15px; }
  .stat .t { font-size: 11px; color: var(--dim); text-transform: uppercase; font-weight: 700; letter-spacing: .5px; }
  .stat .v { font-size: 24px; font-weight: 800; margin: 3px 0 1px; letter-spacing: -.5px; }
  .stat .s { font-size: 12px; color: var(--faint); }
  .meter { height: 4px; border-radius: 2px; background: var(--card); margin-top: 8px; overflow: hidden; }
  .meter > div { height: 100%; background: var(--green); border-radius: 2px; transition: width .4s; }

  .grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: start; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  .card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 14px;
               border-bottom: 1px solid var(--border); flex-wrap: wrap; }
  .card-head h3 { font-size: 14px; }
  .card-head .hint { color: var(--faint); font-size: 12px; }
  .filter { position: relative; width: 220px; }

  /* Track list */
  .tracks { position: relative; padding: 6px 0; }
  .row { display: grid; grid-template-columns: 22px 26px 46px minmax(0, 1fr) auto 48px 46px 94px; gap: 10px; align-items: center;
         padding: 7px 12px 7px 8px; margin: 0 6px; border-radius: 9px; border: 1px solid transparent; background: var(--panel);
         position: relative; user-select: none; }
  .row:hover { background: var(--hover); }
  .row.manual { background: linear-gradient(90deg, rgba(192,132,252,.10), transparent 60%); border-color: rgba(192,132,252,.25); }
  .row.manual:hover { background: linear-gradient(90deg, rgba(192,132,252,.16), var(--hover) 60%); }
  .row.flagged { box-shadow: inset 3px 0 0 var(--red); }
  .row.unknown .song, .row.unknown .bpm { opacity: .6; }
  .row.dragging { opacity: .35; }
  .row.flash { animation: flash 1.2s ease-out; }
  .row.placed { animation: placed 1.6s ease-out; }
  @keyframes flash { 0% { background: rgba(34,211,238,.18); } 100% { } }
  @keyframes placed { 0% { background: rgba(192,132,252,.35); transform: scale(1.01); } 100% { } }
  .handle { color: var(--faint); cursor: grab; display: grid; place-items: center; height: 28px; border-radius: 5px; }
  .row:hover .handle { color: var(--dim); }
  .handle:active { cursor: grabbing; }
  .pos { color: var(--faint); font-weight: 700; font-size: 12.5px; text-align: right; font-variant-numeric: tabular-nums; }
  .song { min-width: 0; }
  .song .title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .song .artist { color: var(--dim); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 1px; }
  .tags { display: flex; gap: 5px; align-items: center; }
  .tag { font-size: 10.5px; font-weight: 700; letter-spacing: .3px; padding: 2px 7px; border-radius: 20px; white-space: nowrap;
         display: inline-flex; align-items: center; gap: 4px; }
  .tag.manual { color: var(--manual); background: rgba(192,132,252,.14); border: 1px solid rgba(192,132,252,.3); }
  .tag.flag { color: var(--red); background: rgba(248,113,113,.12); border: 1px solid rgba(248,113,113,.3); }
  .tag.src { color: var(--faint); background: rgba(255,255,255,.04); border: 1px solid var(--border); font-weight: 600; }
  .tag svg.i { width: 11px; height: 11px; }
  .bpm, .dur { color: var(--dim); font-size: 12.5px; text-align: right; font-variant-numeric: tabular-nums; }
  .actions { display: flex; justify-content: flex-end; gap: 2px; opacity: 0; transition: opacity .12s; }
  .row:hover .actions, .row:focus-within .actions, .row.manual .actions { opacity: 1; }
  .actions .icon-btn { height: 28px; width: 28px; padding: 0; }
  .actions .pin.on { color: var(--manual); }
  .actions .rm:hover { color: var(--red); }
  .pill { display: inline-block; width: 44px; text-align: center; padding: 4px 0; border-radius: 7px;
          font-weight: 800; font-size: 12px; letter-spacing: .3px; }
  .pill.none { background: #2a3248; color: #aab4c8; }
  .conn { display: flex; align-items: center; gap: 8px; height: 18px; padding-left: 52px; font-size: 11.5px; color: var(--faint); }
  .conn::before { content: ""; width: 2px; height: 100%; background: currentColor; opacity: .5; margin-left: 9px; margin-right: 6px; border-radius: 1px; }
  .conn.smooth { color: rgba(52,211,153,.8); } .conn.rough { color: var(--red); } .conn.unknown { color: var(--faint); }
  .conn .d { opacity: .95; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .drop-line { position: absolute; left: 10px; right: 10px; height: 3px; border-radius: 2px; background: var(--manual);
               box-shadow: 0 0 12px var(--manual); pointer-events: none; z-index: 5; display: none; }
  .drop-line::before { content: ""; position: absolute; left: -5px; top: -4px; width: 11px; height: 11px; border-radius: 50%;
                       background: var(--bg); border: 3px solid var(--manual); box-sizing: border-box; }
  .drop-line span { position: absolute; right: 0; top: -22px; font-size: 11px; font-weight: 700; color: #fff; background: var(--manual);
                    padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
  .no-match { color: var(--faint); padding: 26px; text-align: center; }

  .export { position: sticky; bottom: 0; z-index: 20; margin: 16px -28px 0; padding: 14px 28px;
            background: rgba(11,13,20,.86); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap; }
  .export .what { color: var(--dim); font-size: 13px; }
  .export .what strong { color: var(--text); }

  /* Side panel */
  .side-panel { display: flex; flex-direction: column; gap: 16px; position: sticky; top: 16px; }
  .panel-body { padding: 12px 14px; }
  .wheel-wrap { display: flex; justify-content: center; padding: 10px 0 4px; }
  .legend { display: flex; justify-content: center; gap: 14px; font-size: 11.5px; color: var(--faint); padding-bottom: 12px; }
  .legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  #journey { width: 100%; height: 130px; display: block; }
  .journey-cap { font-size: 11.5px; color: var(--faint); margin-top: 6px; line-height: 1.5; }
  .budget { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--dim); padding: 12px 14px; border-bottom: 1px solid var(--border); }
  .stepper { display: inline-flex; align-items: center; background: var(--card); border: 1px solid var(--border); border-radius: 9px; overflow: hidden; }
  .stepper button { border: none; background: none; width: 30px; height: 32px; font-size: 16px; color: var(--dim); }
  .stepper button:hover:not(:disabled) { background: var(--hover); color: var(--text); }
  .stepper input { width: 40px; height: 32px; border: none; background: none; text-align: center; font-weight: 800; font-size: 15px; outline: none; -moz-appearance: textfield; }
  .stepper input::-webkit-inner-spin-button { -webkit-appearance: none; }
  .trim-body { padding: 12px 14px 14px; transition: opacity .2s; }
  .trim-body.stale { opacity: .45; }
  .headline { font-size: 13.5px; line-height: 1.5; font-weight: 600; }
  .headline.good { color: #a7f3d0; }
  .compare { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }
  .cmp { background: var(--card); border: 1px solid var(--border); border-radius: 9px; padding: 8px 9px; }
  .cmp .t { font-size: 10.5px; color: var(--dim); text-transform: uppercase; font-weight: 700; letter-spacing: .4px; }
  .cmp .v { font-size: 15px; font-weight: 800; margin-top: 3px; white-space: nowrap; }
  .cmp .v s { color: var(--faint); font-weight: 600; text-decoration: none; font-size: 13px; }
  .cmp .d { font-size: 11px; font-weight: 700; margin-top: 2px; }
  .cmp .d.up { color: var(--green); } .cmp .d.flat { color: var(--faint); }
  .hint-box { font-size: 12.5px; line-height: 1.45; color: #cffafe; background: rgba(34,211,238,.07); border: 1px solid rgba(34,211,238,.28);
              border-radius: 9px; padding: 8px 10px; margin: 10px 0; display: flex; gap: 10px; align-items: center; justify-content: space-between; }
  .sugg { padding: 10px 0; border-top: 1px solid var(--border); }
  .sugg .who { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; }
  .sugg .who .n { color: var(--faint); font-size: 12px; width: 14px; text-align: right; flex: none; }
  .sugg .who .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1; }
  .sugg .impact { font-size: 11.5px; color: var(--green); margin: 5px 0 0 22px; font-weight: 600; }
  .sugg .why { color: #9aa6bd; font-size: 12px; margin: 4px 0 0 22px; line-height: 1.45; }
  .sugg .btns { margin: 7px 0 0 22px; display: flex; gap: 6px; }
  .trim-apply { width: 100%; justify-content: center; margin-top: 10px; height: 36px; }
  .tray { min-height: 54px; padding: 6px; transition: background .15s; border-radius: 0 0 var(--radius) var(--radius); }
  .tray.over { background: rgba(248,113,113,.08); box-shadow: inset 0 0 0 2px rgba(248,113,113,.4); }
  .tray-empty { color: var(--faint); font-size: 12.5px; text-align: center; padding: 14px 8px; line-height: 1.5; }
  .tray-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 8px; cursor: grab; }
  .tray-item:hover { background: var(--hover); }
  .tray-item .pill { width: 38px; font-size: 11px; padding: 3px 0; }
  .tray-item .t { flex: 1; min-width: 0; font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #c6cede; }

  .popover { position: fixed; z-index: 50; background: var(--card); border: 1px solid var(--border); border-radius: 11px;
             box-shadow: 0 16px 40px rgba(0,0,0,.55); padding: 12px; width: 230px; }
  .popover label { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; font-weight: 700; color: var(--dim); display: block; margin-bottom: 7px; }
  .popover .r { display: flex; gap: 6px; }
  .popover input { width: 100%; height: 32px; border-radius: 7px; background: var(--bg); border: 1px solid var(--border); padding: 0 9px; outline: none; }
  .popover input:focus { border-color: var(--manual); }
  .popover .q { display: flex; gap: 6px; margin-top: 8px; }
  .popover .note { font-size: 11.5px; color: var(--faint); margin-top: 8px; line-height: 1.45; }

  .toasts { position: fixed; bottom: 84px; left: 50%; transform: translateX(-50%); z-index: 60; display: flex; flex-direction: column; gap: 8px; align-items: center; pointer-events: none; }
  .toast { pointer-events: auto; background: #f1f5f9; color: #0b1120; border-radius: 10px; padding: 9px 10px 9px 14px; font-size: 13px; font-weight: 500;
           display: flex; align-items: center; gap: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.45); animation: pop .2s ease-out; max-width: min(560px, 90vw); }
  .toast.err { background: #fecaca; }
  .toast button { border: none; background: rgba(0,0,0,.08); color: #0b1120; font-weight: 700; border-radius: 7px; height: 26px; padding: 0 10px; font-size: 12px; }
  .toast button:hover { background: rgba(0,0,0,.15); }
  @keyframes pop { from { opacity: 0; transform: translateY(8px); } }

  @media (max-width: 1250px) {
    .grid { grid-template-columns: minmax(0, 1fr); }
    .side-panel { position: static; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
  }
  @media (max-width: 900px) {
    .app { grid-template-columns: 1fr; }
    aside { position: static; height: auto; max-height: 46vh; border-right: none; border-bottom: 1px solid var(--border); }
    .content { padding: 18px 14px 0; }
    .export { margin: 16px -14px 0; padding: 12px 14px; }
    .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .row { grid-template-columns: 22px 24px 44px minmax(0, 1fr) 40px 94px; }
    .row .tags, .row .dur { display: none; }
    .steps { grid-template-columns: 1fr; }
    .filter { width: 100%; }
  }
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute">
  <symbol id="i-grip" viewBox="0 0 24 24"><circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/></symbol>
  <symbol id="i-pin" viewBox="0 0 24 24"><path d="M12 17v5"/><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"/></symbol>
  <symbol id="i-move" viewBox="0 0 24 24"><path d="M7 4v16"/><path d="m3 8 4-4 4 4"/><path d="M17 20V4"/><path d="m21 16-4 4-4-4"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></symbol>
  <symbol id="i-undo" viewBox="0 0 24 24"><path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/></symbol>
  <symbol id="i-redo" viewBox="0 0 24 24"><path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/></symbol>
  <symbol id="i-sort" viewBox="0 0 24 24"><path d="M3 6h13M3 12h9M3 18h5"/><path d="m17 15 3 3 3-3M20 18V6"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="i-music" viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></symbol>
</svg>

<div class="app">
  <aside>
    <div class="brand">
      <div class="logo"></div>
      <div><h1>Camelot DJ Sorter</h1><div class="sub">Harmonic order for Apple Music</div></div>
    </div>
    <div id="mode" class="mode"><span class="dot"></span><span id="mode-text">Connecting…</span></div>
    <div class="side-search">
      <svg class="i"><use href="#i-search"/></svg>
      <input id="pl-search" type="search" placeholder="Search playlists" autocomplete="off">
    </div>
    <div class="side-head"><span>Playlists</span>
      <button id="refresh" class="icon-btn" title="Reload playlists and re-read tracks from Music"><svg class="i"><use href="#i-refresh"/></svg></button>
    </div>
    <div id="pl-list" class="pl-list"><div class="side-empty">Loading playlists…</div></div>
  </aside>

  <main>
    <div id="busy-line" class="busy-line hidden"><div></div></div>
    <div class="content">
      <div id="ffmpeg-notice" class="notice warn"></div>
      <div id="error" class="notice error"></div>
      <div id="success" class="notice success"></div>

      <div id="welcome" class="welcome">
        <h2>Mix your playlists in key</h2>
        <p>Pick a playlist on the left. Every song's key is worked out, then the playlist is put in the smoothest harmonic order using the Camelot wheel. Your original playlist is never changed.</p>
        <div class="steps">
          <div class="step"><div class="n">1</div><b>Calculate keys</b><span>From Comments/Grouping (Mixed In Key, Rekordbox), file tags, or the audio itself.</span></div>
          <div class="step"><div class="n">2</div><b>Shape the set</b><span>Drag a song anywhere to lock it in place. Everything below re-sorts around your choice.</span></div>
          <div class="step"><div class="n">3</div><b>Save to Music</b><span>Creates a new “… sorted” playlist from top to bottom.</span></div>
        </div>
      </div>

      <div id="loading" class="loading hidden">
        <div class="spinner"></div>
        <h3 id="loading-title">Reading playlist…</h3>
        <div class="bar indeterminate" id="bar"><div></div></div>
        <div class="cur" id="loading-cur"></div>
      </div>

      <div id="results" class="hidden">
        <div class="head">
          <div>
            <h2 id="pl-title"></h2>
            <div class="meta" id="pl-meta"></div>
          </div>
          <div class="toolbar">
            <div class="seg" id="flow" role="radiogroup" aria-label="Flow">
              <button data-flow="gradual_build" title="Prefer stepping up the wheel and rising tempo">Build energy</button>
              <button data-flow="balanced" title="Smoothest mixing in any direction">Smoothest</button>
            </div>
            <button id="undo" class="btn" title="Undo (⌘Z)"><svg class="i"><use href="#i-undo"/></svg></button>
            <button id="redo" class="btn" title="Redo (⇧⌘Z)"><svg class="i"><use href="#i-redo"/></svg></button>
            <button id="clear-manual" class="btn manual hidden" title="Unlock every manual song and re-sort everything"><svg class="i"><use href="#i-pin"/></svg>Clear manual</button>
            <button id="resort" class="btn" title="Re-sort everything except manual songs"><svg class="i"><use href="#i-sort"/></svg>Re-sort</button>
          </div>
        </div>

        <div class="stats">
          <div class="stat"><div class="t">Smooth mixes</div><div class="v" id="m-smooth" style="color:var(--green)">–</div><div class="meter"><div id="m-smooth-bar"></div></div></div>
          <div class="stat"><div class="t">Key clashes</div><div class="v" id="m-clash">–</div><div class="s">transitions that won't blend</div></div>
          <div class="stat"><div class="t">Friction vs. original</div><div class="v" id="m-improve" style="color:var(--accent)">–</div><div class="s" id="m-improve-s"></div></div>
          <div class="stat"><div class="t">Set length</div><div class="v" id="m-len">–</div><div class="s" id="m-len-s"></div></div>
        </div>

        <div id="unknown-notice" class="notice info"></div>

        <div class="grid">
          <div class="card">
            <div class="card-head">
              <div><h3>Running order</h3><div class="hint">Drag <svg class="i" style="width:12px;height:12px;vertical-align:-2px"><use href="#i-grip"/></svg> to place a song. It's marked manual and every song below it re-sorts.</div></div>
              <div class="filter"><svg class="i"><use href="#i-search"/></svg><input id="filter" type="search" placeholder="Filter songs  ( / )" autocomplete="off"></div>
            </div>
            <div id="tracks" class="tracks"></div>
          </div>

          <div class="side-panel">
            <div class="card">
              <div class="card-head"><h3>Keys in this set</h3></div>
              <div class="wheel-wrap"><svg id="wheel" width="220" height="220" viewBox="-100 -100 200 200"></svg></div>
              <div class="legend"><span><i style="background:#64748b"></i>Outer: major (B)</span><span><i style="background:#334155"></i>Inner: minor (A)</span></div>
            </div>
            <div class="card">
              <div class="card-head"><h3>Set journey</h3><span class="hint" id="journey-hint"></span></div>
              <div class="panel-body"><svg id="journey" preserveAspectRatio="none"></svg><div class="journey-cap" id="journey-cap"></div></div>
            </div>
            <div id="trim-card" class="card">
              <div class="card-head"><h3>Trim the set</h3><span class="hint" id="trim-status"></span></div>
              <div class="budget">
                <span>I'm willing to remove up to</span>
                <div class="stepper"><button id="budget-dec" aria-label="Fewer">−</button><input id="budget" type="number" min="0" max="20" value="3" aria-label="Maximum songs to remove"><button id="budget-inc" aria-label="More">+</button></div>
                <span>songs</span>
              </div>
              <div id="trim-body" class="trim-body"></div>
            </div>
            <div class="card">
              <div class="card-head"><h3>Removed</h3><button id="restore-all" class="btn sm hidden">Restore all</button></div>
              <div id="tray" class="tray"></div>
            </div>
          </div>
        </div>

        <div class="export">
          <div class="what" id="export-what"></div>
          <button id="export" class="btn primary"><svg class="i"><use href="#i-plus"/></svg>Create sorted playlist</button>
        </div>
      </div>
    </div>
  </main>
</div>

<div id="popover" class="popover hidden"></div>
<div id="toasts" class="toasts"></div>

<script>
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name) => `<svg class="i"><use href="#i-${name}"/></svg>`;
const KEY_COLORS = ['#0077b6','#0096c7','#00b4d8','#48cae4','#52b788','#74c69d','#ffd166','#f39c12','#e76f51','#e63946','#b5179e','#7209b7'];
const DARK_TEXT = new Set([3,4,5,6,7,8]);
const isMac = /Mac|iPhone|iPad/.test(navigator.platform);

const state = {
  playlists: [], playlistId: null, result: null, strategy: 'gradual_build',
  excluded: new Set(), manual: new Set(), busy: false, undo: [], redo: [], drag: null,
  budget: 3, plan: null, planSeq: 0,
};
try { const b = parseInt(localStorage.getItem('camelot.budget'), 10); if (b >= 0 && b <= 20) state.budget = b; } catch (e) {}

function pill(k) {
  if (!k) return '<span class="pill none" title="Key unknown">?</span>';
  const bg = KEY_COLORS[k.number - 1], fg = DARK_TEXT.has(k.number) ? '#000' : '#fff';
  return `<span class="pill" style="background:${bg};color:${fg}" title="${esc(k.standard_name)}">${esc(k.camelot)}</span>`;
}
function fmtTime(sec) {
  sec = Math.round(sec || 0);
  if (!sec) return '—';
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}
function fmtLong(sec) {
  const m = Math.round((sec || 0) / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}
function show(id, html) {
  const el = $(id);
  if (!html) { el.classList.remove('show'); el.innerHTML = ''; } else { el.innerHTML = html; el.classList.add('show'); }
}
function toast(msg, { action, onAction, error = false, ms = 5000 } = {}) {
  const el = document.createElement('div');
  el.className = 'toast' + (error ? ' err' : '');
  el.innerHTML = `<span>${msg}</span>` + (action ? `<button>${esc(action)}</button>` : '');
  if (action) el.querySelector('button').addEventListener('click', () => { el.remove(); onAction(); });
  $('toasts').appendChild(el);
  while ($('toasts').children.length > 3) $('toasts').firstElementChild.remove();
  setTimeout(() => el.remove(), ms);
}

async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) };
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new Error('Lost connection to the app. Is it still running in Terminal?'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function setBusy(busy) {
  state.busy = busy;
  $('busy-line').classList.toggle('hidden', !busy);
  document.querySelectorAll('#results button, #refresh').forEach(b => { b.disabled = busy; });
  document.body.style.cursor = busy ? 'progress' : '';
  if (!busy) updateControls();
}

function updateControls() {
  if (state.busy) return;
  $('undo').disabled = !state.undo.length;
  $('redo').disabled = !state.redo.length;
  $('export').disabled = !(state.result && state.result.sorted_songs.length);
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
        $('loading-title').textContent = `Calculating keys · ${p.done} of ${p.total}`;
      }
      if (p.current) $('loading-cur').textContent = p.current;
    } catch (e) {}
  }, 350);
}
function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = null; }

async function loadStatus() {
  try {
    const s = await api('/api/status');
    const demo = s.mode === 'demo';
    $('mode').className = 'mode ' + (demo ? 'demo' : 'ok');
    $('mode-text').textContent = demo ? 'Demo library · not connected to Music' : 'Connected to Music';
    show('ffmpeg-notice', s.ffmpeg ? '' : '<strong>ffmpeg not found.</strong> Keys can still be read from Comments/Grouping and file tags, but audio analysis is off. Install it with <code>brew install ffmpeg</code> and restart the app.');
  } catch (e) { show('error', esc(e.message)); }
}

async function loadPlaylists() {
  try {
    const data = await api('/api/playlists');
    state.playlists = data.playlists.filter(p => p.track_count > 0);
    renderPlaylists();
  } catch (e) {
    $('pl-list').innerHTML = '<div class="side-empty">Could not load playlists.</div>';
    show('error', esc(e.message));
  }
}

function renderPlaylists() {
  const q = $('pl-search').value.trim().toLowerCase();
  const lists = state.playlists.filter(p => !q || p.name.toLowerCase().includes(q));
  if (!state.playlists.length) { $('pl-list').innerHTML = '<div class="side-empty">No playlists with songs found in Music.</div>'; return; }
  if (!lists.length) { $('pl-list').innerHTML = `<div class="side-empty">No playlists match “${esc(q)}”.</div>`; return; }
  $('pl-list').innerHTML = lists.map(p => {
    let h = 0; for (const c of p.name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const c1 = KEY_COLORS[h % 12], c2 = KEY_COLORS[(h >> 4) % 12];
    const initials = p.name.replace(/[^\p{L}\p{N} ]/gu, '').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '♪';
    return `<button class="pl${p.id === state.playlistId ? ' active' : ''}" data-playlist="${esc(p.id)}">
      <span class="pl-art" style="background:linear-gradient(135deg, ${c1}, ${c2})">${esc(initials)}</span>
      <span class="pl-text"><div class="pl-name">${esc(p.name)}</div><div class="pl-meta">${p.track_count} songs${p.smart ? ' · Smart' : ''}</div></span>
    </button>`;
  }).join('');
}

function currentOrder() { return state.result ? state.result.sorted_songs.map(s => s.id) : []; }
function pinsFor(order) { return order.map((id, i) => [id, i]).filter(([id]) => state.manual.has(id)).map(([id, position]) => ({ id, position })); }
function snapshot() { return { result: state.result, excluded: [...state.excluded], manual: [...state.manual], strategy: state.strategy }; }
function restoreSnapshot(s) {
  const prev = currentOrder();
  state.result = s.result; state.excluded = new Set(s.excluded); state.manual = new Set(s.manual); state.strategy = s.strategy;
  render({ prevOrder: prev });
}

async function run(body, { label, placed, message, undoable = true, mutate } = {}) {
  if (state.busy || !state.playlistId) return;
  const before = snapshot();
  const prevOrder = currentOrder();
  if (mutate) mutate();
  show('error', ''); show('success', '');
  setBusy(true);
  try {
    const data = await api('/api/analyze', {
      playlist_id: state.playlistId, strategy: state.strategy, exclude_ids: [...state.excluded], ...body,
    });
    if (undoable && before.result) { state.undo.push(before); if (state.undo.length > 100) state.undo.shift(); state.redo = []; }
    state.result = data;
    state.manual = new Set(data.sorted_songs.filter(s => s.manual).map(s => s.id));
    render({ prevOrder, placed });
    if (message) toast(message, undoable && before.result ? { action: 'Undo', onAction: undo } : {});
  } catch (e) {
    state.excluded = new Set(before.excluded); state.manual = new Set(before.manual); state.strategy = before.strategy;
    if (state.result) { render({}); toast(esc(e.message), { error: true }); } else show('error', esc(e.message));
  } finally { setBusy(false); updateControls(); }
}

async function openPlaylist(id, { refresh = false } = {}) {
  if (state.busy) return;
  if (id !== state.playlistId) {
    state.playlistId = id; state.result = null; state.excluded.clear(); state.manual.clear(); state.undo = []; state.redo = [];
    $('filter').value = '';
  }
  renderPlaylists();
  const p = state.playlists.find(x => x.id === id);
  $('welcome').classList.add('hidden'); $('results').classList.add('hidden'); $('loading').classList.remove('hidden');
  $('loading-title').textContent = refresh ? 'Re-reading playlist from Music…' : `Opening “${p ? p.name : 'playlist'}”…`;
  $('loading-cur').textContent = ''; $('bar').classList.add('indeterminate'); $('bar').firstElementChild.style.width = '';
  show('error', ''); show('success', '');
  setBusy(true); startPolling();
  try {
    const data = await api('/api/analyze', {
      playlist_id: id, strategy: state.strategy, refresh, exclude_ids: [...state.excluded],
      manual: pinsFor(currentOrder()),
    });
    if (state.playlistId !== id) return;
    state.result = data;
    state.manual = new Set(data.sorted_songs.filter(s => s.manual).map(s => s.id));
    render({});
  } catch (e) {
    show('error', esc(e.message));
    $('welcome').classList.toggle('hidden', !!state.result);
    $('results').classList.toggle('hidden', !state.result);
  } finally {
    stopPolling(); setBusy(false); $('loading').classList.add('hidden'); updateControls();
  }
}

/* ---------- User actions ---------- */

function moveSong(id, toIndex, { fromTray = false } = {}) {
  const order = currentOrder().filter(x => x !== id);
  toIndex = Math.max(0, Math.min(toIndex, order.length));
  order.splice(toIndex, 0, id);
  const title = fromTray ? excludedTitle(id) : (songById(id) || {}).title;
  run({ keep_ids: order.slice(0, toIndex), manual: pinsFor(order).concat([{ id, position: toIndex }]) }, {
    placed: id,
    mutate: () => { state.manual.add(id); if (fromTray) state.excluded.delete(id); },
    message: `${fromTray ? 'Restored' : 'Placed'} <b>${esc(title || 'song')}</b> at #${toIndex + 1} · songs below re-sorted`,
  });
}

function removeSongs(ids) {
  const order = currentOrder();
  const first = Math.min(...ids.map(id => order.indexOf(id)).filter(i => i >= 0));
  const rest = order.filter(x => !ids.includes(x));
  const keep = rest.slice(0, Number.isFinite(first) ? first : 0);
  const name = ids.length === 1 ? `<b>${esc((songById(ids[0]) || {}).title)}</b>` : `${ids.length} songs`;
  run({ keep_ids: keep, manual: pinsFor(rest).filter(p => !ids.includes(p.id)) }, {
    mutate: () => ids.forEach(id => { state.excluded.add(id); state.manual.delete(id); }),
    message: `Removed ${name} · songs below re-sorted`,
  });
}

function restoreSongs(ids) {
  run({ order: currentOrder(), insert_ids: ids, manual: pinsFor(currentOrder()) }, {
    placed: ids.length === 1 ? ids[0] : undefined,
    mutate: () => ids.forEach(id => state.excluded.delete(id)),
    message: ids.length === 1 ? `Restored <b>${esc(excludedTitle(ids[0]))}</b> where it fits best` : `Restored ${ids.length} songs`,
  });
}

function pinInPlace(id) {
  if (state.busy) return;
  state.undo.push(snapshot()); state.redo = [];
  state.manual.add(id);
  state.result = { ...state.result, sorted_songs: state.result.sorted_songs.map(s => s.id === id ? { ...s, manual: true } : s) };
  render({});
  updateControls();
  toast(`Locked <b>${esc((songById(id) || {}).title)}</b> at #${currentOrder().indexOf(id) + 1}`, { action: 'Undo', onAction: undo });
}

function unpin(id) {
  const order = currentOrder();
  const idx = order.indexOf(id);
  run({ keep_ids: order.slice(0, idx), manual: pinsFor(order).filter(p => p.id !== id) }, {
    mutate: () => state.manual.delete(id),
    message: `Unlocked <b>${esc((songById(id) || {}).title)}</b> · re-sorted from #${idx + 1} down`,
  });
}

function resort({ clear = false } = {}) {
  run({ manual: clear ? [] : pinsFor(currentOrder()) }, {
    mutate: () => { if (clear) state.manual.clear(); },
    message: clear ? 'Cleared manual placements and re-sorted' : 'Re-sorted around your manual songs',
  });
}

function setFlow(flow) {
  if (flow === state.strategy || state.busy) return;
  run({ manual: pinsFor(currentOrder()) }, {
    mutate: () => { state.strategy = flow; },
    message: flow === 'balanced' ? 'Flow: smoothest mixing' : 'Flow: building energy',
  });
}

function undo() {
  if (state.busy || !state.undo.length) return;
  state.redo.push(snapshot());
  restoreSnapshot(state.undo.pop());
  updateControls();
}
function redo() {
  if (state.busy || !state.redo.length) return;
  state.undo.push(snapshot());
  restoreSnapshot(state.redo.pop());
  updateControls();
}
function songById(id) { return state.result && state.result.sorted_songs.find(s => s.id === id); }
function excludedTitle(id) { const s = state.result && state.result.excluded_songs.find(x => x.id === id); return s ? s.title : 'song'; }

/* ---------- Rendering ---------- */

function render({ prevOrder = [], placed } = {}) {
  const data = state.result;
  if (!data) return;
  $('welcome').classList.add('hidden'); $('loading').classList.add('hidden'); $('results').classList.remove('hidden');
  const s = data.summary, songs = data.sorted_songs;

  $('pl-title').textContent = data.playlist.name;
  const total = songs.reduce((a, x) => a + (x.duration_seconds || 0), 0);
  const manualCount = songs.filter(x => x.manual).length;
  $('pl-meta').innerHTML = `${songs.length} songs` + (total ? ` · ${fmtLong(total)}` : '') +
    (data.excluded_songs.length ? ` · ${data.excluded_songs.length} removed` : '') +
    (manualCount ? ` · <b>${manualCount} placed manually</b>` : '');
  document.querySelectorAll('#flow button').forEach(b => { b.classList.toggle('on', b.dataset.flow === state.strategy); b.setAttribute('aria-checked', b.dataset.flow === state.strategy); });
  $('clear-manual').classList.toggle('hidden', !manualCount);

  $('m-smooth').textContent = s.scored_transitions ? `${s.smooth_transitions}/${s.scored_transitions}` : '–';
  $('m-smooth-bar').style.width = s.scored_transitions ? `${100 * s.smooth_transitions / s.scored_transitions}%` : '0';
  $('m-clash').textContent = s.rough_transitions;
  $('m-clash').style.color = s.rough_transitions ? 'var(--red)' : 'var(--green)';
  $('m-improve').textContent = s.initial_penalty > 0 ? `−${Math.round(s.improvement_percent)}%` : '–';
  $('m-improve-s').textContent = `key & tempo friction ${s.initial_penalty} → ${s.final_penalty}`;
  $('m-len').textContent = total ? fmtLong(total) : `${songs.length} songs`;
  const bpms = songs.map(x => x.bpm).filter(b => b > 0);
  $('m-len-s').textContent = bpms.length ? `${Math.round(Math.min(...bpms))}–${Math.round(Math.max(...bpms))} BPM` : `${songs.length} songs`;

  const unknown = songs.filter(x => !x.resolved_key);
  show('unknown-notice', unknown.length ? `<strong>${unknown.length} song${unknown.length > 1 ? 's have' : ' has'} no known key</strong> and ${unknown.length > 1 ? 'go' : 'goes'} to the bottom unless you place ${unknown.length > 1 ? 'them' : 'it'}. ` +
    `Streaming and DRM-protected songs can't be analyzed. Add the key (e.g. <code>8A</code> or <code>Am</code>) to the song's Comments in Music, or analyze it with Mixed In Key / Rekordbox, then press ${icon('refresh')}.` : '');

  renderTracks({ prevOrder, placed });
  renderWheel(songs);
  renderJourney(songs, data.transitions);
  schedulePlan();
  renderTray(data.excluded_songs);

  $('export-what').innerHTML = `Creates <strong>“${esc(data.new_playlist_name)}”</strong> in Apple Music · ${songs.length} songs, top to bottom`;
  updateControls();
}

function renderTracks({ prevOrder = [], placed } = {}) {
  const data = state.result, songs = data.sorted_songs;
  const q = $('filter').value.trim().toLowerCase();
  const flagged = new Set(planFresh() ? state.plan.steps.map(x => x.song.id) : []);
  const prevIndex = new Map(prevOrder.map((id, i) => [id, i]));
  const SRC = { metadata: 'Comments', file_tag: 'File tag', audio_analysis: 'Audio', unknown: 'No key' };
  const parts = [];
  let shown = 0;
  songs.forEach((song, i) => {
    const visible = !q || `${song.title} ${song.artist} ${song.album} ${song.resolved_key ? song.resolved_key.camelot : ''}`.toLowerCase().includes(q);
    if (!visible) return;
    shown++;
    const cls = ['row'];
    if (song.manual) cls.push('manual');
    if (flagged.has(song.id)) cls.push('flagged');
    if (!song.resolved_key) cls.push('unknown');
    if (song.id === placed) cls.push('placed');
    else if (prevIndex.size && prevIndex.get(song.id) !== i) cls.push('flash');
    const src = song.key_source === 'audio_analysis' ? `Audio ${Math.round(song.confidence * 100)}%` : (SRC[song.key_source] || song.key_source);
    parts.push(`<div class="${cls.join(' ')}" draggable="true" data-id="${esc(song.id)}" data-index="${i}">
      <span class="handle" title="Drag to place this song">${icon('grip')}</span>
      <span class="pos">${i + 1}</span>
      ${pill(song.resolved_key)}
      <div class="song"><div class="title">${esc(song.title)}</div><div class="artist">${esc(song.artist)}${song.album ? ' · ' + esc(song.album) : ''}</div></div>
      <div class="tags">
        ${song.manual ? `<span class="tag manual" title="You placed this song. Sorting keeps it here.">${icon('pin')}Manual</span>` : ''}
        <span class="tag flag${flagged.has(song.id) ? '' : ' hidden'}" title="Suggested cut. See Trim the set">Suggested cut</span>
        <span class="tag src" title="${esc(song.key_note || 'Where the key came from')}">${esc(src)}</span>
      </div>
      <span class="bpm">${song.bpm > 0 ? Math.round(song.bpm) : '—'}</span>
      <span class="dur">${fmtTime(song.duration_seconds)}</span>
      <div class="actions">
        <button class="icon-btn pin${song.manual ? ' on' : ''}" data-act="pin" title="${song.manual ? 'Unlock: let sorting move this song' : 'Lock this song at this position'}">${icon('pin')}</button>
        <button class="icon-btn" data-act="move" title="Move to position…">${icon('move')}</button>
        <button class="icon-btn rm" data-act="remove" title="Remove from the sorted playlist">${icon('x')}</button>
      </div>
    </div>`);
    const t = data.transitions[i];
    if (t && !q) {
      const kind = t.is_unknown ? 'unknown' : (t.is_smooth ? 'smooth' : 'rough');
      parts.push(`<div class="conn ${kind}" title="Mix difficulty ${t.penalty}"><span class="d">${esc(t.description)}</span></div>`);
    }
  });
  if (!shown) parts.push(`<div class="no-match">No songs match “${esc(q)}”.</div>`);
  parts.push('<div class="drop-line" id="drop-line"><span></span></div>');
  $('tracks').innerHTML = parts.join('');
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
    [['B', 62, 97], ['A', 30, 62]].forEach(([letter, r0, r1]) => {
      const c = counts[`${n}${letter}`] || 0;
      const op = c ? 0.4 + 0.6 * c / max : 0.07;
      svg += `<path d="${seg(r0, r1, i)}" fill="${KEY_COLORS[i]}" fill-opacity="${op}" stroke="#151a28" stroke-width="1.5"><title>${n}${letter}: ${c} song${c === 1 ? '' : 's'}</title></path>`;
      const r = (r0 + r1) / 2;
      svg += `<text x="${(r * Math.cos(mid)).toFixed(1)}" y="${(r * Math.sin(mid)).toFixed(1)}" text-anchor="middle" dominant-baseline="central" font-size="${letter === 'B' ? 10 : 9}" font-weight="700" fill="${c ? '#fff' : '#3d4760'}" pointer-events="none">${n}${letter}</text>`;
    });
  }
  const known = songs.filter(s => s.resolved_key).length;
  svg += `<text x="0" y="-5" text-anchor="middle" font-size="16" font-weight="800" fill="#eef2f8">${known}</text><text x="0" y="11" text-anchor="middle" font-size="8" fill="#8e9ab3">keyed songs</text>`;
  $('wheel').innerHTML = svg;
}

function renderJourney(songs, transitions) {
  const el = $('journey');
  const W = el.clientWidth || 290, H = 130, pad = 10;
  el.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const useBpm = songs.filter(s => s.bpm > 0).length >= 2;
  const val = (s) => useBpm ? (s.bpm > 0 ? s.bpm : null) : (s.resolved_key ? s.resolved_key.number + (s.resolved_key.letter === 'B' ? 0.5 : 0) : null);
  const vals = songs.map(val).filter(v => v !== null);
  if (songs.length < 2 || vals.length < 2) { el.innerHTML = ''; $('journey-cap').textContent = 'Not enough songs with a known tempo or key to chart.'; $('journey-hint').textContent = ''; return; }
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi - lo < 4) { lo -= 2; hi += 2; }
  const x = (i) => pad + (W - 2 * pad) * (songs.length === 1 ? 0.5 : i / (songs.length - 1));
  const y = (v) => H - pad - (H - 2 * pad) * (v - lo) / (hi - lo);
  let svg = '';
  [0.25, 0.5, 0.75].forEach(f => { svg += `<line x1="0" x2="${W}" y1="${(pad + (H - 2 * pad) * f).toFixed(1)}" y2="${(pad + (H - 2 * pad) * f).toFixed(1)}" stroke="#262f48" stroke-dasharray="2 4"/>`; });
  for (let i = 0; i < songs.length - 1; i++) {
    const a = val(songs[i]), b = val(songs[i + 1]), t = transitions[i];
    if (a === null || b === null) continue;
    const rough = t && !t.is_unknown && !t.is_smooth;
    svg += `<line x1="${x(i).toFixed(1)}" y1="${y(a).toFixed(1)}" x2="${x(i + 1).toFixed(1)}" y2="${y(b).toFixed(1)}" stroke="${rough ? '#f87171' : '#5b6680'}" stroke-width="${rough ? 2 : 1.5}"${rough ? ' stroke-dasharray="4 3"' : ''}/>`;
  }
  songs.forEach((s, i) => {
    const v = val(s); if (v === null) return;
    const k = s.resolved_key, color = k ? KEY_COLORS[k.number - 1] : '#64748b';
    svg += `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${s.manual ? 5 : 4}" fill="${color}" stroke="${s.manual ? '#c084fc' : '#151a28'}" stroke-width="2"><title>#${i + 1} ${esc(s.title)} · ${k ? esc(k.camelot) : '?'}${s.bpm > 0 ? ' · ' + Math.round(s.bpm) + ' BPM' : ''}</title></circle>`;
  });
  el.innerHTML = svg;
  $('journey-hint').textContent = useBpm ? `${Math.round(Math.min(...vals))}–${Math.round(Math.max(...vals))} BPM` : 'by key';
  $('journey-cap').innerHTML = `${useBpm ? 'Tempo' : 'Wheel position'} from first to last song. Dots are colored by key; <span style="color:var(--red)">dashed red</span> lines are key clashes.`;
}

/* ---------- Trim the set (removal budget) ---------- */

let planTimer = null;
function schedulePlan(delay = 250) {
  clearTimeout(planTimer);
  if (state.plan && state.plan.forResult !== state.result) $('trim-body').classList.add('stale');
  planTimer = setTimeout(fetchPlan, delay);
}

async function fetchPlan() {
  const result = state.result;
  if (!result) return;
  const budget = state.budget;
  const order = result.sorted_songs.map(s => s.id);
  const seq = ++state.planSeq;
  $('trim-status').textContent = budget ? 'Finding the best cuts…' : '';
  try {
    const plan = await api('/api/removal_plan', {
      playlist_id: state.playlistId, strategy: state.strategy, exclude_ids: [...state.excluded],
      order, manual: pinsFor(order), max_remove: budget,
    });
    if (seq !== state.planSeq || result !== state.result) return;
    plan.forResult = result;
    state.plan = plan;
    renderPlan();
  } catch (e) {
    if (seq === state.planSeq) { $('trim-status').textContent = ''; $('trim-body').innerHTML = `<div class="headline" style="color:var(--red)">${esc(e.message)}</div>`; }
  }
}

function planFresh() { return state.plan && state.plan.forResult === state.result; }

function cmpCell(label, before, after, { fmt = (v) => v, lowerIsBetter = true, pct = false } = {}) {
  const diff = after - before;
  const better = lowerIsBetter ? diff < 0 : diff > 0;
  let d = 'no change', cls = 'flat';
  if (Math.abs(diff) > 1e-9) {
    cls = better ? 'up' : 'flat';
    d = pct && before ? `${diff < 0 ? '−' : '+'}${Math.round(100 * Math.abs(diff) / before)}%` : `${diff < 0 ? '−' : '+'}${fmt(Math.abs(diff))}`;
  }
  return `<div class="cmp"><div class="t">${label}</div><div class="v"><s>${fmt(before)}</s> → ${fmt(after)}</div><div class="d ${cls}">${d}</div></div>`;
}

function renderPlan() {
  const plan = state.plan;
  $('trim-status').textContent = '';
  $('trim-body').classList.remove('stale');
  markSuggestedCuts();
  if (!plan) { $('trim-body').innerHTML = ''; return; }
  const b = plan.baseline, a = plan.after, n = plan.steps.length;
  const smoothPct = (m) => m.scored ? Math.round(100 * m.smooth / m.scored) : 100;
  let html = `<div class="headline${n ? ' good' : ''}">${esc(plan.headline)}</div>`;
  if (n) {
    html += '<div class="compare">' +
      cmpCell('Key clashes', b.clashes, a.clashes) +
      cmpCell('Smooth mixes', smoothPct(b), smoothPct(a), { fmt: (v) => `${Math.round(v)}%`, lowerIsBetter: false }) +
      cmpCell('Friction', b.friction, a.friction, { fmt: (v) => (+v).toFixed(1), pct: true }) + '</div>';
  }
  if (plan.hint) {
    const want = Math.min(20, plan.hint_budget || 0);
    html += `<div class="hint-box"><span>${esc(plan.hint)}</span>${want > state.budget ? `<button class="btn sm" data-budget="${want}">Allow ${want}</button>` : ''}</div>`;
  }
  let prev = b;
  html += plan.steps.map((st, i) => {
    const m = st.metrics, bits = [];
    if (m.clashes < prev.clashes) bits.push(`fixes ${prev.clashes - m.clashes} clash${prev.clashes - m.clashes > 1 ? 'es' : ''}`);
    if (m.friction < prev.friction) bits.push(`friction −${(prev.friction - m.friction).toFixed(1)}`);
    const sameAsNext = plan.steps[i + 1] && plan.steps[i + 1].metrics.objective === m.objective;
    if (!sameAsNext) prev = m;
    const impact = sameAsNext ? 'removed together with the next song' : (bits.length ? bits.join(' · ') : 'smoother flow');
    return `<div class="sugg">
      <div class="who"><span class="n">${i + 1}</span>${pill(st.song.resolved_key)}<span class="name">${esc(st.song.title)} <span style="color:var(--dim);font-weight:400">· ${esc(st.song.artist)}</span></span></div>
      <div class="impact">${esc(impact)}</div>
      <div class="why">${esc(st.reason)}</div>
      <div class="btns"><button class="btn sm" data-remove="${esc(st.song.id)}">Remove</button><button class="btn sm" data-keep="${esc(st.song.id)}" title="Lock it where it is so it's never suggested">Keep it</button></div>
    </div>`;
  }).join('');
  if (n) html += `<button id="trim-apply" class="btn primary trim-apply">Remove ${n === 1 ? 'this song' : `these ${n} songs`}</button>`;
  $('trim-body').innerHTML = html;
  if (state.busy) $('trim-body').querySelectorAll('button').forEach(x => { x.disabled = true; });
}

function markSuggestedCuts() {
  const ids = new Set(planFresh() ? state.plan.steps.map(s => s.song.id) : []);
  document.querySelectorAll('#tracks .row').forEach(r => {
    const on = ids.has(r.dataset.id);
    r.classList.toggle('flagged', on);
    r.querySelector('.tag.flag').classList.toggle('hidden', !on);
  });
}

function applyPlan() {
  if (!planFresh() || !state.plan.steps.length) return;
  const plan = state.plan, ids = plan.steps.map(s => s.song.id);
  const finalOrder = plan.final_order_ids;
  const b = plan.baseline, a = plan.after;
  const effect = b.clashes !== a.clashes ? `clashes ${b.clashes} → ${a.clashes}` : `friction ${b.friction.toFixed(1)} → ${a.friction.toFixed(1)}`;
  run({ order: finalOrder, manual: pinsFor(finalOrder) }, {
    mutate: () => ids.forEach(id => { state.excluded.add(id); state.manual.delete(id); }),
    message: `Removed ${ids.length} song${ids.length > 1 ? 's' : ''} · ${effect}`,
  });
}

function setBudget(v) {
  v = Math.max(0, Math.min(20, parseInt(v, 10) || 0));
  if (v === state.budget && $('budget').value == v) return;
  state.budget = v;
  $('budget').value = v;
  try { localStorage.setItem('camelot.budget', String(v)); } catch (e) {}
  if (state.result) schedulePlan(350);
}

function renderTray(excluded) {
  $('restore-all').classList.toggle('hidden', excluded.length < 2);
  $('tray').innerHTML = excluded.length ? excluded.map(x => `
    <div class="tray-item" draggable="true" data-tray="${esc(x.id)}" title="Drag into the running order, or press Restore">
      ${pill(x.resolved_key)}<span class="t">${esc(x.title)} · ${esc(x.artist)}</span>
      <button class="btn sm" data-restore="${esc(x.id)}">Restore</button>
    </div>`).join('') : '<div class="tray-empty">Removed songs land here. Drag a song here to remove it, or drag one back into the list.</div>';
}

/* ---------- Move-to popover ---------- */

function openMovePopover(id, anchor) {
  const order = currentOrder(), idx = order.indexOf(id), n = order.length, song = songById(id);
  const pop = $('popover');
  pop.innerHTML = `<label>Move “${esc(song.title)}” to</label>
    <div class="r"><input id="move-to" type="number" min="1" max="${n}" value="${idx + 1}"><button class="btn sm primary" id="move-go">Move</button></div>
    <div class="q"><button class="btn sm" data-moveto="0">Top</button><button class="btn sm" data-moveto="${Math.floor((n - 1) / 2)}">Middle</button><button class="btn sm" data-moveto="${n - 1}">Bottom</button></div>
    <div class="note">The song is locked there; songs above stay put and songs below re-sort.</div>`;
  pop.classList.remove('hidden');
  const r = anchor.getBoundingClientRect();
  const left = Math.min(window.innerWidth - pop.offsetWidth - 12, r.right - pop.offsetWidth);
  const top = r.bottom + 6 + pop.offsetHeight > window.innerHeight ? r.top - pop.offsetHeight - 6 : r.bottom + 6;
  pop.style.left = `${Math.max(12, left)}px`; pop.style.top = `${Math.max(12, top)}px`;
  pop.dataset.id = id;
  const input = $('move-to'); input.focus(); input.select();
  const go = (to) => { closePopover(); if (to !== idx || !state.manual.has(id)) moveSong(id, to); };
  $('move-go').addEventListener('click', () => go(Math.max(0, Math.min(n - 1, (parseInt(input.value, 10) || 1) - 1))));
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('move-go').click(); });
  pop.querySelectorAll('[data-moveto]').forEach(b => b.addEventListener('click', () => go(parseInt(b.dataset.moveto, 10))));
}
function closePopover() { $('popover').classList.add('hidden'); }

/* ---------- Drag and drop ---------- */

function dropIndexAt(clientY) {
  const rows = [...$('tracks').querySelectorAll('.row')];
  for (const r of rows) {
    const b = r.getBoundingClientRect();
    if (clientY < b.top + b.height / 2) return { index: +r.dataset.index, el: r, before: true };
  }
  const last = rows[rows.length - 1];
  return last ? { index: +last.dataset.index + 1, el: last, before: false } : { index: 0, el: null, before: true };
}

function finalIndex(dropIndex) {
  const d = state.drag;
  return d && d.from >= 0 && d.from < dropIndex ? dropIndex - 1 : dropIndex;
}

$('tracks').addEventListener('dragstart', (e) => {
  const row = e.target.closest('.row');
  if (!row || state.busy) { e.preventDefault(); return; }
  state.drag = { id: row.dataset.id, from: +row.dataset.index };
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', row.dataset.id);
  closePopover();
  setTimeout(() => row.classList.add('dragging'), 0);
});
$('tray').addEventListener('dragstart', (e) => {
  const item = e.target.closest('[data-tray]');
  if (!item || state.busy) { e.preventDefault(); return; }
  state.drag = { id: item.dataset.tray, from: -1 };
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', item.dataset.tray);
});
document.addEventListener('dragend', () => {
  state.drag = null;
  document.querySelectorAll('.row.dragging').forEach(r => r.classList.remove('dragging'));
  const line = $('drop-line'); if (line) line.style.display = 'none';
  $('tray').classList.remove('over');
});

$('tracks').addEventListener('dragover', (e) => {
  if (!state.drag) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const { index, el, before } = dropIndexAt(e.clientY);
  const line = $('drop-line');
  if (!el) { line.style.display = 'none'; return; }
  const host = $('tracks').getBoundingClientRect(), b = el.getBoundingClientRect();
  const yPos = before ? b.top - host.top - 2 : b.bottom - host.top + 1;
  line.style.display = 'block';
  line.style.top = `${yPos}px`;
  line.querySelector('span').textContent = `Place at #${finalIndex(index) + 1}`;
  if (e.clientY < 70) window.scrollBy(0, -14); else if (e.clientY > window.innerHeight - 110) window.scrollBy(0, 14);
});
$('tracks').addEventListener('dragleave', (e) => {
  if (!$('tracks').contains(e.relatedTarget)) { const line = $('drop-line'); if (line) line.style.display = 'none'; }
});
$('tracks').addEventListener('drop', (e) => {
  if (!state.drag) return;
  e.preventDefault();
  const d = state.drag, to = finalIndex(dropIndexAt(e.clientY).index);
  state.drag = null;
  $('drop-line').style.display = 'none';
  if (d.from === to && state.manual.has(d.id)) return;
  moveSong(d.id, to, { fromTray: d.from < 0 });
});

$('tray').addEventListener('dragover', (e) => { if (state.drag && state.drag.from >= 0) { e.preventDefault(); $('tray').classList.add('over'); } });
$('tray').addEventListener('dragleave', (e) => { if (!$('tray').contains(e.relatedTarget)) $('tray').classList.remove('over'); });
$('tray').addEventListener('drop', (e) => {
  $('tray').classList.remove('over');
  if (!state.drag || state.drag.from < 0) return;
  e.preventDefault();
  const id = state.drag.id; state.drag = null;
  removeSongs([id]);
});

/* ---------- Export ---------- */

async function exportPlaylist() {
  if (!state.result || state.busy) return;
  show('error', ''); show('success', '');
  setBusy(true);
  try {
    const r = await api('/api/export', { playlist_id: state.result.playlist.id, ordered_ids: currentOrder() });
    let msg = `Created <strong>“${esc(r.name)}”</strong> in Apple Music with ${r.added} songs.`;
    if (r.replaced) msg += ' The previous sorted copy was replaced.';
    if (r.added < r.requested) msg += ` ${r.requested - r.added} song(s) could not be added (they may no longer be available).`;
    show('success', msg);
    toast(`Saved “${esc(r.name)}” to Music`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    loadPlaylists();
  } catch (e) {
    show('error', esc(e.message));
  } finally { setBusy(false); updateControls(); }
}

/* ---------- Wiring ---------- */

document.addEventListener('click', (e) => {
  const pl = e.target.closest('[data-playlist]');
  if (pl) return openPlaylist(pl.dataset.playlist);
  if (!e.target.closest('#popover') && !e.target.closest('[data-act="move"]')) closePopover();
  if (state.busy) return;
  const act = e.target.closest('[data-act]');
  if (act) {
    const id = act.closest('.row').dataset.id;
    if (act.dataset.act === 'remove') removeSongs([id]);
    else if (act.dataset.act === 'pin') state.manual.has(id) ? unpin(id) : pinInPlace(id);
    else if (act.dataset.act === 'move') { if (!$('popover').classList.contains('hidden') && $('popover').dataset.id === id) closePopover(); else openMovePopover(id, act); }
    return;
  }
  const rm = e.target.closest('[data-remove]'), rs = e.target.closest('[data-restore]'), keep = e.target.closest('[data-keep]');
  if (rm) removeSongs([rm.dataset.remove]);
  if (rs) restoreSongs([rs.dataset.restore]);
  if (keep) pinInPlace(keep.dataset.keep);
  const budgetBtn = e.target.closest('[data-budget]');
  if (budgetBtn) setBudget(budgetBtn.dataset.budget);
  if (e.target.closest('#trim-apply')) applyPlan();
});
document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  if (e.key === 'Escape') { closePopover(); if (typing) document.activeElement.blur(); return; }
  if (typing) return;
  const mod = isMac ? e.metaKey : e.ctrlKey;
  if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); }
  else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); }
  else if (e.key === '/' && state.result) { e.preventDefault(); $('filter').focus(); }
});
$('flow').addEventListener('click', (e) => { const b = e.target.closest('[data-flow]'); if (b) setFlow(b.dataset.flow); });
$('resort').addEventListener('click', () => resort());
$('clear-manual').addEventListener('click', () => resort({ clear: true }));
$('undo').addEventListener('click', undo);
$('redo').addEventListener('click', redo);
$('budget').addEventListener('input', () => setBudget($('budget').value));
$('budget-dec').addEventListener('click', () => setBudget(state.budget - 1));
$('budget-inc').addEventListener('click', () => setBudget(state.budget + 1));
$('restore-all').addEventListener('click', () => { if (state.result) restoreSongs(state.result.excluded_songs.map(x => x.id)); });
$('export').addEventListener('click', exportPlaylist);
$('filter').addEventListener('input', () => { if (state.result) renderTracks({}); });
$('pl-search').addEventListener('input', renderPlaylists);
$('refresh').addEventListener('click', async () => { await loadPlaylists(); if (state.playlistId) openPlaylist(state.playlistId, { refresh: true }); });
window.addEventListener('resize', () => { if (state.result) renderJourney(state.result.sorted_songs, state.result.transitions); });
$('undo').title = isMac ? 'Undo (⌘Z)' : 'Undo (Ctrl+Z)';
$('redo').title = isMac ? 'Redo (⇧⌘Z)' : 'Redo (Ctrl+Y)';

$('budget').value = state.budget;
loadStatus();
loadPlaylists();
updateControls();
</script>
</body>
</html>
"""
