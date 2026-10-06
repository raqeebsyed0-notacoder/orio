/**
 * ORIO Operations - Hermes Desktop demo plugin (Innovex 90-Day AI Operations Pilot).
 *
 * Door: unified package desktop half. Installed at
 *   $HERMES_HOME/plugins/euphoria-orio-operations/desktop/plugin.js
 * and mirrored by the shell into desktop-plugins/ (opt-in toggle).
 *
 * Data: NONE is hardcoded here. Every view reads the demo SQLite database
 * through the Python backend (ctx.rest -> /api/plugins/euphoria-orio-operations).
 * Approvals POST back and mutate DEMO STATE ONLY. No external actions exist.
 *
 * UI: native Hermes SDK components (Button, Dialog, SearchField,
 * SegmentedControl, EmptyState, ErrorState, ScrollArea, Separator) plus a
 * small theme-var stylesheet. No hardcoded colors, no emojis.
 * Plain ESM, loaded uncompiled - jsx() calls only.
 */
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  PALETTE_AREA,
  ROUTES_AREA,
  ScrollArea,
  SearchField,
  SegmentedControl,
  Separator,
  SIDEBAR_NAV_AREA,
  atom,
  host,
  useQuery,
  useQueryClient,
  useValue
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useEffect, useMemo, useState } from 'react'

const ID = 'euphoria-orio-operations'
const PAGE = '/orio-operations'
const ARCH_HTML =
  'D:/12_projects/Innovex (ajeez)/Innovex_Ajeez_90_Day_AI_Operations_Architecture.html'

let restFn = null
let storageGet = (k, fb) => fb
let storageSet = () => {}
let revealPath = async () => false
let refreshAll = () => false
let stylesDone = false

const api = (path, opts) => {
  if (!restFn) return Promise.reject(new Error('backend not bound'))
  return restFn(path, opts)
}

const QK = (...parts) => [ID, ...parts]
const errText = e => String((e && (e.message || e.data || e)) || e)
const textOf = v => String(v === null || v === undefined ? '' : v)

/* Styling: one injected stylesheet, theme vars only, 8px radius lock,
 * single accent (critical tile + primary approve), mono numerals. */
function ensureStyles() {
  if (stylesDone || typeof document === 'undefined') return
  stylesDone = true
  const css = `
  .${ID}-page { display:flex; flex-direction:column; height:100%; min-height:0; font-size:13px; line-height:1.45; }
  .${ID}-page button:focus-visible { outline:2px solid var(--ui-accent); outline-offset:1px; }
  .${ID}-topbar { display:flex; align-items:center; gap:.6rem; padding:.55rem 1rem; border-bottom:1px solid var(--ui-stroke-secondary); flex-wrap:wrap; }
  .${ID}-title { font-size:14px; font-weight:700; }
  .${ID}-demobadge { font-size:11px; font-weight:700; padding:1px 8px; border-radius:20px; border:1px solid var(--ui-stroke-secondary); color:var(--ui-text-secondary); white-space:nowrap; }
  .${ID}-body { display:flex; flex:1; min-height:0; }
  .${ID}-side { width:186px; flex-shrink:0; border-right:1px solid var(--ui-stroke-secondary); padding:.6rem .5rem; display:flex; flex-direction:column; gap:2px; overflow-y:auto; }
  .${ID}-navbtn { display:flex; align-items:center; justify-content:space-between; gap:.4rem; text-align:left; padding:.4rem .6rem; border-radius:8px; border:0; background:transparent; color:var(--ui-text-secondary); cursor:pointer; font-size:13px; font-family:inherit; width:100%; }
  .${ID}-navbtn:hover { background:var(--chrome-action-hover); color:var(--foreground); }
  .${ID}-navbtn[data-active="1"] { background:var(--chrome-action-hover); color:var(--foreground); font-weight:600; }
  .${ID}-navbtn:focus-visible { outline:2px solid var(--ui-accent); outline-offset:1px; }
  .${ID}-count { font-size:11px; font-weight:700; min-width:20px; text-align:center; padding:0 6px; border-radius:20px; border:1px solid var(--ui-stroke-secondary); color:var(--ui-text-secondary); font-variant-numeric:tabular-nums; }
  .${ID}-count[data-hot="1"] { border-color:var(--ui-accent); color:var(--ui-accent); }
  .${ID}-main { flex:1; min-width:0; display:flex; flex-direction:column; }
  .${ID}-content { padding:.8rem 1rem 2rem; max-width:1560px; }
  .${ID}-h { font-size:15px; font-weight:700; margin:0 0 .3rem; }
  .${ID}-sub { font-size:12px; color:var(--ui-text-tertiary); margin-bottom:.7rem; }
  .${ID}-secttl { font-size:13px; font-weight:700; margin:.1rem 0 .45rem; }
  .${ID}-tiles { display:grid; grid-template-columns:repeat(6, minmax(110px, 1fr)); gap:.5rem; margin-bottom:.8rem; }
  .${ID}-tile { border:1px solid var(--ui-stroke-secondary); border-radius:8px; padding:.5rem .65rem; min-width:0; background:var(--ui-bg-card); }
  .${ID}-tile[data-hot="1"] { border-top:2px solid var(--ui-accent); }
  .${ID}-num { font-size:22px; font-weight:700; font-variant-numeric:tabular-nums; }
  .${ID}-lbl { font-size:11px; color:var(--ui-text-tertiary); }
  .${ID}-toolbar { display:flex; gap:.5rem; margin-bottom:.6rem; align-items:center; flex-wrap:wrap; }
  .${ID}-resultcount { font-size:12px; color:var(--ui-text-tertiary); margin-left:auto; white-space:nowrap; }
  .${ID}-tablewrap { border:1px solid var(--ui-stroke-secondary); border-radius:8px; overflow:auto; background:var(--ui-bg-card); }
  .${ID}-table { width:100%; min-width:880px; border-collapse:separate; border-spacing:0; font-size:12.5px; }
  .${ID}-table thead th { text-align:left; padding:.5rem .6rem; font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--ui-text-secondary); border-bottom:2px solid var(--ui-stroke-secondary); white-space:nowrap; background:var(--ui-bg-elevated); position:sticky; top:0; z-index:2; }
  .${ID}-table tbody td { padding:.5rem .6rem; border-bottom:1px solid var(--ui-stroke-tertiary); vertical-align:top; }
  .${ID}-table tbody tr:last-child td { border-bottom:0; }
  .${ID}-table tbody tr:hover td { background:var(--chrome-action-hover); }
  .${ID}-table tbody tr[data-hot="1"] td:first-child { box-shadow:inset 2px 0 0 var(--ui-accent); }
  .${ID}-mono { white-space:nowrap; font-variant-numeric:tabular-nums; font-family:ui-monospace, SFMono-Regular, Consolas, monospace; font-size:12px; }
  .${ID}-pill { display:inline-block; padding:1px 8px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; text-transform:uppercase; letter-spacing:.02em; border:1px solid var(--ui-stroke-secondary); color:var(--ui-text-secondary); }
  .${ID}-pill[data-hot="1"] { border-color:var(--ui-accent); color:var(--ui-accent); }
  .${ID}-card { border:1px solid var(--ui-stroke-secondary); border-radius:8px; padding:.7rem .8rem; margin-top:.6rem; background:var(--ui-bg-card); }
  .${ID}-card[data-hot="1"] { border-left:2px solid var(--ui-accent); }
  .${ID}-rowline { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }
  .${ID}-kv { margin:.25rem 0; }
  .${ID}-kv[data-missing="1"] { color:var(--ui-accent); font-weight:600; }
  .${ID}-actions { margin-top:.5rem; display:flex; gap:.4rem; align-items:center; flex-wrap:wrap; }
  .${ID}-confirm { display:inline-flex; gap:.35rem; align-items:center; flex-wrap:wrap; border:1px solid var(--ui-stroke-secondary); border-radius:8px; padding:.35rem .45rem; background:var(--ui-bg-elevated); }
  .${ID}-pager { margin-top:.6rem; display:flex; gap:.5rem; align-items:center; }
  .${ID}-center { display:grid; place-items:center; padding:2.5rem 1rem; }
  .${ID}-pickerrow { display:flex; gap:.35rem; overflow-x:auto; padding-bottom:.25rem; max-width:100%; }
  .${ID}-pickerrow .${ID}-navbtn { width:auto; flex-shrink:0; white-space:nowrap; border:1px solid var(--ui-stroke-secondary); }
  .${ID}-pickerrow .${ID}-navbtn[data-active="1"] { border-color:var(--ui-accent); color:var(--ui-accent); }
  .${ID}-tl { margin:.6rem 0 0; padding:0; list-style:none; }
  .${ID}-tl li { position:relative; padding:0 0 1rem 1.4rem; border-left:1px solid var(--ui-stroke-secondary); margin-left:.4rem; }
  .${ID}-tl li:last-child { border-left-color:transparent; padding-bottom:0; }
  .${ID}-tl li::before { content:""; position:absolute; left:-4px; top:4px; width:7px; height:7px; border-radius:50%; background:var(--ui-bg-editor); border:1px solid var(--ui-text-tertiary); }
  .${ID}-tl li[data-key="1"]::before { border-color:var(--ui-accent); background:var(--ui-accent); }
  .${ID}-ev { border-left:2px solid var(--ui-stroke-secondary); padding:.25rem 0 .25rem .65rem; margin:.45rem 0; font-size:12.5px; }
  .${ID}-pre { white-space:pre-wrap; font-size:12px; font-family:ui-monospace, SFMono-Regular, Consolas, monospace; }
  .${ID}-todaygrid { display:grid; grid-template-columns:minmax(0, 1fr) 300px; gap:.8rem; align-items:start; }
  .${ID}-todaymain { min-width:0; }
  .${ID}-rail { display:flex; flex-direction:column; gap:.6rem; position:sticky; top:.6rem; }
  .${ID}-panel { border:1px solid var(--ui-stroke-secondary); border-radius:8px; padding:.7rem .8rem; background:var(--ui-bg-card); }
  .${ID}-panelttl { font-size:12px; font-weight:700; margin-bottom:.5rem; }
  .${ID}-donutrow { display:flex; gap:.7rem; align-items:center; }
  .${ID}-donutrow svg { flex-shrink:0; }
  .${ID}-legend { display:flex; flex-direction:column; gap:.2rem; flex:1; min-width:0; }
  .${ID}-legrow { display:flex; align-items:center; gap:.45rem; width:100%; text-align:left; background:transparent; border:0; border-radius:6px; padding:.2rem .3rem; color:var(--ui-text-secondary); cursor:pointer; font-size:12px; font-family:inherit; }
  .${ID}-legrow:hover { background:var(--chrome-action-hover); color:var(--foreground); }
  .${ID}-legrow[data-active="1"] { color:var(--ui-accent); font-weight:700; }
  .${ID}-legline { display:flex; align-items:center; justify-content:space-between; gap:.45rem; padding:.2rem .3rem; font-size:12px; color:var(--ui-text-secondary); }
  .${ID}-swatch { width:10px; height:10px; border-radius:3px; flex-shrink:0; }
  .${ID}-stagerow { display:block; width:100%; text-align:left; background:transparent; border:0; border-radius:6px; padding:.25rem .3rem; cursor:pointer; color:var(--ui-text-secondary); font-size:12px; font-family:inherit; }
  .${ID}-stagerow:hover { background:var(--chrome-action-hover); color:var(--foreground); }
  .${ID}-stagerowline { display:flex; justify-content:space-between; gap:.5rem; }
  .${ID}-bar { display:block; height:6px; border-radius:4px; background:var(--chrome-action-hover); margin-top:.25rem; overflow:hidden; }
  .${ID}-bar > span { display:block; height:100%; background:var(--ui-accent); border-radius:4px; }
  @media (max-width:1100px) {
    .${ID}-todaygrid { grid-template-columns:minmax(0, 1fr); }
    .${ID}-rail { position:static; display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); }
  }
  @media (max-width:1150px) { .${ID}-tiles { grid-template-columns:repeat(3, 1fr); } }
  @media (max-width:900px) { .${ID}-content { padding:.7rem .7rem 2rem; } }
  @media (max-width:720px) {
    .${ID}-body { flex-direction:column; }
    .${ID}-side { width:auto; flex-direction:row; border-right:0; border-bottom:1px solid var(--ui-stroke-secondary); overflow-x:auto; overflow-y:hidden; }
    .${ID}-navbtn { width:auto; flex-shrink:0; white-space:nowrap; }
    .${ID}-tiles { grid-template-columns:repeat(2, 1fr); }
  }
  @media (prefers-reduced-motion: reduce) { .${ID}-navbtn, .${ID}-table tbody tr td { transition:none; } }
  .${ID}-todaymain { min-width:0; }
  .${ID}-legline > *, .${ID}-stagerowline > *, .${ID}-legrow > *, .${ID}-rowline > * { min-width:0; }
  .${ID}-legline { gap:.5rem; }
  .${ID}-legline > span:last-child { text-align:right; overflow-wrap:anywhere; white-space:normal; }
  .${ID}-stagerowline > span:first-child { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .${ID}-legrow > span:nth-child(2) { overflow-wrap:anywhere; }
  .${ID}-rowline > * { overflow-wrap:anywhere; }
  .${ID}-stagerow[data-active="1"] { color:var(--ui-accent); font-weight:700; }
  .${ID}-rail { position:static; align-self:start; }
  .${ID}-panel { overflow:hidden; }
  .${ID}-stagerowline { gap:.5rem; }
  .${ID}-stagerowline > span:last-child { flex-shrink:0; }
  `
  const el = document.createElement('style')
  el.setAttribute('data-plugin', ID)
  el.textContent = css
  document.head.appendChild(el)
}

