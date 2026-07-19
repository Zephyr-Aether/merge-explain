import React, { useState } from 'react'
import * as api from './api'

import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  CheckCircle2, AlertTriangle, AlertCircle, Loader2,
  ArrowLeftRight, FolderOpen, GitBranch, Search, FileCode2,
} from 'lucide-react'

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
  const [diffData, setDiffData] = useState<{file:string;rowsA:any[];rowsB:any[];labelA:string;labelB:string}|null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [showTree, setShowTree] = useState(false)
  const [treePath, setTreePath] = useState('')
  const [treeHistory, setTreeHistory] = useState<string[]>([''])
  const [treeContent, setTreeContent] = useState<any[]>([])
  const [treeParent, setTreeParent] = useState('')
  const [isGit, setIsGit] = useState(false)

  function swapBranches() {
    const tmp = branchA
    setBranchA(branchB)
    setBranchB(tmp)
  }

  async function handleLoadRepo(path: string) {
    setLoading(true); setStatus('加载仓库中...')
    try {
      const d = await api.loadRepo(path)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setBranches(d.branches); setStep(2)
      if (!target || target === 'main') {
        const detected = ['main', 'master', 'develop'].find(b => d.branches.includes(b))
        if (detected && detected !== target) setTarget(detected)
      }
      setStatus('✅ ' + d.branches.length + ' 个分支')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  async function browseFolder() {
    try {
      const d = await api.pickFolder()
      if (d.success && d.path) { setRepoPath(d.path); handleLoadRepo(d.path) }
      else { openTree() }
    } catch { openTree() }
  }

  async function openTree() { setShowTree(true); setTreeHistory(['']); loadTreeLevel('') }
  function closeTree() { setShowTree(false) }
  async function loadTreeLevel(path: string) {
    try {
      const d = await api.listDirs(path || '.')
      if (!d.success) return
      setTreePath(d.current); setIsGit(d.is_git); setTreeParent(d.parent || '')
      setTreeContent(d.dirs)
    } catch {}
  }
  function goTreeUp() {
    if (treeHistory.length < 2) return
    const h = [...treeHistory]; h.pop()
    setTreeHistory(h); loadTreeLevel(h[h.length - 1] || '')
  }
  function enterDir(name: string) {
    const current = treeHistory[treeHistory.length - 1]
    const full = current ? current + '/' + name : name
    setTreeHistory([...treeHistory, full]); loadTreeLevel(full)
  }
  function selectTreeDir() { setRepoPath(treePath); closeTree(); handleLoadRepo(treePath) }

  async function handleAnalyze() {
    if (!branchA || !branchB) { setStatus('请选择两个分支'); return }
    setStep(3); setLoading(true); setStatus('分析 ' + branchA + ' 和 ' + branchB + ' 合入 ' + target + ' 的冲突...')
    try {
      const d = await api.analyze(repoPath, branchA, branchB, target)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setReport(d.report); setStep(4)
      setStatus('✅ 分析完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  async function handleResolve() {
    setLoading(true); setStatus('正在生成预览代码...')
    try {
      const d = await api.resolve(repoPath, branchA, target, false, false)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      if (d.report) setReport(d.report)
      setStatus('✅ 预览完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  function renderDiffRows(rows: any[]) {
    const out: { key: number; marker: string; num: string; content: string; isDel: boolean; isAdd: boolean }[] = []
    let k = 0
    for (const r of rows) {
      if (r.t === 'rp') {
        out.push({ key: k++, marker: '-', num: String(r.na || ''), content: r.la, isDel: true, isAdd: false })
        out.push({ key: k++, marker: '+', num: String(r.nb || ''), content: r.lb, isDel: false, isAdd: true })
      } else if (r.t === 'dl') {
        out.push({ key: k++, marker: '-', num: String(r.na || ''), content: r.la, isDel: true, isAdd: false })
      } else if (r.t === 'ad') {
        out.push({ key: k++, marker: '+', num: String(r.nb || ''), content: r.lb, isDel: false, isAdd: true })
      } else {
        out.push({ key: k++, marker: ' ', num: String(r.na || ''), content: r.la, isDel: false, isAdd: false })
      }
    }
    return out
  }

  async function openDiff(filePath: string) {
    setDiffData(null); setDiffLoading(true)
    try {
      const [ra, rb] = await Promise.all([
        api.compare(repoPath, target, branchA, filePath),
        api.compare(repoPath, target, branchB, filePath),
      ])
      if (ra.success || rb.success) {
        setDiffData({
          file: filePath,
          rowsA: ra.success ? ra.rows : [],
          rowsB: rb.success ? rb.rows : [],
          labelA: branchA,
          labelB: branchB,
        })
      }
    } catch {}
    finally { setDiffLoading(false) }
  }
  function closeDiff() { setDiffData(null) }

  function escHtml(s: string) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }

  const red = report?.conflicts.filter(c => c.risk === 'red').length || 0
  const yellow = report?.conflicts.filter(c => c.risk === 'yellow').length || 0
  const green = report?.conflicts.filter(c => c.risk === 'green').length || 0

  const riskIcon = (r: string) => {
    if (r === 'red') return <AlertCircle className="h-4 w-4 text-destructive" />
    if (r === 'yellow') return <AlertTriangle className="h-4 w-4 text-warning" />
    return <CheckCircle2 className="h-4 w-4 text-success" />
  }

  const riskLabel = (r: string) => {
    if (r === 'red') return '必须人工'
    if (r === 'yellow') return '建议审查'
    return '自动合并'
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto max-w-5xl px-4 py-8">
        {/* Header */}
        <header className="flex items-center gap-3 mb-4 pb-3 border-b border-border">
          <GitBranch className="h-5 w-5 text-accent-custom" />
          <h1 className="text-lg font-semibold">Merge-Explain</h1>
          <Badge variant="secondary" className="text-[10px] px-2 py-0">可解释性合并工具</Badge>
        </header>

        {/* Steps */}
        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="flex items-center">
              {[
                { n: 1, label: '选择仓库' },
                { n: 2, label: '选择分支' },
                { n: 3, label: '分析冲突' },
                { n: 4, label: '查看结果' },
              ].map((s, i) => (
                <React.Fragment key={s.n}>
                  {i > 0 && <Separator className={`flex-1 h-[2px] ${step > i ? 'bg-accent-custom' : 'bg-muted'}`} />}
                  <button
                    onClick={() => setStep(s.n)}
                    className="flex flex-col items-center gap-1.5 shrink-0 px-3 py-1 transition-colors"
                  >
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border-2
                      ${step >= s.n ? 'bg-accent-custom border-accent-custom text-white' : 'border-muted-foreground/30 text-muted-foreground'}
                      ${step === s.n ? 'shadow-[0_0_0_4px_rgba(124,77,255,0.2)]' : ''}
                    `}>
                      {step > s.n ? <CheckCircle2 className="h-4 w-4" /> : s.n}
                    </div>
                    <span className={`text-[10px] whitespace-nowrap ${step >= s.n ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {s.label}
                    </span>
                  </button>
                </React.Fragment>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Step 1: Repo */}
        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground flex items-center gap-2">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-semibold text-muted-foreground">1</span>
              选择仓库
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 items-end">
              <div
                className="flex items-center gap-2 flex-1 px-3 py-2 bg-muted/50 border border-border rounded-md cursor-pointer hover:border-accent-custom transition-colors min-h-[36px]"
                onClick={openTree}
              >
                <FolderOpen className="h-4 w-4 text-warning shrink-0" />
                <span className="text-xs flex-1 truncate">{repoPath || '点击选择或粘贴路径...'}</span>
                {repoPath && <Badge className="text-[9px] px-1.5 py-0 h-4 bg-success text-white">Git</Badge>}
              </div>
              <Button variant="secondary" size="sm" onClick={browseFolder}>选择文件夹</Button>
              <Button size="sm" disabled={!repoPath} onClick={() => handleLoadRepo(repoPath)}>加载</Button>
            </div>
          </CardContent>
        </Card>

        {/* Step 2: Branches */}
        {branches.length > 0 && (
          <Card className="mb-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground flex items-center gap-2">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-semibold text-muted-foreground">2</span>
                选择分支
                <span className="text-[10px] font-normal text-muted-foreground/60 ml-auto">{branches.length} 个分支</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <label className="block text-[11px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">分支 A</label>
                    <Select value={branchA} onValueChange={v => setBranchA(v || "")}>
                      <SelectTrigger className="h-10 text-sm w-full">
                        <SelectValue placeholder="选择分支" />
                      </SelectTrigger>
                      <SelectContent className="overflow-x-auto">
                        {branches.filter(b => b !== branchB).map(b => (
                          <SelectItem key={b} value={b} className="text-sm">{b}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <button
                    onClick={swapBranches}
                    className="self-end p-1.5 rounded-md hover:bg-muted transition-colors cursor-pointer shrink-0"
                    title="交换 A 和 B"
                  >
                    <ArrowLeftRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <div className="flex-1">
                    <label className="block text-[11px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">分支 B</label>
                    <Select value={branchB} onValueChange={v => setBranchB(v || "")}>
                      <SelectTrigger className="h-10 text-sm w-full">
                        <SelectValue placeholder="选择分支" />
                      </SelectTrigger>
                      <SelectContent className="overflow-x-auto">
                        {branches.filter(b => b !== branchA).map(b => (
                          <SelectItem key={b} value={b} className="text-sm">{b}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-28">
                    <label className="block text-[11px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">目标</label>
                    <Select value={target} onValueChange={v => setTarget(v || "main")}>
                      <SelectTrigger className="h-10 text-sm w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="main" className="text-sm">main</SelectItem>
                        <SelectItem value="master" className="text-sm">master</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="pt-5">
                    <Button onClick={handleAnalyze} disabled={loading || !branchA || !branchB || branchA === branchB} className="gap-1.5 h-10">
                      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      分析冲突
                    </Button>
                  </div>
                  {branchA && branchB && branchA === branchB && (
                    <div className="text-[10px] text-destructive pt-5">两个分支不能相同</div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Status */}
        {status && (
          <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 border border-border rounded-md mb-3 text-xs">
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent-custom" />}
            {status}
          </div>
        )}

        {/* Results */}
        {report && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              {[
                { num: red, label: '需人工介入', icon: <AlertCircle className="h-4 w-4 text-destructive" />, color: 'text-destructive' },
                { num: yellow, label: '建议审查', icon: <AlertTriangle className="h-4 w-4 text-warning" />, color: 'text-warning' },
                { num: green, label: '自动合并', icon: <CheckCircle2 className="h-4 w-4 text-success" />, color: 'text-success' },
                { num: report.overall_advice, label: '建议', icon: null, color: '' },
              ].map((item, i) => (
                <Card key={i}>
                  <CardContent className="p-3 text-center">
                    {item.icon && <div className="mb-0.5">{item.icon}</div>}
                    <div className={`text-xl font-bold ${item.color}`}>
                      {typeof item.num === 'number' ? item.num : item.num === 'auto_merge' ? '✅' : item.num === 'blocked' ? '🚫' : '⚠️'}
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{item.label}</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {report.conflicts.length === 0 ? (
              <div className="px-4 py-3 rounded-md bg-success/10 border border-success/20 text-success text-xs">✅ 未检测到冲突</div>
            ) : (
              <>
                {report.conflicts.map((c, i) => (
                  <Card key={i} className="mb-2 overflow-hidden">
                    <button
                      className="flex items-center gap-2 w-full px-3 py-2.5 bg-card hover:bg-muted/50 transition-colors text-left"
                      onClick={e => {
                        const el = e.currentTarget.nextElementSibling
                        if (el) el.classList.toggle('hidden')
                      }}
                    >
                      {riskIcon(c.risk)}
                      <span className="flex-1 text-xs font-medium truncate">{c.file_path}</span>
                    </button>
                    <div className="hidden border-t border-border px-3 py-3 bg-muted/30 text-xs space-y-2">
                      <div className="flex gap-2">
                        <span className="text-muted-foreground shrink-0 w-[60px]">分支 A</span>
                        <span>{c.branch_a_action}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-muted-foreground shrink-0 w-[60px]">分支 B</span>
                        <span>{c.branch_b_action}</span>
                      </div>
                      {c.code_snippet && (
                        <ScrollArea className="h-24">
                          <pre className="bg-background border border-muted rounded p-2 text-[11px] leading-relaxed overflow-x-auto whitespace-pre font-mono">{escHtml(c.code_snippet)}</pre>
                        </ScrollArea>
                      )}
                      <div className="px-2.5 py-2 rounded bg-accent/10 border border-accent/20 text-accent-custom">💡 {c.suggestion}</div>
                      <Button variant="secondary" size="sm" onClick={() => openDiff(c.file_path)}>
                        <FileCode2 className="h-3 w-3 mr-1" />
                        查看 Diff
                      </Button>
                    </div>
                  </Card>
                ))}
                {red === 0 && (
                  <div className="mt-3">
                    <Button variant="destructive" onClick={handleResolve} disabled={loading}>
                      {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                      自动解决冲突
                    </Button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        <footer className="text-center py-8 text-[11px] text-muted-foreground">Merge-Explain · 先理解，再合并</footer>
      </div>

      {/* Tree Browser Dialog */}
      <Dialog open={showTree} onOpenChange={setShowTree}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">选择仓库目录</DialogTitle>
          </DialogHeader>
          <div className="text-[10px] text-muted-foreground mb-2">{treePath || '/'}</div>
          <ScrollArea className="max-h-[300px]">
            {treeParent && (
              <button className="w-full text-left px-2 py-1.5 text-xs hover:bg-muted rounded cursor-pointer" onClick={goTreeUp}>
                📂 ..
              </button>
            )}
            {treeContent.map((dir, i) => (
              <button key={i} className="w-full text-left px-2 py-1.5 text-xs hover:bg-muted rounded cursor-pointer" onClick={() => enterDir(dir)}>
                📁 {dir}
              </button>
            ))}
          </ScrollArea>
          <div className="flex justify-end gap-2 mt-3">
            <Button variant="secondary" size="sm" onClick={closeTree}>取消</Button>
            <Button size="sm" disabled={!isGit} onClick={selectTreeDir}>选择此目录</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Diff Dialog */}
      <Dialog open={diffData !== null || diffLoading} onOpenChange={o => { if (!o) closeDiff() }}>
        <DialogContent className="max-w-[95vw] lg:max-w-[1200px] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-sm truncate">{diffData?.file || '加载中...'}</DialogTitle>
          </DialogHeader>
          {diffLoading && !diffData && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {diffData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 flex-1 min-h-0">
              {[diffData.labelA, diffData.labelB].map((label, idx) => {
                const rows = idx === 0 ? diffData.rowsA : diffData.rowsB
                const unified = renderDiffRows(rows)
                return (
                  <div key={idx} className="flex flex-col min-w-0 border border-border rounded-md overflow-hidden">
                    <div className="text-[10px] text-muted-foreground font-medium px-2.5 py-1.5 bg-muted/50 border-b border-border">
                      {target} ← <span className="text-foreground">{label}</span>
                    </div>
                    <ScrollArea className="flex-1 max-h-[60vh]">
                      <table className="w-full border-collapse font-mono text-[11px] leading-[1.6]">
                        <tbody>
                          {unified.map(r => (
                            <tr key={r.key} className={r.isDel ? 'bg-red-950/15' : r.isAdd ? 'bg-green-950/15' : ''}>
                              <td className={`w-5 text-center select-none text-[10px] ${
                                r.isDel ? 'text-red-400' : r.isAdd ? 'text-green-400' : 'text-muted-foreground/40'
                              }`}>{r.marker}</td>
                              <td className="w-10 text-right text-muted-foreground/50 text-[10px] px-1 py-0 select-none">{r.num}</td>
                              <td className="px-2.5 py-0 whitespace-pre overflow-x-auto">{escHtml(r.content)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </ScrollArea>
                  </div>
                )
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
