import { useState } from 'react'
import './App.css'
import * as api from './api'

interface Conflict { file_path: string; risk: string; branch_a_action: string; branch_b_action: string; suggestion: string; code_snippet?: string }
interface Report { branch_a_summary: any[]; branch_b_summary: any[]; conflicts: Conflict[]; overall_advice: string; reasoning: string }

export default function App() {
  const [repoPath, setRepoPath] = useState('')
  const [branches, setBranches] = useState<string[]>([])
  const [branchA, setBranchA] = useState('')
  const [branchB, setBranchB] = useState('')
  const [target, setTarget] = useState('main')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [step, setStep] = useState(1)
  const [diffRows, setDiffRows] = useState<any[] | null>(null)
  const [diffFile, setDiffFile] = useState('')
  const [commitMode, setCommitMode] = useState(false)
  const [showTree, setShowTree] = useState(false)
  const [treePath, setTreePath] = useState('')
  const [treeHistory, setTreeHistory] = useState<string[]>([''])
  const [treeContent, setTreeContent] = useState<any[]>([])
  const [treeParent, setTreeParent] = useState('')
  const [isGit, setIsGit] = useState(false)

  // ── Load Repo ──
  async function handleLoadRepo(path: string) {
    setLoading(true); setStatus('加载仓库中...')
    try {
      const d = await api.loadRepo(path)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setBranches(d.branches); setStep(2)
      if (!branchA && d.branches.length > 0) setBranchA(d.branches[0])
      if (!branchB && d.branches.length > 1) setBranchB(d.branches[1])
      setStatus(`✅ ${d.branches.length} 个分支`)
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  // ── Browse Folder ──
  async function browseFolder() {
    try {
      const d = await api.pickFolder()
      if (d.success && d.path) {
        setRepoPath(d.path); handleLoadRepo(d.path)
      } else { openTree() }
    } catch { openTree() }
  }

  // ── Tree Browser ──
  async function openTree() {
    setShowTree(true); setTreeHistory(['']); loadTreeLevel('')
  }
  function closeTree() { setShowTree(false) }
  async function loadTreeLevel(path: string) {
    try {
      const d = await api.listDirs(path || '.')
      if (!d.success) return
      setTreePath(d.current)
      setIsGit(d.is_git)
      setTreeParent(d.parent || '')
      setTreeContent(d.dirs)
    } catch {}
  }
  function goTreeUp() {
    if (treeHistory.length < 2) return
    const h = [...treeHistory]; h.pop()
    setTreeHistory(h)
    loadTreeLevel(h[h.length - 1] || '')
  }
  function enterDir(name: string) {
    const current = treeHistory[treeHistory.length - 1]
    const full = current ? current + '/' + name : name
    setTreeHistory([...treeHistory, full])
    loadTreeLevel(full)
  }
  function selectTreeDir() {
    setRepoPath(treePath); closeTree(); handleLoadRepo(treePath)
  }

  // ── Analyze ──
  async function handleAnalyze() {
    if (!branchA || !branchB) { setStatus('请选择两个分支'); return }
    setStep(3); setLoading(true); setStatus(`分析 ${branchA} 和 ${branchB} 合入 ${target} 的冲突...`)
    try {
      const d = await api.analyze(repoPath, branchA, branchB, target)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setReport(d.report); setStep(4)
      setStatus(`✅ 分析完成`)
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  // ── Resolve ──
  async function handleResolve() {
    setLoading(true); setStatus(commitMode ? '正在合并提交...' : '正在预览解决...')
    try {
      const d = await api.resolve(repoPath, branchA, target, commitMode, commitMode)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      if (d.report) setReport(d.report)
      setStatus(commitMode ? '✅ 已合并提交' : '✅ 预览完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  // ── Diff Modal ──
  async function openDiff(filePath: string) {
    setDiffRows(null); setDiffFile(filePath)
    try {
      const d = await api.compare(repoPath, target, branchA, filePath)
      if (d.success) setDiffRows(d.rows)
    } catch {}
  }
  function closeDiff() { setDiffRows(null) }

  function escHtml(s: string) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }

  const red = report?.conflicts.filter(c => c.risk === 'red').length || 0
  const yellow = report?.conflicts.filter(c => c.risk === 'yellow').length || 0
  const green = report?.conflicts.filter(c => c.risk === 'green').length || 0

  return (
    <div className="container">
      <header>
        <h1>Merge-Explain</h1>
        <span className="badge">可解释性合并工具</span>
      </header>

      {/* Steps */}
      <div className="steps">
        {[1, 2, 3, 4].map((n, i) => (
          <>
            {i > 0 && <div className="step-line"><div className={`step-line-fill ${step > n ? '' : ''}`} style={{ width: step > i ? '100%' : '0%' }} /></div>}
            <div className={`step-item ${step === n ? 'active' : ''} ${step > n ? 'done' : ''}`} onClick={() => setStep(n)}>
              <div className="step-circle">
                <span className="step-number">{n}</span>
                <span className="step-dot" />
                <svg className="step-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              </div>
              <span className="step-label">{['选择仓库', '选择分支', '分析冲突', '查看结果'][n - 1]}</span>
            </div>
          </>
        ))}
      </div>

      {/* Step 1: Repo */}
      <div className="card">
        <div className="card-title"><span className="step">1</span> 选择仓库</div>
        <div className="row">
          <div className="path-bar" onClick={openTree}>
            <span className="path-icon">📁</span>
            <span className="path-text">{repoPath || '点击选择或粘贴路径...'}</span>
            {repoPath && <span className="path-git">Git</span>}
          </div>
          <button className="btn btn-secondary btn-sm" onClick={browseFolder}>选择文件夹</button>
          <button className="btn btn-primary btn-sm" disabled={!repoPath} onClick={() => handleLoadRepo(repoPath)}>加载</button>
        </div>
      </div>

      {/* Step 2: Branches */}
      {branches.length > 0 && (
        <div className="card">
          <div className="card-title"><span className="step">2</span> 选择分支</div>
          <div className="row">
            <div className="field">
              <label>特性分支 A</label>
              <select value={branchA} onChange={e => setBranchA(e.target.value)}>
                {branches.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div className="field">
              <label>特性分支 B</label>
              <select value={branchB} onChange={e => setBranchB(e.target.value)}>
                {branches.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div className="field" style={{ minWidth: 100, flex: 0.5 }}>
              <label>目标</label>
              <select value={target} onChange={e => setTarget(e.target.value)}>
                <option value="main">main</option>
                <option value="master">master</option>
              </select>
            </div>
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading}>🔍 分析冲突</button>
          </div>
        </div>
      )}

      {/* Status */}
      {status && <div className="status-bar">{loading && <div className="spinner" />}{status}</div>}

      {/* Results */}
      {report && (
        <>
          <div className="summary-row">
            <div className="summary-card"><div className="num" style={{ color: 'var(--danger)' }}>{red}</div><div className="lbl">🔴 必须人工</div></div>
            <div className="summary-card"><div className="num" style={{ color: 'var(--warning)' }}>{yellow}</div><div className="lbl">🟡 建议审查</div></div>
            <div className="summary-card"><div className="num" style={{ color: 'var(--success)' }}>{green}</div><div className="lbl">🟢 自动合并</div></div>
            <div className="summary-card"><div className="num">{report.overall_advice === 'auto_merge' ? '✅' : report.overall_advice === 'blocked' ? '🚫' : '⚠️'}</div><div className="lbl">{report.overall_advice}</div></div>
          </div>

          {report.conflicts.length === 0 ? (
            <div className="result-box" style={{ background: 'rgba(63,185,80,.1)', borderColor: 'rgba(63,185,80,.2)', color: 'var(--success)' }}>✅ 未检测到冲突</div>
          ) : (
            <>
              {report.conflicts.map((c, i) => (
                <div className="conflict-card" key={i}>
                  <div className="conflict-hd" onClick={e => (e.currentTarget as HTMLElement).classList.toggle('open')}>
                    <span className={`dot dot-${c.risk}`} />
                    <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>{c.file_path}</span>
                  </div>
                  <div className="conflict-bd">
                    <div className="action-row"><span className="label">Branch A</span><span>{c.branch_a_action}</span></div>
                    <div className="action-row"><span className="label">Branch B</span><span>{c.branch_b_action}</span></div>
                    {c.code_snippet && <div className="code-block">{escHtml(c.code_snippet)}</div>}
                    <div className="result-box">💡 {c.suggestion}</div>
                    <button className="btn btn-secondary btn-sm mt-8" onClick={() => openDiff(c.file_path)}>📊 查看 Diff</button>
                  </div>
                </div>
              ))}
              <div className="mt-12">
                <button className="btn btn-danger" onClick={handleResolve} disabled={loading}>🤖 自动解决冲突</button>
                <label style={{ marginLeft: 12, fontSize: 12, color: 'var(--text2)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={commitMode} onChange={e => setCommitMode(e.target.checked)} /> 应用修改并提交合并
                </label>
              </div>
            </>
          )}
        </>
      )}

      <footer>Merge-Explain · 先理解，再合并</footer>

      {/* Tree Browser Modal */}
      {showTree && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
          onClick={e => { if (e.target === e.currentTarget) closeTree() }}>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', width: 520, maxHeight: 480, display: 'flex', flexDirection: 'column', boxShadow: '0 8px 24px rgba(0,0,0,.4)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>选择仓库目录</h3>
              <span style={{ cursor: 'pointer', color: 'var(--text3)' }} onClick={closeTree}>✕</span>
            </div>
            <div style={{ padding: '10px 14px', flex: 1, overflowY: 'auto' }}>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>{treePath || '/'}</div>
              {treeParent && <div className="dropdown-item" onClick={goTreeUp}>📂 ..</div>}
              {treeContent.map((dir, i) => (
                <div key={i} className="dropdown-item" onClick={() => enterDir(dir)}>📁 {dir}</div>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '12px 18px', borderTop: '1px solid var(--border)' }}>
              <button className="btn btn-secondary btn-sm" onClick={closeTree}>取消</button>
              <button className="btn btn-primary btn-sm" disabled={!isGit} onClick={selectTreeDir}>选择此目录</button>
            </div>
          </div>
        </div>
      )}

      {/* Diff Modal */}
      {diffRows !== null && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
          onClick={e => { if (e.target === e.currentTarget) closeDiff() }}>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', width: '90vw', maxWidth: 1000, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>{diffFile}</h3>
              <span style={{ cursor: 'pointer', color: 'var(--text3)' }} onClick={closeDiff}>✕</span>
            </div>
            <div style={{ padding: 6, flex: 1, overflow: 'auto' }}>
              <div className="diff-wrapper">
                <table className="diff-table">
                  <thead><tr><th style={{ width: 48 }}>#</th><th style={{ width: '50%' }}>{target}</th><th style={{ width: 48 }}>#</th><th style={{ width: '50%' }}>{branchA}</th></tr></thead>
                  <tbody>
                    {diffRows.map((r, i) => {
                      const cls = r.t === 'eq' ? '' : r.t === 'dl' ? 'del' : r.t === 'ad' ? 'add' : 'rep'
                      return (
                        <tr key={i} className={cls}>
                          <td className="dn">{r.na || ''}</td>
                          <td className="dc">{escHtml(r.la)}</td>
                          <td className="dn">{r.nb || ''}</td>
                          <td className="dc">{escHtml(r.lb)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