const VIEWS = [
  { id: 'today', label: 'Today' },
  { id: 'actions', label: 'Action Queue' },
  { id: 'rigs', label: 'Rigs & Wells' },
  { id: 'lifecycle', label: 'ORIO Lifecycle' },
  { id: 'exceptions', label: 'Exceptions' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'history', label: 'History' },
  { id: 'expansion', label: 'Expansion' }
]

const $view = atom(storageGet('view', 'today'))
const hotState = raw => {
  const s = String(raw).toUpperCase()
  return (s === 'CONFLICT' || s === 'BLOCKED' || s === 'INCORRECT' ||
    s === 'CRITICAL' || s === 'HIGH' || s === 'OPEN' ? '1' : '0')
}
const isMissing = v => String(v || '').indexOf('MISSING') >= 0

function useApi(path, opts) {
  return useQuery({ queryKey: QK(path, JSON.stringify(opts || {})), queryFn: () => api(path, opts), retry: 1, staleTime: 15000 })
}

function Center({ children }) {
  return jsx('div', { className: `${ID}-center`, children })
}

function LoadGate({ q, empty, children }) {
  if (q.isLoading) return jsx(Center, { children: jsx(GlyphSpinner, {}) })
  if (q.isError) {
    return jsx(Center, {
      children: jsxs('div', {
        children: [
          jsx(ErrorState, { title: 'Could not load', description: errText(q.error) }),
          jsx('div', {
            style: { marginTop: '.6rem', textAlign: 'center' },
            children: jsx(Button, { size: 'xs', onClick: () => q.refetch(), children: 'Retry' })
          })
        ]
      })
    })
  }
  if (empty) return jsx(Center, { children: jsx(EmptyState, { title: empty.title, description: empty.desc }) })
  return children
}

function Pill({ status }) {
  return jsx('span', { className: `${ID}-pill`, 'data-hot': hotState(status), children: status })
}

function searchVal(v) {
  return typeof v === 'string' ? v : (v && v.target ? v.target.value : '')
}

function DecisionButtons({ action, onDone }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(null)
  const [note, setNote] = useState('')
  const send = (decision, noteText) => {
    setBusy(true)
    api('/actions/' + action.id + '/decision', { method: 'POST', body: { decision, note: noteText || '' } })
      .then(r => {
        host.notify({ kind: 'info', message: 'Recorded: ' + action.id + ' -> ' + r.state + ' (demo only).' })
        setConfirm(null)
        setNote('')
        qc.invalidateQueries({ queryKey: [ID] })
        if (onDone) onDone()
      })
      .catch(e => host.notify({ kind: 'error', message: 'Decision failed: ' + errText(e) }))
      .finally(() => setBusy(false))
  }
  const done = action.state === 'approved' || action.state === 'rejected' || action.state === 'incorrect'
  const dis = busy || done
  if (confirm) {
    return jsxs('span', {
      className: `${ID}-confirm`,
      children: [
        jsx(SearchField, {
          value: note,
          onChange: v => setNote(searchVal(v)),
          placeholder: 'Note for the demo log (optional)...'
        }),
        jsx(Button, { size: 'xs', disabled: busy, onClick: () => send(confirm, note), children: busy ? 'Saving...' : 'Confirm ' + confirm }),
        jsx(Button, { size: 'xs', variant: 'ghost', disabled: busy, onClick: () => { setConfirm(null); setNote('') }, children: 'Cancel' })
      ]
    })
  }
  return jsxs('span', {
    style: { display: 'inline-flex', gap: '.35rem', flexWrap: 'wrap' },
    children: [
      action.state === 'blocked'
        ? jsx(Button, { size: 'xs', variant: 'ghost', disabled: true, title: 'Blocked: identifiers missing', children: 'Approve (blocked)' })
        : jsx(Button, { size: 'xs', disabled: dis, onClick: () => send('approve', ''), children: 'Approve' }),
      jsx(Button, { size: 'xs', variant: 'ghost', disabled: dis, onClick: () => setConfirm('reject'), children: 'Reject' }),
      jsx(Button, { size: 'xs', variant: 'ghost', disabled: dis, onClick: () => setConfirm('incorrect'), children: 'Mark Incorrect' })
    ]
  })
}

/* Shared table head: thead with sticky elevated band, scope cols. */
function THead({ cols }) {
  return jsx('thead', {
    children: jsx('tr', {
      children: cols.map(h => jsx('th', { scope: 'col', children: h, key: h }))
    })
  })
}

/* Snapshot rail: live charts drawn from the same Today payload. No new
 * backend, no libraries, theme vars only. Donut segments and legend rows
 * filter the table; stage bars drop the stage into search. */
function Donut({ parts, label }) {
  const total = parts.reduce((s, p) => s + p.value, 0)
  let acc = 0
  const R = 15.9155
  return jsx('div', {
    className: `${ID}-donutrow`,
    children: [
      jsxs('svg', {
        viewBox: '0 0 42 42', width: 92, height: 92, role: 'img', 'aria-label': label + ', total ' + total,
        children: [
          jsx('circle', { cx: 21, cy: 21, r: R, fill: 'none', stroke: 'var(--ui-stroke-secondary)', strokeWidth: 6 }),
          total > 0 ? parts.map(p => {
            const len = (p.value / total) * 100
            const off = 25 - acc
            acc += len
            if (!p.value) return null
            const w = Math.max(len - 0.8, 0.5)
            return jsx('circle', {
              key: p.id, cx: 21, cy: 21, r: R, fill: 'none',
              stroke: 'var(--ui-accent)', strokeOpacity: p.opacity,
              strokeWidth: p.active ? 8 : 6, pathLength: 100,
              strokeDasharray: w + ' ' + (100 - w), strokeDashoffset: off,
              style: { cursor: 'pointer' }, onClick: p.onPick,
              children: jsx('title', { children: p.label + ': ' + p.value + '. Activate to filter.' })
            })
          }) : null,
          jsx('text', { x: 21, y: 21, textAnchor: 'middle', dominantBaseline: 'central', style: { fontSize: '9px', fontWeight: 700, fill: 'var(--ui-text-primary)' }, children: String(total) })
        ]
      }),
      jsx('div', {
        className: `${ID}-legend`,
        children: parts.map(p => jsx('button', {
          key: p.id, className: `${ID}-legrow`, 'data-active': p.active ? '1' : '0',
          onClick: p.onPick, title: 'Filter table: ' + p.label,
          children: [
            jsx('span', { className: `${ID}-swatch`, style: { background: 'var(--ui-accent)', opacity: p.opacity } }),
            jsx('span', { style: { flex: 1 }, children: p.label }),
            jsx('span', { className: `${ID}-mono`, children: String(p.value) })
          ]
        }))
      })
    ]
  })
}

function SnapshotRail({ items, fPri, onPri, onStage }) {
  const pri = [
    { id: 'critical', label: 'Critical', opacity: 1 },
    { id: 'high', label: 'High', opacity: 0.55 },
    { id: 'medium', label: 'Medium', opacity: 0.3 }
  ].map(g => ({
    id: g.id, label: g.label, opacity: g.opacity,
    value: items.filter(i => i.priority === g.id).length,
    active: fPri === g.id,
    onPick: () => onPri(fPri === g.id ? 'all' : g.id)
  }))
  const stageMap = {}
  items.forEach(i => { stageMap[i.stage] = (stageMap[i.stage] || 0) + 1 })
  const stages = Object.keys(stageMap).map(s => ({ stage: s, count: stageMap[s] })).sort((a, b) => b.count - a.count)
  const max = Math.max(1, ...stages.map(s => s.count))
  const approvals = ['Awaiting Ajeez', 'Blocked', 'Monitoring'].map(a => ({
    label: a, value: items.filter(i => i.approval === a).length
  }))
  return jsx('aside', {
    className: `${ID}-rail`,
    'aria-label': 'Morning snapshot',
    children: [
      jsx('div', {
        className: `${ID}-panel`, key: 'pri',
        children: [
          jsx('div', { className: `${ID}-panelttl`, children: 'Priority mix, tap to filter' }),
          jsx(Donut, { parts: pri, label: 'Items by priority' })
        ]
      }),
      jsx('div', {
        className: `${ID}-panel`, key: 'stage',
        children: [
          jsx('div', { className: `${ID}-panelttl`, children: 'Lifecycle mix, tap to search' }),
          jsx('div', {
            children: stages.map(s => jsx('button', {
              key: s.stage, className: `${ID}-stagerow`, onClick: () => onStage(s.stage), title: 'Search table: ' + s.stage,
              children: [
                jsxs('span', {
                  className: `${ID}-stagerowline`,
                  children: [
                    jsx('span', { children: s.stage + ' (' + s.count + ')' }),
                    jsx('span', { className: `${ID}-mono`, children: String(s.count) })
                  ]
                }),
                jsx('span', { className: `${ID}-bar`, children: jsx('span', { style: { width: (s.count / max * 100) + '%' } }) })
              ]
            }))
          })
        ]
      }),
      jsx('div', {
        className: `${ID}-panel`, key: 'appr',
        children: [
          jsx('div', { className: `${ID}-panelttl`, children: 'Approvals' }),
          jsx('div', {
            children: approvals.map(a => jsxs('div', {
              key: a.label, className: `${ID}-legline`,
              children: [
                jsx('span', { children: a.label }),
                jsx('span', { className: `${ID}-mono`, children: String(a.value) })
              ]
            }))
          })
        ]
      }),
      jsx('div', {
        className: `${ID}-panel`, key: 'pilot',
        children: [
          jsx('div', { className: `${ID}-panelttl`, children: 'Pilot link: Month 1 benchmark' }),
          jsx('div', { className: `${ID}-kv`, children: 'This demo is the reconstruction surface for HP-707 / THRY-961612.' }),
          jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: 'Milestone 1 pays SAR 3,000 + VAT when Ajeez confirms environment + benchmark in writing.' })
        ]
      })
    ]
  })
}

/* ------------------------------- Today ------------------------------- */
function TodayView({ openJob }) {
  const q = useApi('/today')
  const [fPri, setFPri] = useState('all')
  const [fText, setFText] = useState('')
  const items = useMemo(() => {
    const list = (q.data && q.data.items) || []
    const needle = fText.toUpperCase()
    return list.filter(i =>
      (fPri === 'all' || i.priority === fPri) &&
      (!needle || (textOf(i.rig) + ' ' + textOf(i.well) + ' ' + textOf(i.finding) + ' ' + textOf(i.stage) + ' ' + textOf(i.action_required)).toUpperCase().includes(needle)))
  }, [q.data, fPri, fText])
  const total = (q.data && q.data.items && q.data.items.length) || 0
  return jsx(LoadGate, {
    q, empty: q.data && items.length === 0 ? { title: 'Nothing matches', desc: 'Clear the filters to see all items.' } : null,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'Today, 19 September 2026' }),
        jsx('div', { className: `${ID}-sub`, children: 'Only what requires attention. ' + q.data.date_rule }),
        jsx('div', {
          className: `${ID}-tiles`,
          children: q.data.cards.map(c => jsx('div', {
            className: `${ID}-tile`, key: c.key,
            'data-hot': (c.key === 'attention' || c.key === 'conflict') && c.value > 0 ? '1' : '0',
            children: jsxs('div', {
              children: [
                jsx('div', { className: `${ID}-num`, children: String(c.value) }),
                jsx('div', { className: `${ID}-lbl`, children: c.label })
              ]
            })
          }))
        }),
        jsxs('div', {
          className: `${ID}-toolbar`,
          children: [
            jsx(SegmentedControl, {
              value: fPri,
              onChange: v => setFPri(v),
              options: [
                { id: 'all', label: 'All' },
                { id: 'critical', label: 'Critical' },
                { id: 'high', label: 'High' },
                { id: 'medium', label: 'Medium' }
              ]
            }),
            jsx(SearchField, {
              value: fText,
              onChange: v => setFText(searchVal(v)),
              placeholder: 'Filter rig, well, finding...'
            }),
            jsx('span', { className: `${ID}-resultcount`, children: 'Showing ' + items.length + ' of ' + total })
          ]
        }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: jsx('div', {
          className: `${ID}-tablewrap`,
          children: jsx('table', {
            className: `${ID}-table`,
            'aria-label': 'Items requiring attention',
            children: [
              jsx(THead, { cols: ['Priority', 'Rig', 'Well', 'Stage', 'Finding', 'Action Required', 'Evidence', 'Page', 'Approval'] }),
              jsx('tbody', {
                children: items.map(i => jsx('tr', {
                  key: i.job_id, 'data-hot': i.priority === 'critical' ? '1' : '0',
                  children: [
                    jsx('td', { children: jsx(Pill, { status: i.priority }) }),
                    jsx('td', { children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => openJob(i.job_id), children: jsx('strong', { children: i.rig }) }) }),
                    jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: i.well }) }),
                    jsx('td', { children: jsx(Pill, { status: i.stage }) }),
                    jsx('td', { children: i.finding }),
                    jsx('td', { children: i.action_required }),
                    jsx('td', { children: jsx(Pill, { status: i.evidence_state }) }),
                    jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: 'p' + i.source_page }) }),
                    jsx('td', { children: jsx(Pill, { status: i.approval }) })
                  ]
                }))
              })
            ]
          })
        })
            }),
            jsx(SnapshotRail, { items: items, fPri: fPri, onPri: setFPri, onStage: s => { setFPri('all'); setFText(s) } })
          ]
        })
      ]
    }) : null
  })
}

/* ---------------------------- Action Queue ---------------------------- */
function ActionsView({ openJob }) {
  const q = useApi('/actions')
  const [fState, setFState] = useState('open')
  const all = (q.data && q.data.actions) || []
  const open = all.filter(a => a.state === 'awaiting' || a.state === 'blocked')
  const decided = all.length - open.length
  const shown = fState === 'open' ? open : fState === 'all' ? all : all.filter(a => a.state === fState)
  const parts = [
    { id: 'awaiting', label: 'Awaiting', opacity: 1 },
    { id: 'blocked', label: 'Blocked', opacity: 0.7 },
    { id: 'approved', label: 'Approved', opacity: 0.45 },
    { id: 'rejected', label: 'Rejected', opacity: 0.3 },
    { id: 'incorrect', label: 'Incorrect', opacity: 0.18 }
  ].map(g => ({
    id: g.id, label: g.label, opacity: g.opacity,
    value: all.filter(a => a.state === g.id).length,
    active: fState === g.id,
    onPick: () => setFState(fState === g.id ? 'open' : g.id)
  }))
  return jsx(LoadGate, {
    q, empty: q.data && shown.length === 0 ? { title: fState === 'open' ? 'Queue is clear' : 'No actions in this state', desc: fState === 'open' ? 'Every proposed action has a decision.' : 'Pick another state in the snapshot rail.' } : null,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'Action Queue' }),
        jsx('div', { className: `${ID}-sub`, children: 'Hermes proposes, Ajeez decides. Approve writes to the LOCAL DEMO database only. ' + shown.length + ' shown.' }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: shown.map(a => jsx('div', {
                className: `${ID}-card`, key: a.id, 'data-hot': a.state === 'blocked' ? '1' : '0',
                children: jsxs('div', {
                  children: [
                    jsxs('div', {
                      className: `${ID}-rowline`,
                      children: [
                        jsx('strong', { children: a.title }),
                        jsx(Pill, { status: a.state.toUpperCase() }),
                        jsx('span', { className: `${ID}-sub`, style: { margin: 0 }, children: a.kind + ', ' + a.scope })
                      ]
                    }),
                    jsx('div', { className: `${ID}-kv`, children: 'Why: ' + a.why }),
                    jsx('div', { className: `${ID}-kv`, children: 'Proposal: ' + a.proposal }),
                    jsx('div', { className: `${ID}-kv`, children: jsx('span', { className: `${ID}-sub`, children: 'If approved: ' + a.effect }) }),
                    a.last_decision ? jsx('div', {
                      className: `${ID}-kv`,
                      children: jsx('span', { className: `${ID}-sub`, children: 'Last: ' + a.last_decision.decision + ' at ' + a.last_decision.at + (a.last_decision.note ? ', ' + a.last_decision.note : '') })
                    }) : null,
                    jsxs('div', {
                      className: `${ID}-actions`,
                      children: [
                        jsx(DecisionButtons, { action: a }),
                        a.job_id ? jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => openJob(a.job_id), children: 'View Evidence' }) : null
                      ]
                    })
                  ]
                })
              }))
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Queue snapshot',
              children: [
                jsx('div', {
                  className: `${ID}-panel`, key: 'state',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: 'Decision states, tap to filter' }),
                    jsx('div', {
                      className: `${ID}-legend`,
                      children: parts.map(p => jsx('button', {
                        key: p.id, className: `${ID}-legrow`, 'data-active': p.active ? '1' : '0',
                        onClick: p.onPick, title: 'Filter actions: ' + p.label,
                        children: [
                          jsx('span', { className: `${ID}-swatch`, style: { background: 'var(--ui-accent)', opacity: p.opacity } }),
                          jsx('span', { style: { flex: 1 }, children: p.label }),
                          jsx('span', { className: `${ID}-mono`, children: String(p.value) })
                        ]
                      }))
                    })
                  ]
                }),
                jsx('div', {
                  className: `${ID}-panel`, key: 'sum',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: 'Summary' }),
                    jsx('div', {
                      children: [
                        jsxs('div', { className: `${ID}-legline`, key: 'o', children: [jsx('span', { children: 'Open now' }), jsx('span', { className: `${ID}-mono`, children: String(open.length) })] }),
                        jsxs('div', { className: `${ID}-legline`, key: 'd', children: [jsx('span', { children: 'Decided' }), jsx('span', { className: `${ID}-mono`, children: String(decided) })] }),
                        jsxs('div', { className: `${ID}-legline`, key: 't', children: [jsx('span', { children: 'Total proposed' }), jsx('span', { className: `${ID}-mono`, children: String(all.length) })] })
                      ]
                    }),
                    jsx('div', {
                      className: `${ID}-actions`,
                      children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => setFState(fState === 'all' ? 'open' : 'all'), children: fState === 'all' ? 'Show open only' : 'Show decided too' })
                    })
                  ]
                })
              ]
            })
          ]
        })
      ]
    }) : null
  })
}

/* ----------------------------- Rigs & Wells ----------------------------- */
function RigsView({ openRig }) {
  const [qry, setQry] = useState(storageGet('rigq', ''))
  const [fStage, setFStage] = useState('all')
  const [page, setPage] = useState(0)
  const per = 60
  // Full index in one cached read (292 rows max): stage bars and search
  // both run client-side, so every bar tap filters instantly.
  const q = useApi('/rigs?limit=292&offset=0')
  useEffect(() => { storageSet('rigq', qry); setPage(0) }, [qry, fStage])
  const allRows = (q.data && q.data.rows) || []
  const indexTotal = (q.data && q.data.total) || 0
  const stageMap = {}
  allRows.forEach(r => { stageMap[r.stage] = (stageMap[r.stage] || 0) + 1 })
  const stages = Object.keys(stageMap).map(s => ({ stage: s, count: stageMap[s] })).sort((a, b) => b.count - a.count)
  const maxStage = Math.max(1, ...stages.map(s => s.count))
  const filtered = useMemo(() => {
    const needle = qry.toUpperCase()
    return allRows.filter(r =>
      (fStage === 'all' || r.stage === fStage) &&
      (!needle || (textOf(r.rig) + ' ' + textOf(r.well) + ' ' + textOf(r.stage) + ' ' + textOf(r.orio_relevance)).toUpperCase().includes(needle)))
  }, [allRows, qry, fStage])
  const total = filtered.length
  const rows = filtered.slice(page * per, page * per + per)
  const pages = Math.max(1, Math.ceil(total / per))
  const safePage = Math.min(page, pages - 1)
  const pageRows = safePage === page ? rows : filtered.slice(safePage * per, safePage * per + per)
  return jsx(LoadGate, {
    q, empty: q.data && filtered.length === 0 ? { title: 'No matching blocks', desc: 'Try a different rig, well, or stage.' } : null,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'Rigs & Wells' }),
        jsx('div', { className: `${ID}-sub`, children: 'Full Sep 19 index, ' + indexTotal + ' blocks. No bookmarks, no Ctrl+F.' }),
        jsxs('div', {
          className: `${ID}-toolbar`,
          children: [
            jsx(SearchField, {
              value: qry,
              onChange: v => setQry(searchVal(v)),
              placeholder: 'Search rig, well, stage (try HP-707)...'
            }),
            jsx('span', { className: `${ID}-resultcount`, children: 'Showing ' + pageRows.length + ' of ' + total })
          ]
        }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: [
                jsx('div', {
                  className: `${ID}-tablewrap`,
                  children: jsx('table', {
                    className: `${ID}-table`,
                    'aria-label': 'Rig and well index',
                    children: [
                      jsx(THead, { cols: ['Rig', 'Well', 'Pages', 'Stage', 'ORIO relevance', ''] }),
                      jsx('tbody', {
                        children: pageRows.map(r => jsx('tr', {
                          key: r.rig + r.well,
                          children: [
                            jsx('td', { children: jsx('strong', { children: r.rig }) }),
                            jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: r.well }) }),
                            jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: 'p' + r.first_page + (r.pages > 1 ? '-' + (r.first_page + r.pages - 1) : '') }) }),
                            jsx('td', { children: r.stage }),
                            jsx('td', { children: r.orio_relevance }),
                            jsx('td', { children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => openRig(r.rig, r.well), children: 'Open' }) })
                          ]
                        }))
                      })
                    ]
                  })
                }),
                total > per ? jsxs('div', {
                  className: `${ID}-pager`,
                  children: [
                    jsx(Button, { size: 'xs', variant: 'ghost', disabled: safePage === 0, onClick: () => setPage(p => Math.max(0, (p > pages - 1 ? pages - 1 : p)) - 1), children: 'Prev' }),
                    jsx('span', { className: `${ID}-sub`, style: { margin: 0 }, children: 'Page ' + (safePage + 1) + ' of ' + pages }),
                    jsx(Button, { size: 'xs', variant: 'ghost', disabled: (safePage + 1) * per >= total, onClick: () => setPage(p => (p > pages - 1 ? pages - 1 : p) + 1), children: 'Next' })
                  ]
                }) : null
              ]
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Index snapshot',
              children: [
                jsx('div', {
                  className: `${ID}-panel`, key: 'stage',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: 'Stages, tap to filter' }),
                    jsx('div', {
                      children: stages.map(s => jsx('button', {
                        key: s.stage, className: `${ID}-stagerow`,
                        'data-active': fStage === s.stage ? '1' : '0',
                        onClick: () => setFStage(fStage === s.stage ? 'all' : s.stage),
                        title: 'Filter index: ' + s.stage,
                        children: [
                          jsxs('span', {
                            className: `${ID}-stagerowline`,
                            children: [
                              jsx('span', { style: fStage === s.stage ? { fontWeight: 700, color: 'var(--ui-accent)' } : null, children: s.stage + ' (' + s.count + ')' }),
                              jsx('span', { className: `${ID}-mono`, children: String(s.count) })
                            ]
                          }),
                          jsx('span', { className: `${ID}-bar`, children: jsx('span', { style: { width: (s.count / maxStage * 100) + '%' } }) })
                        ]
                      }))
                    })
                  ]
                }),
                fStage !== 'all' ? jsx('div', {
                  className: `${ID}-panel`, key: 'clear',
                  children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => setFStage('all'), children: 'Clear stage filter' })
                }) : null
              ]
            })
          ]
        })
      ]
    }) : null
  })
}

/* ------------------------------ Lifecycle ------------------------------ */
function LifecycleView({ openJob }) {
  const q = useApi('/lifecycle')
  const [fState, setFState] = useState('all')
  const jobs = (q.data && q.data.jobs) || []
  const states = []
  jobs.forEach(j => {
    if (!states.some(s => s.id === j.lifecycle)) states.push({ id: j.lifecycle, label: j.lifecycle })
  })
  const opac = [1, 0.7, 0.5, 0.36, 0.24, 0.16]
  const parts = states.map((s, ix) => ({
    id: s.id, label: s.label, opacity: opac[Math.min(ix, opac.length - 1)],
    value: jobs.filter(j => j.lifecycle === s.id).length,
    active: fState === s.id,
    onPick: () => setFState(fState === s.id ? 'all' : s.id)
  }))
  const shown = fState === 'all' ? jobs : jobs.filter(j => j.lifecycle === fState)
  return jsx(LoadGate, {
    q,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'ORIO Lifecycle' }),
        jsx('div', { className: `${ID}-sub`, children: q.data.note + ' ' + shown.length + ' of ' + jobs.length + ' tracked jobs.' }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: jsx('div', {
                className: `${ID}-tablewrap`,
                children: jsx('table', {
                  className: `${ID}-table`,
                  'aria-label': 'ORIO job lifecycle',
                  children: [
                    jsx(THead, { cols: ['Job', 'Cycle', 'State', 'Priority', 'Finding', ''] }),
                    jsx('tbody', {
                      children: shown.map(j => jsx('tr', {
                        key: j.id,
                        children: [
                          jsx('td', { children: jsx('strong', { children: j.rig + ' / ' + j.well }) }),
                          jsx('td', { children: jsx('span', { className: `${ID}-sub`, children: j.cycle }) }),
                          jsx('td', { children: jsx(Pill, { status: j.lifecycle }) }),
                          jsx('td', { children: jsx(Pill, { status: j.priority }) }),
                          jsx('td', { children: j.finding }),
                          jsx('td', { children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => openJob(j.id), children: 'Open' }) })
                        ]
                      }))
                    })
                  ]
                })
              })
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Lifecycle snapshot',
              children: jsx('div', {
                className: `${ID}-panel`, key: 'state',
                children: [
                  jsx('div', { className: `${ID}-panelttl`, children: 'States, tap to filter' }),
                  jsx(Donut, { parts: parts, label: 'Jobs by lifecycle state' })
                ]
              })
            })
          ]
        })
      ]
    }) : null
  })
}

/* ------------------------------ Exceptions ------------------------------ */
function ExceptionCard({ x, openJob }) {
  const qc = useQueryClient()
  const [resolving, setResolving] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const resolve = () => {
    if (!note.trim()) {
      host.notify({ kind: 'error', message: 'A resolution note is required.' })
      return
    }
    setBusy(true)
    api('/exceptions/' + x.id + '/resolve', { method: 'POST', body: { note } })
      .then(() => {
        host.notify({ kind: 'info', message: 'Exception annotated in demo state.' })
        setResolving(false)
        setNote('')
        qc.invalidateQueries({ queryKey: [ID] })
      })
      .catch(e => host.notify({ kind: 'error', message: 'Resolve failed: ' + errText(e) }))
      .finally(() => setBusy(false))
  }
  return jsx('div', {
    className: `${ID}-card`, 'data-hot': x.state === 'open' ? '1' : '0',
    children: jsxs('div', {
      children: [
        jsxs('div', {
          className: `${ID}-rowline`,
          children: [jsx('strong', { children: x.issue }), jsx(Pill, { status: x.state.toUpperCase() })]
        }),
        jsx('div', { className: `${ID}-kv`, children: 'Source A: ' + x.source_a }),
        jsx('div', { className: `${ID}-kv`, children: 'Source B: ' + x.source_b }),
        jsx('div', { className: `${ID}-kv`, children: 'Risk: ' + x.risk }),
        jsx('div', { className: `${ID}-kv`, children: jsx('span', { className: `${ID}-sub`, children: 'Recommended: ' + x.resolution }) }),
        x.state === 'open' ? (resolving
          ? jsxs('div', {
            className: `${ID}-actions`,
            children: [
              jsx(SearchField, {
                value: note,
                onChange: v => setNote(searchVal(v)),
                placeholder: 'Resolution note (required)...'
              }),
              jsx(Button, { size: 'xs', disabled: busy, onClick: resolve, children: busy ? 'Saving...' : 'Save' }),
              jsx(Button, { size: 'xs', variant: 'ghost', disabled: busy, onClick: () => { setResolving(false); setNote('') }, children: 'Cancel' })
            ]
          })
          : jsxs('div', {
            className: `${ID}-actions`,
            children: [
              jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => { setResolving(true); setNote('') }, children: 'Resolve / Annotate' }),
              x.job_id ? jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => openJob(x.job_id), children: 'Open Job' }) : null
            ]
          })) : null
      ]
    })
  })
}

function ExceptionsView({ openJob }) {
  const q = useApi('/exceptions')
  const [fState, setFState] = useState('all')
  const list = (q.data && q.data.exceptions) || []
  const openCount = list.filter(x => x.state === 'open').length
  const resolvedCount = list.length - openCount
  const parts = [
    { id: 'open', label: 'Open', opacity: 1, value: openCount, active: fState === 'open', onPick: () => setFState(fState === 'open' ? 'all' : 'open') },
    { id: 'resolved', label: 'Resolved', opacity: 0.35, value: resolvedCount, active: fState === 'resolved', onPick: () => setFState(fState === 'resolved' ? 'all' : 'resolved') }
  ]
  const shown = fState === 'all' ? list : list.filter(x => x.state === fState)
  return jsx(LoadGate, {
    q, empty: q.data && shown.length === 0 ? { title: 'Nothing in this state', desc: 'Pick another state in the snapshot rail.' } : null,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'Exceptions' }),
        jsx('div', { className: `${ID}-sub`, children: 'Real inconsistencies with both sources shown. Nothing auto-resolved. ' + openCount + ' open.' }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: shown.map(x => jsx(ExceptionCard, { x, openJob, key: x.id }))
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Exceptions snapshot',
              children: jsx('div', {
                className: `${ID}-panel`, key: 'state',
                children: [
                  jsx('div', { className: `${ID}-panelttl`, children: 'Resolution, tap to filter' }),
                  jsx('div', {
                    className: `${ID}-legend`,
                    children: parts.map(p => jsx('button', {
                      key: p.id, className: `${ID}-legrow`, 'data-active': p.active ? '1' : '0',
                      onClick: p.onPick, title: 'Filter exceptions: ' + p.label,
                      children: [
                        jsx('span', { className: `${ID}-swatch`, style: { background: 'var(--ui-accent)', opacity: p.opacity } }),
                        jsx('span', { style: { flex: 1 }, children: p.label }),
                        jsx('span', { className: `${ID}-mono`, children: String(p.value) })
                      ]
                    }))
                  })
                ]
              })
            })
          ]
        })
      ]
    }) : null
  })
}

/* ------------------------------- Evidence ------------------------------- */
function EvidenceView() {
  const listQ = useApi('/lifecycle')
  const [jobId, setJobId] = useState('hp701')
  const [fEv, setFEv] = useState('all')
  const jobs = (listQ.data && listQ.data.jobs) || []
  useEffect(() => {
    if (jobs.length && !jobs.some(j => j.id === jobId)) setJobId(jobs[0].id)
  }, [jobs.length])
  useEffect(() => { setFEv('all') }, [jobId])
  const jobQ = useApi('/jobs/' + jobId)
  const job = jobQ.data
  const statuses = []
  if (job) job.evidence.forEach(e => { if (!statuses.includes(e.status)) statuses.push(e.status) })
  const maxEv = Math.max(1, ...statuses.map(s => job.evidence.filter(e => e.status === s).length))
  return jsx(LoadGate, {
    q: listQ,
    children: listQ.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'Evidence' }),
        jsx('div', { className: `${ID}-sub`, children: 'Why Hermes said it. Source page and tracker row on every conclusion.' }),
        jsx('div', {
          className: `${ID}-toolbar`,
          children: jsx('div', {
            className: `${ID}-pickerrow`,
            role: 'tablist',
            'aria-label': 'Job evidence picker',
            children: jobs.map(j => jsx('button', {
              role: 'tab',
              'aria-selected': jobId === j.id ? 'true' : 'false',
              className: `${ID}-navbtn`,
              'data-active': jobId === j.id ? '1' : '0',
              key: j.id,
              onClick: () => setJobId(j.id),
              children: j.rig + ' / ' + j.well
            }))
          })
        }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: jsx(LoadGate, { q: jobQ, children: job ? jsx(JobEvidence, { job, fEv, onEv: setFEv }) : null })
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Evidence snapshot',
              children: job ? [
                jsx('div', {
                  className: `${ID}-panel`, key: 'job',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: job.rig + ' / ' + job.well }),
                    jsx('div', {
                      children: [
                        jsxs('div', { className: `${ID}-legline`, key: 'p', children: [jsx('span', { children: 'Source pages' }), jsx('span', { className: `${ID}-mono`, children: 'p' + job.first_page + '-' + (job.first_page + job.pages - 1) })] }),
                        jsxs('div', { className: `${ID}-legline`, key: 'f', children: [jsx('span', { children: 'Foreman' }), jsx('span', { className: `${ID}-mono`, children: String(job.foreman || 'not listed') })] }),
                        jsxs('div', { className: `${ID}-legline`, key: 't', children: [jsx('span', { children: 'Tracker rows' }), jsx('span', { className: `${ID}-mono`, children: String((job.tracker || []).length) })] }),
                        jsxs('div', { className: `${ID}-legline`, key: 'e', children: [jsx('span', { children: 'Evidence entries' }), jsx('span', { className: `${ID}-mono`, children: String(job.evidence.length) })] })
                      ]
                    })
                  ]
                }),
                statuses.length > 1 ? jsx('div', {
                  className: `${ID}-panel`, key: 'status',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: 'Entry states, tap to filter' }),
                    jsx('div', {
                      children: statuses.map(s => {
                        const n = job.evidence.filter(e => e.status === s).length
                        return jsx('button', {
                          key: s, className: `${ID}-stagerow`,
                                                    'data-active': fEv === s ? '1' : '0',
                                                    onClick: () => setFEv(fEv === s ? 'all' : s),
                          title: 'Filter entries: ' + s,
                          children: [
                            jsxs('span', {
                              className: `${ID}-stagerowline`,
                              children: [
                                jsx('span', { style: fEv === s ? { fontWeight: 700, color: 'var(--ui-accent)' } : null, children: s + ' (' + n + ')' }),
                                jsx('span', { className: `${ID}-mono`, children: String(n) })
                              ]
                            }),
                            jsx('span', { className: `${ID}-bar`, children: jsx('span', { style: { width: (n / maxEv * 100) + '%' } }) })
                          ]
                        })
                      })
                    })
                  ]
                }) : null
              ] : null
            })
          ]
        })
      ]
    }) : null
  })
}

function JobEvidence({ job, fEv, onEv }) {
  const [inner, setInner] = useState('all')
  const active = onEv ? fEv : inner
  const setActive = onEv || setInner
  const statuses = []
  job.evidence.forEach(e => { if (!statuses.includes(e.status)) statuses.push(e.status) })
  const shown = active === 'all' ? job.evidence : job.evidence.filter(e => e.status === active)
  return jsxs('div', {
    children: [
      jsx('div', { className: `${ID}-sub`, children: 'Source: Sep 19 MR pages ' + job.first_page + '-' + (job.first_page + job.pages - 1) + '. Foreman: ' + (job.foreman || 'not listed') + '.' }),
      statuses.length > 1 ? jsx('div', {
        className: `${ID}-pickerrow`,
        role: 'tablist',
        'aria-label': 'Evidence status filter',
        children: ['all'].concat(statuses).map(s => jsx('button', {
          role: 'tab',
          'aria-selected': active === s ? 'true' : 'false',
          className: `${ID}-navbtn`,
          'data-active': active === s ? '1' : '0',
          key: s,
          onClick: () => setActive(s),
          children: s === 'all' ? 'All (' + job.evidence.length + ')' : s + ' (' + job.evidence.filter(e => e.status === s).length + ')'
        }))
      }) : null,
      (job.tracker || []).map((t, i) => jsx('div', {
        className: `${ID}-ev`, key: 't' + i,
        children: jsxs('div', { children: [jsx(Pill, { status: 'TRACKER' }), jsx('span', { children: ' Qty ' + (t.qty || 'n/a') + '. ' + t.note })] })
      })),
      shown.map((e, i) => jsx('div', {
        className: `${ID}-ev`, key: i,
        children: jsxs('div', {
          children: [
            jsx(Pill, { status: e.status }),
            jsx('span', { className: `${ID}-sub`, children: ' ' + e.kind + (e.page ? ', MR p' + e.page : ', tracker') + ': ' }),
            jsx('span', { children: e.text })
          ]
        })
      }))
    ]
  })
}

/* -------------------------------- History ------------------------------- */
function HistoryView() {
  const q = useApi('/history')
  const [retro, setRetro] = useState('current')
  const [fStage, setFStage] = useState('all')
  const events = (q.data && q.data.events) || []
  const isKey = e => (e.stage || '').indexOf('ORIO') >= 0 || (e.stage || '').indexOf('Landing') >= 0
  const stageMap = {}
  events.forEach(e => { const s = e.stage || 'n/a'; stageMap[s] = (stageMap[s] || 0) + 1 })
  const stages = Object.keys(stageMap).map(s => ({ stage: s, count: stageMap[s] })).sort((a, b) => b.count - a.count)
  const maxStage = Math.max(1, ...stages.map(s => s.count))
  const shownEvents = events.filter(e => (retro !== 'key' || isKey(e)) && (fStage === 'all' || (e.stage || 'n/a') === fStage))
  const main = retro === 'retro'
    ? jsx('div', {
      className: `${ID}-card`, 'data-hot': '1',
      children: jsxs('div', {
        children: [
          jsx('strong', { children: 'Retrospective QA, did the early flags prove meaningful?' }),
          jsx('div', { className: `${ID}-kv`, children: 'Yes. The Sep 1 dispatch-window signal (cement done, 8-1/2 BHA next) was followed by the full chain: 8-1/2 lateral to TD Sep 14, ORIO KSVs RIH Sep 15, INNOVEX ORIO valves landed Sep 17.' }),
          jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: 'No information newer than the stated source dates is used. Sep 19 state is never contaminated by later data, none is loaded in this demo.' })
        ]
      })
    })
    : shownEvents.length === 0
      ? jsx(Center, { children: jsx(EmptyState, { title: 'No events in this filter', desc: 'Clear the stage filter or pick another segment.' }) })
      : jsx('ol', {
        className: `${ID}-tl`,
        children: shownEvents.map((e, i) => jsx('li', {
          key: i, 'data-key': isKey(e) ? '1' : '0',
          children: jsxs('div', {
            children: [
              jsxs('div', {
                className: `${ID}-rowline`,
                children: [
                  jsx('span', { className: `${ID}-mono`, children: e.date }),
                  jsx(Pill, { status: String(e.stage || 'n/a').toUpperCase() })
                ]
              }),
              jsx('div', { children: e.text }),
              jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: e.source })
            ]
          })
        }))
      })
  return jsx(LoadGate, {
    q,
    children: q.data ? jsxs('div', {
      children: [
        jsx('h2', { className: `${ID}-h`, children: 'History, ' + q.data.job }),
        jsx('div', { className: `${ID}-sub`, children: q.data.note }),
        jsx('div', {
          className: `${ID}-toolbar`,
          children: jsx(SegmentedControl, {
            value: retro,
            onChange: v => setRetro(v),
            options: [
              { id: 'current', label: 'Current evidence' },
              { id: 'key', label: 'Key milestones' },
              { id: 'retro', label: 'Retrospective QA' }
            ]
          })
        }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', { className: `${ID}-todaymain`, children: main }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'History snapshot',
              children: [
                jsx('div', {
                  className: `${ID}-panel`, key: 'stage',
                  children: [
                    jsx('div', { className: `${ID}-panelttl`, children: 'Stages, tap to filter' }),
                    jsx('div', {
                      children: stages.map(s => jsx('button', {
                        key: s.stage, className: `${ID}-stagerow`,
                                                'data-active': fStage === s.stage ? '1' : '0',
                                                onClick: () => setFStage(fStage === s.stage ? 'all' : s.stage),
                                                title: 'Filter timeline: ' + s.stage,
                        children: [
                          jsxs('span', {
                            className: `${ID}-stagerowline`,
                            children: [
                              jsx('span', { style: fStage === s.stage ? { fontWeight: 700, color: 'var(--ui-accent)' } : null, children: s.stage + ' (' + s.count + ')' }),
                              jsx('span', { className: `${ID}-mono`, children: String(s.count) })
                            ]
                          }),
                          jsx('span', { className: `${ID}-bar`, children: jsx('span', { style: { width: (s.count / maxStage * 100) + '%' } }) })
                        ]
                      }))
                    })
                  ]
                }),
                fStage !== 'all' ? jsx('div', {
                  className: `${ID}-panel`, key: 'clear',
                  children: jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => setFStage('all'), children: 'Clear stage filter' })
                }) : null
              ]
            })
          ]
        })
      ]
    }) : null
  })
}

/* ------------------------------- Expansion ------------------------------- */
function ExpansionView() {
  const q = useApi('/expansion')
  const [fText, setFText] = useState('')
  const allRows = (q.data && q.data.rows) || []
  const needle = fText.toUpperCase()
  const rows = allRows.filter(r =>
    !needle || (textOf(r.date) + ' ' + textOf(r.rig) + ' ' + textOf(r.well) + ' ' + textOf(r.size) + ' ' + textOf(r.company) + ' ' + textOf(r.remarks)).toUpperCase().includes(needle))
  const coMap = {}
  allRows.forEach(r => { coMap[r.company] = (coMap[r.company] || 0) + 1 })
  const companies = Object.keys(coMap).map(c => ({ company: c, count: coMap[c] })).sort((a, b) => b.count - a.count)
  const maxCo = Math.max(1, ...companies.map(c => c.count))
  return jsx(LoadGate, {
    q,
    children: q.data ? jsxs('div', {
      children: [
        jsx('div', {
          className: `${ID}-card`, 'data-hot': '1',
          children: jsx('strong', { children: q.data.scope })
        }),
        jsx('h2', { className: `${ID}-h`, style: { marginTop: '.7rem' }, children: 'Competitor / Market Intelligence' }),
        jsx('div', { className: `${ID}-sub`, children: 'Limited demonstration. ' + q.data.statement + ' Showing ' + rows.length + ' of ' + allRows.length + ' rows.' }),
        jsx('div', {
          className: `${ID}-toolbar`,
          children: jsx(SearchField, {
            value: fText,
            onChange: v => setFText(searchVal(v)),
            placeholder: 'Filter company, rig, well...'
          })
        }),
        jsx('div', {
          className: `${ID}-todaygrid`,
          children: [
            jsx('div', {
              className: `${ID}-todaymain`,
              children: jsx('div', {
                  className: `${ID}-tablewrap`,
                  children: jsx('table', {
                    className: `${ID}-table`,
                    'aria-label': 'Competitor intelligence demo rows',
                    children: [
                      jsx(THead, { cols: ['Date RIH', 'Rig', 'Well', 'Size', 'Company', 'Special Remarks'] }),
                      jsx('tbody', {
                        children: rows.map((r, i) => jsx('tr', {
                          key: i,
                          children: [
                            jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: r.date || 'n/a' }) }),
                            jsx('td', { children: jsx('strong', { children: r.rig }) }),
                            jsx('td', { children: jsx('span', { className: `${ID}-mono`, children: r.well }) }),
                            jsx('td', { children: r.size }),
                            jsx('td', { children: r.company }),
                            jsx('td', { children: r.remarks })
                          ]
                        }))
                      })
                    ]
                  })
                })
            }),
            jsx('aside', {
              className: `${ID}-rail`,
              'aria-label': 'Competitor snapshot',
              children: jsx('div', {
                className: `${ID}-panel`, key: 'co',
                children: [
                  jsx('div', { className: `${ID}-panelttl`, children: 'Companies, tap to filter' }),
                  jsx('div', {
                    children: companies.map(c => jsx('button', {
                      key: c.company, className: `${ID}-stagerow`,
                                            'data-active': fText === c.company ? '1' : '0',
                                            onClick: () => setFText(fText === c.company ? '' : c.company),
                      title: 'Filter table: ' + c.company,
                      children: [
                        jsxs('span', {
                          className: `${ID}-stagerowline`,
                          children: [
                            jsx('span', { style: fText === c.company ? { fontWeight: 700, color: 'var(--ui-accent)' } : null, children: c.company + ' (' + c.count + ')' }),
                            jsx('span', { className: `${ID}-mono`, children: String(c.count) })
                          ]
                        }),
                        jsx('span', { className: `${ID}-bar`, children: jsx('span', { style: { width: (c.count / maxCo * 100) + '%' } }) })
                      ]
                    }))
                  })
                ]
              })
            })
          ]
        })
      ]
    }) : null
  })
}

/* ------------------------------- Job dialog ------------------------------ */
function JobDialog({ jobId, rigWell, onClose }) {
  const qc = useQueryClient()
  const open = !!(jobId || rigWell)
  // Both queries run unconditionally (hook order must never change).
  // The inactive one reads /health: tiny, cached, never a 404.
  const jobQ = useApi(jobId ? '/jobs/' + jobId : '/health')
  const rigQ = useApi((!jobId && rigWell) ? '/rigs/' + rigWell.rig + '/' + rigWell.well : '/health')
  const [mdd, setMdd] = useState(null)
  const [draft, setDraft] = useState(null)
  useEffect(() => { setMdd(null); setDraft(null) }, [jobId, rigWell && rigWell.rig, rigWell && rigWell.well])
  const activeQ = jobId ? jobQ : rigQ
  const job = jobId ? jobQ.data : (rigQ.data && rigQ.data.job)
  const block = jobId ? jobQ.data : rigQ.data
  const title = job ? job.rig + ' / ' + job.well : (block && block.rig ? block.rig + ' / ' + block.well : 'Job')
  const loadMdd = () => {
    api('/mdd/preview?job=' + (job ? job.id : 'hp701')).then(setMdd)
      .catch(e => host.notify({ kind: 'error', message: 'MDD preview failed: ' + errText(e) }))
  }
  const makeDraft = () => {
    api('/drafts/email', { method: 'POST', body: { job: job ? job.id : 'hp701' } })
      .then(d => { setDraft(d.body); qc.invalidateQueries({ queryKey: [ID] }) })
      .catch(e => host.notify({ kind: 'error', message: 'Draft failed: ' + errText(e) }))
  }
  return jsx(Dialog, {
    open, onOpenChange: v => { if (!v) onClose() },
    children: jsx(DialogContent, {
      style: { maxWidth: '46rem' },
      children: activeQ.isLoading
        ? jsx(Center, { children: jsx(GlyphSpinner, {}) })
        : activeQ.isError
          ? jsx(Center, {
            children: jsxs('div', {
              children: [
                jsx(ErrorState, { title: 'Could not load detail', description: errText(activeQ.error) }),
                jsxs('div', {
                  style: { marginTop: '.6rem', display: 'flex', gap: '.4rem', justifyContent: 'center' },
                  children: [
                    jsx(Button, { size: 'xs', onClick: () => activeQ.refetch(), children: 'Retry' }),
                    jsx(Button, { size: 'xs', variant: 'ghost', onClick: onClose, children: 'Close' })
                  ]
                })
              ]
            })
          })
          : !block
            ? jsx(Center, { children: jsx(EmptyState, { title: 'No detail', description: 'This record is not in the Sep 19 index.' }) })
            : jsxs('div', {
              children: [
                jsxs(DialogHeader, {
                  children: [
                    jsx(DialogTitle, { children: title }),
                    jsx(DialogDescription, {
                      children: job
                        ? job.lifecycle + ', priority ' + job.priority + ', cycle ' + job.cycle
                        : 'Sep 19 block, pages ' + block.first_page + '-' + (block.first_page + block.pages - 1) + '. Not a tracked ORIO job.'
                    })
                  ]
                }),
                jsx(ScrollArea, {
                  className: 'h-full',
                  children: job ? jsxs('div', {
                    children: [
                      jsx('div', { children: job.finding }),
                      jsx('div', { className: `${ID}-sub`, style: { margin: '.3rem 0 0' }, children: 'Last 24h: ' + job.last24 }),
                      jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: 'Next 24h: ' + job.next24 }),
                      jsx(Separator, {}),
                      jsx('div', { className: `${ID}-secttl`, children: 'Evidence' }),
                      jsx(JobEvidence, { job }),
                      jsx(Separator, {}),
                      jsx('div', { className: `${ID}-secttl`, children: 'Proposed actions' }),
                      job.actions.length ? job.actions.map(a => jsx('div', {
                        className: `${ID}-card`, key: a.id, 'data-hot': a.state === 'blocked' ? '1' : '0',
                        children: jsxs('div', {
                          children: [
                            jsxs('div', {
                              className: `${ID}-rowline`,
                              children: [jsx('strong', { children: a.title }), jsx(Pill, { status: a.state.toUpperCase() })]
                            }),
                            jsx('div', { className: `${ID}-sub`, style: { margin: '.2rem 0 0' }, children: 'Why: ' + a.why }),
                            jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: 'If approved: ' + a.effect }),
                            jsx('div', { className: `${ID}-actions`, children: jsx(DecisionButtons, { action: a, onDone: () => qc.invalidateQueries({ queryKey: [ID] }) }) })
                          ]
                        })
                      })) : jsx('div', { className: `${ID}-sub`, children: 'No proposed actions. Monitoring.' }),
                      jsx(Separator, {}),
                      jsx('div', { className: `${ID}-secttl`, children: 'Documents' }),
                      jsxs('div', {
                        className: `${ID}-actions`,
                        children: [
                          jsx(Button, { size: 'xs', variant: 'ghost', onClick: loadMdd, children: 'Preview MDD Requirement' }),
                          jsx(Button, { size: 'xs', variant: 'ghost', onClick: makeDraft, children: 'Draft Email (local preview)' }),
                          jsx(Button, { size: 'xs', variant: 'ghost', disabled: true, title: 'Production connection disabled in demo', children: 'Send Email (disabled)' })
                        ]
                      }),
                      mdd ? jsx('div', {
                        className: `${ID}-card`, 'data-hot': '1',
                        children: jsxs('div', {
                          children: [
                            jsx('strong', { children: 'MDD preview, local only, nothing sent.' }),
                            mdd.lines.map((l, i) => jsx('div', { className: `${ID}-kv`, 'data-missing': isMissing(l[1]) ? '1' : '0', key: i, children: jsxs('div', { children: [jsx('strong', { children: l[0] + ': ' }), jsx('span', { children: l[1] })] }) })),
                            jsx('div', { className: `${ID}-sub`, style: { margin: 0 }, children: mdd.cross_check })
                          ]
                        })
                      }) : null,
                      draft ? jsx('div', {
                        className: `${ID}-card`,
                        children: jsxs('div', {
                          children: [
                            jsx('strong', { children: 'Email draft, local preview, not sent.' }),
                            jsx('pre', { className: `${ID}-pre`, children: draft })
                          ]
                        })
                      }) : null
                    ]
                  }) : jsxs('div', {
                    children: [
                      jsx('div', { className: `${ID}-sub`, children: 'Stage: ' + (block.stage || 'n/a') + '. Monitoring.' }),
                      jsx('div', { className: `${ID}-kv`, children: 'Last 24h: ' + (block.last24 || 'n/a') }),
                      jsx('div', { className: `${ID}-kv`, children: 'Next 24h: ' + (block.next24 || 'n/a') })
                    ]
                  })
                }),
                jsxs(DialogFooter, {
                  children: [
                    jsx('span', { className: `${ID}-sub`, style: { margin: '0 auto 0 0' }, children: 'Demo state only. Nothing leaves this machine.' }),
                    jsx(Button, { size: 'xs', variant: 'ghost', onClick: onClose, children: 'Close' })
                  ]
                })
              ]
            })
    })
  })
}

/* --------------------------------- App --------------------------------- */
function OrioPage() {
  const view = useValue($view)
  const qc = useQueryClient()
  useEffect(() => { refreshAll = () => { qc.invalidateQueries({ queryKey: [ID] }); return true } }, [qc])
  const [selJob, setSelJob] = useState(null)
  const [selRig, setSelRig] = useState(null)
  const openJob = id => { setSelRig(null); setSelJob(id) }
  const openRig = (rig, well) => { setSelJob(null); setSelRig({ rig, well }) }
  const closeSel = () => { setSelJob(null); setSelRig(null) }
  const todayQ = useApi('/today')
  const actsQ = useApi('/actions')
  const excQ = useApi('/exceptions')
  const rigsQ = useApi('/rigs?limit=1&offset=0')
  const attn = todayQ.data ? todayQ.data.items.filter(i => i.priority === 'critical' || i.priority === 'high').length : 0
  const awaiting = actsQ.data ? actsQ.data.actions.filter(a => a.state === 'awaiting' || a.state === 'blocked').length : 0
  const openExc = excQ.data ? excQ.data.exceptions.filter(x => x.state === 'open').length : 0
  const rigsTotal = rigsQ.data ? rigsQ.data.total : null
  const countFor = id => (id === 'today' ? attn : id === 'actions' ? awaiting : id === 'exceptions' ? openExc : id === 'rigs' ? rigsTotal : null)
  const V = view === 'today' ? jsx(TodayView, { openJob })
    : view === 'actions' ? jsx(ActionsView, { openJob })
    : view === 'rigs' ? jsx(RigsView, { openRig })
    : view === 'lifecycle' ? jsx(LifecycleView, { openJob })
    : view === 'exceptions' ? jsx(ExceptionsView, { openJob })
    : view === 'evidence' ? jsx(EvidenceView, {})
    : view === 'history' ? jsx(HistoryView, {})
    : jsx(ExpansionView, {})
  const howItWorks = async () => {
    const ok = await revealPath(ARCH_HTML).catch(() => false)
    host.notify(ok
      ? { kind: 'info', message: 'Architecture reference revealed.' }
      : { kind: 'info', message: 'Architecture: ' + ARCH_HTML })
  }
  return jsxs('div', {
    className: `${ID}-page`,
    children: [
      jsxs('div', {
        className: `${ID}-topbar`,
        children: [
          jsx('span', { className: `${ID}-title`, children: 'ORIO Operations' }),
          jsx('span', { className: `${ID}-demobadge`, children: 'DEMO, LOCAL DATA ONLY' }),
          jsx('span', { className: `${ID}-sub`, style: { margin: 0 }, children: 'No external actions enabled.' }),
          jsx('span', { style: { flex: 1 } }),
          jsx(Button, { size: 'xs', variant: 'ghost', onClick: howItWorks, children: 'How this works' }),
          jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => { refreshAll(); host.notify({ kind: 'info', message: 'ORIO data refresh requested.' }) }, children: 'Refresh' })
        ]
      }),
      jsxs('div', {
        className: `${ID}-body`,
        children: [
          jsx('nav', {
            className: `${ID}-side`,
            'aria-label': 'ORIO views',
            children: VIEWS.map(v => {
              const c = countFor(v.id)
              return jsx('button', {
                className: `${ID}-navbtn`, key: v.id, 'data-active': view === v.id ? '1' : '0',
                'aria-current': view === v.id ? 'page' : undefined,
                onClick: () => { $view.set(v.id); storageSet('view', v.id) },
                children: jsxs('span', {
                  style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '.4rem' },
                  children: [
                    jsx('span', { children: v.label }),
                    c !== null && c !== undefined ? jsx('span', { className: `${ID}-count`, 'data-hot': c > 0 && (v.id === 'today' || v.id === 'actions' || v.id === 'exceptions') ? '1' : '0', children: String(c) }) : null
                  ]
                })
              })
            })
          }),
          jsx('div', {
            className: `${ID}-main`,
            children: jsx(ScrollArea, {
              className: 'h-full',
              children: jsx('div', { className: `${ID}-content`, children: V })
            })
          })
        ]
      }),
      jsx(JobDialog, { jobId: selJob, rigWell: selRig, onClose: closeSel })
    ]
  })
}

export default {
  id: ID,
  name: 'ORIO Operations',
  description: 'ORIO Operations demo for the Innovex pilot. Local data only, no external actions.',
  defaultEnabled: true,
  register(ctx) {
    ensureStyles()
    restFn = ctx.rest
    revealPath = ctx.os && ctx.os.revealPath ? p => ctx.os.revealPath(p) : async () => false
    try {
      const v = ctx.storage.get('view', 'today')
      if (VIEWS.some(x => x.id === v)) $view.set(v)
    } catch (e) { /* session-only */ }
    storageGet = (key, fallback) => {
      try { return ctx.storage.get(key, fallback) } catch (e) { return fallback }
    }
    storageSet = (key, value) => {
      try { ctx.storage.set(key, value) } catch (e) { /* session-only */ }
    }
    const dispose = ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: PAGE },
        render: () => jsx(OrioPage, {})
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 55,
        data: { codicon: 'dashboard', label: 'ORIO Operations', path: PAGE }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: { id: ID + '.open', label: 'ORIO: Open Operations', keywords: ['orio', 'operations', 'innovex'], run: () => host.navigate(PAGE) }
      },
      {
        id: 'refresh',
        area: PALETTE_AREA,
        data: { id: ID + '.refresh', label: 'ORIO: Refresh Data', keywords: ['orio', 'refresh'], run: () => { refreshAll(); host.notify({ kind: 'info', message: 'ORIO data refresh requested.' }) } }
      }
    ])
    return dispose
  }
}
