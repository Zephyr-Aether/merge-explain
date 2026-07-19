import React, { useState, useEffect } from 'react'
import * as api from './api'

import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import CodeMirror from '@uiw/react-codemirror'
import { javascript } from '@codemirror/lang-javascript'
import { python } from '@codemirror/lang-python'
import { EditorView, Decoration, ViewPlugin } from '@codemirror/view'
import {
  CheckCircle2, AlertTriangle, AlertCircle, Loader2,
  ArrowLeftRight, FolderOpen, GitBranch, Search, FileCode2, Download, Clock, FileCheck,
} from 'lucide-react'

interface Conflict { file_path: string; risk: string; branch_a_action: string; branch_b_action: string; suggestion: string; code_snippet?: string }
interface ChangeItem { file_path: string; function_name: string; change_desc: string }
interface Report { branch_a_summary: ChangeItem[]; branch_b_summary: ChangeItem[]; conflicts: Conflict[]; overall_advice: string; reasoning: string }

function getLangExt(filePath: string) {
  if (filePath.endsWith('.py')) return python()
  if (filePath.endsWith('.js') || filePath.endsWith('.jsx') || filePath.endsWith('.ts') || filePath.endsWith('.tsx')) return javascript()
  return javascript()
}

function diffHighlightExtension() {
  return ViewPlugin.fromClass(class {
    decorations: any
    constructor(view: EditorView) {
      this.decorations = this.compute(view)
    }
    update(update: any) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.compute(update.view)
      }
    }
    compute(view: EditorView) {
      const deco: any[] = []
      const doc = view.state.doc
      for (let i = 1; i <= doc.lines; i++) {
        const line = doc.line(i)
        if (line.text.startsWith('+')) {
          deco.push(Decoration.line({ class: 'bg-green-950/20' }).range(line.from))
        } else if (line.text.startsWith('-')) {
          deco.push(Decoration.line({ class: 'bg-red-950/20' }).range(line.from))
        }
      }
      return Decoration.set(deco)
    }
  }, {
    decorations: v => v.decorations
  })
}

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
  const [repoHistory, setRepoHistory] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('merge-explain-repos') || '[]') }
    catch { return [] }
  })
  const [expandedConflicts, setExpandedConflicts] = useState<Set<number>>(new Set())
  const [filterRisk, setFilterRisk] = useState<'all' | 'red' | 'yellow' | 'green'>('all')
  const [decisions, setDecisions] = useState<Record<number, string>>({})
  const [previewResult, setPreviewResult] = useState<any>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [diffIndex, setDiffIndex] = useState(0)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Enter' && !loading) {
        if (step === 1 && repoPath) handleLoadRepo(repoPath)
        else if (step === 2 && branchA && branchB && branchA !== branchB) handleAnalyze()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [step, loading, repoPath, branchA, branchB])

  function saveRepoHistory(path: string) {
    const updated = [path, ...repoHistory.filter(r => r !== path)].slice(0, 6)
    setRepoHistory(updated)
    localStorage.setItem("merge-explain-repos", JSON.stringify(updated))
  }

  function exportReport() {
    if (!report) return
    let md = "Merge Conflict Report" + String.fromCharCode(10)
    md += "Branches: " + branchA + " vs " + branchB + " to " + target + String.fromCharCode(10)
    md += "Conflicts: " + report.conflicts.length + " (red " + red + " / yellow " + yellow + " / green " + green + ")" + String.fromCharCode(10)
    md += "Advice: " + report.overall_advice + String.fromCharCode(10) + String.fromCharCode(10)
    report.conflicts.forEach(function(c, i) {
      md += i+1 + ". " + c.file_path + " (" + c.risk + ")" + String.fromCharCode(10)
      md += "  Branch A: " + c.branch_a_action + String.fromCharCode(10)
      md += "  Branch B: " + c.branch_b_action + String.fromCharCode(10)
      md += "  Suggestion: " + c.suggestion + String.fromCharCode(10) + String.fromCharCode(10)
    })
    var blob = new Blob([md], { type: "text/markdown" })
    var url = URL.createObjectURL(blob)
    var a = document.createElement("a")
    a.href = url; a.download = "merge-report.md"; a.click()
    URL.revokeObjectURL(url)
  }

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
      saveRepoHistory(path)

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
      if (d.report.conflicts && d.report.conflicts.length > 0) setExpandedConflicts(new Set(d.report.conflicts.map((_: any, i: number) => i)))
      setStatus('✅ 分析完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  async function handleResolve() {
    setLoading(true); const n = report?.conflicts.length || 0; setStatus('正在生成预览代码 (0/' + n + ')...')
    try {
      const d = await api.resolve(repoPath, branchA, target, decisionsByFile(), false, false)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      if (d.report) setReport(d.report)
      setStatus('✅ 预览完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  function toggleConflict(i: number) {
    setExpandedConflicts(prev => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  function expandAll() {
    setExpandedConflicts(new Set(filteredConflicts.map((_, i) => i)))
  }

  function collapseAll() { setExpandedConflicts(new Set()) }

  function wordDiff(a: string, b: string): { text: string; type: 'same' | 'del' | 'add' }[] {
    if (a === b) return [{ text: a, type: 'same' }]
    if (!a) return b ? [{ text: b, type: 'add' }] : []
    if (!b) return a ? [{ text: a, type: 'del' }] : []
    const tokenize = (s: string) => s.match(/\S+\s*/g) || [s]
    const toksA = tokenize(a), toksB = tokenize(b)
    const m = toksA.length, n = toksB.length
    const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
    for (let i = 1; i <= m; i++)
      for (let j = 1; j <= n; j++)
        dp[i][j] = toksA[i - 1] === toksB[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    const result: { text: string; type: 'same' | 'del' | 'add' }[] = []
    let i = m, j = n
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && toksA[i - 1] === toksB[j - 1]) {
        result.push({ text: toksA[i - 1], type: 'same' }); i--; j--
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        result.push({ text: toksB[j - 1], type: 'add' }); j--
      } else {
        result.push({ text: toksA[i - 1], type: 'del' }); i--
      }
    }
    return result.reverse()
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

  async function openDiff(filePath: string, idx?: number) {
    if (idx !== undefined) setDiffIndex(idx)
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

  const filteredConflicts = report?.conflicts.filter(c => filterRisk === 'all' || c.risk === filterRisk) || []

  function decisionsByFile(): Record<string, string> {
    const byFile: Record<string, string> = {}
    for (const [idx, choice] of Object.entries(decisions)) {
      const c = filteredConflicts[Number(idx)]
      if (c) byFile[c.file_path] = choice
    }
    return byFile
  }

  async function handlePreviewResolve() {
    setLoading(true); setPreviewResult(null); setStatus('正在应用决策...')
    try {
      const byFile = decisionsByFile()
      if (Object.keys(byFile).length === 0) { setStatus('请先选择决议'); return }
      const d = await api.resolve(repoPath, branchA, target, byFile, false, false)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setPreviewResult(d.report); setStatus('✅ 预览完成')
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

  async function handleApplyResolve() {
    if (!previewResult) { setStatus('请先预览合并结果'); return }
    setConfirmOpen(true)
  }

  async function executeApplyResolve() {
    setLoading(true); setStatus('正在写入文件...')
    try {
      const byFile = decisionsByFile()
      const d = await api.resolve(repoPath, branchA, target, byFile, true, false)
      if (!d.success) { setStatus('❌ ' + (d.error || '')); return }
      setStatus('✅ 文件已修改。请运行 git diff 审查变更，确认后手动 git add + git commit')
      setPreviewResult(null)
    } catch (e: any) { setStatus('❌ ' + e.message) }
    finally { setLoading(false) }
  }

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
                      w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all duration-300
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
            {repoHistory.length > 0 && (
              <div className="flex gap-1.5 flex-wrap mt-2">
                <Clock className="h-3 w-3 text-muted-foreground mt-0.5 shrink-0" />
                {repoHistory.map(path => (
                  <button
                    key={path}
                    onClick={() => { setRepoPath(path); handleLoadRepo(path) }}
                    className="max-w-[180px] truncate text-[10px] px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-muted-foreground transition-colors cursor-pointer"
                    title={path}
                  >
                    {path.replace(/^.*\/([^/]+)$/, '$1')}
                  </button>
                ))}
              </div>
            )}
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

        {/* Loading skeleton */}
        {step === 3 && loading && (
          <div className="space-y-2 mb-4">
            {[1,2,3].map(i => (
              <Card key={i} className="overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <div className="w-4 h-4 rounded-full bg-muted animate-pulse" />
                  <div className="h-3 bg-muted rounded animate-pulse flex-1" />
                  <div className="w-3 h-3 bg-muted rounded animate-pulse" />
                </div>
                <div className="border-t border-border px-3 py-3 space-y-2">
                  <div className="h-3 bg-muted rounded animate-pulse w-3/4" />
                  <div className="h-3 bg-muted rounded animate-pulse w-1/2" />
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Results */}
        {report && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              {[
                { num: red, label: '需人工介入', risk: 'red' as const, icon: <AlertCircle className="h-4 w-4 text-destructive" />, color: 'text-destructive' },
                { num: yellow, label: '建议审查', risk: 'yellow' as const, icon: <AlertTriangle className="h-4 w-4 text-warning" />, color: 'text-warning' },
                { num: green, label: '自动合并', risk: 'green' as const, icon: <CheckCircle2 className="h-4 w-4 text-success" />, color: 'text-success' },
                { num: report.overall_advice, label: '建议', risk: null, icon: null, color: '' },
              ].map((item, i) => (
                item.risk ? (
                  <button
                    key={i}
                    onClick={() => setFilterRisk(filterRisk === item.risk ? 'all' : item.risk)}
                    className={`rounded-lg border text-center p-3 transition-all cursor-pointer ${
                      filterRisk === item.risk
                        ? 'border-accent-custom ring-1 ring-accent-custom bg-accent-custom/5'
                        : 'border-border bg-card hover:bg-muted/50'
                    }`}
                  >
                    <div className="mb-0.5">{item.icon}</div>
                    <div className={`text-xl font-bold ${item.color}`}>{item.num}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{item.label}</div>
                  </button>
                ) : (
                  <Card key={i}>
                    <CardContent className="p-3 text-center">
                      <div className={`text-xl font-bold ${item.color}`}>
                        {item.num === 'auto_merge' ? '✅' : item.num === 'blocked' ? '🚫' : '⚠️'}
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">{item.label}</div>
                    </CardContent>
                  </Card>
                )
              ))}
            </div>

            {/* Branch Change Summary */}
            {(report.branch_a_summary.length > 0 || report.branch_b_summary.length > 0) && (
              <Card className="mb-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs text-muted-foreground flex items-center gap-2">
                    <GitBranch className="h-3 w-3" />
                    分支变更摘要
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs space-y-2">
                  {report.branch_a_summary.length > 0 && (
                    <div>
                      <div className="text-[11px] font-medium text-accent-custom mb-1">{branchA}</div>
                      {report.branch_a_summary.map((item, i) => (
                        <div key={i} className="flex gap-1.5 py-0.5 leading-relaxed">
                          <span className="text-muted-foreground/70 shrink-0">{item.file_path}</span>
                          {item.function_name && <><span className="text-muted-foreground/40">·</span><span className="text-foreground/70">{item.function_name}</span></>}
                          <span className="text-muted-foreground/60">- {item.change_desc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {report.branch_b_summary.length > 0 && (
                    <div>
                      <div className="text-[11px] font-medium text-accent-custom mb-1">{branchB}</div>
                      {report.branch_b_summary.map((item, i) => (
                        <div key={i} className="flex gap-1.5 py-0.5 leading-relaxed">
                          <span className="text-muted-foreground/70 shrink-0">{item.file_path}</span>
                          {item.function_name && <><span className="text-muted-foreground/40">·</span><span className="text-foreground/70">{item.function_name}</span></>}
                          <span className="text-muted-foreground/60">- {item.change_desc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {filterRisk !== 'all' && <div className="text-[10px] text-muted-foreground mb-2">筛选: {filterRisk === 'red' ? '需人工介入' : filterRisk === 'yellow' ? '建议审查' : '自动合并'}（{filteredConflicts.length}/{report.conflicts.length}）<button onClick={() => setFilterRisk('all')} className="underline ml-1 cursor-pointer">清除</button></div>}

            {filteredConflicts.length === 0 ? (
              <div className="px-4 py-3 rounded-md bg-muted/30 border border-border text-muted-foreground text-xs">{report.conflicts.length === 0 ? '✅ 未检测到冲突' : '没有匹配筛选条件的冲突'}</div>
            ) : (
              <>
                <div className="flex gap-2 mb-2">
                  <Button variant="ghost" size="sm" onClick={expandAll} className="text-[10px] h-6 px-2">展开全部</Button>
                  <Button variant="ghost" size="sm" onClick={collapseAll} className="text-[10px] h-6 px-2">收起全部</Button>
                  {filterRisk !== 'all' && (
                    <Button variant="ghost" size="sm" onClick={() => setFilterRisk('all')} className="text-[10px] h-6 px-2 text-muted-foreground">清除筛选</Button>
                  )}
                </div>
                {filteredConflicts.map((c, i) => (
                  <Card key={i} className="mb-2 overflow-hidden">
                    <button
                      className="flex items-center gap-2 w-full px-3 py-2.5 bg-card hover:bg-muted/50 transition-colors text-left cursor-pointer"
                      onClick={() => toggleConflict(i)}
                    >
                      {riskIcon(c.risk)}
                      <span className="flex-1 text-xs font-medium truncate">{c.file_path}</span>
                      <span className="text-[9px] text-muted-foreground/40 shrink-0 mr-1">{i + 1}/{filteredConflicts.length}</span>
                      <svg className={`h-3 w-3 text-muted-foreground transition-transform ${expandedConflicts.has(i) ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6"/></svg>
                    </button>
                    {expandedConflicts.has(i) && (
                      <div className="border-t border-border px-3 py-3 bg-muted/30 text-xs space-y-2">
                        <div className="flex gap-2">
                          <span className="text-muted-foreground shrink-0 w-[60px]">分支 A</span>
                          <span>{c.branch_a_action}</span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-muted-foreground shrink-0 w-[60px]">分支 B</span>
                          <span>{c.branch_b_action}</span>
                        </div>
                        {c.code_snippet && (
                          <div className="border border-border rounded overflow-hidden">
                            <CodeMirror
                              value={c.code_snippet}
                              height="100px"
                              theme="dark"
                              extensions={[EditorView.editable.of(false), getLangExt(c.file_path), diffHighlightExtension()]}
                              basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: false, highlightSelectionMatches: false }}
                              className="text-[11px]"
                            />
                          </div>
                        )}
                        <div className="px-2.5 py-2 rounded bg-accent/10 border border-accent/20 text-accent-custom">💡 {c.suggestion}</div>
                        <Button variant="secondary" size="sm" onClick={() => openDiff(c.file_path, i)}>
                          <FileCode2 className="h-3 w-3 mr-1" />
                          查看 Diff
                        </Button>
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          <Button size="sm" variant={decisions[i] === 'a' ? 'default' : 'outline'}
                            onClick={() => setDecisions(d => ({...d, [i]: d[i] === 'a' ? undefined! : 'a'}))}
                            className="h-6 text-[10px]">采用 {branchA}</Button>
                          <Button size="sm" variant={decisions[i] === 'b' ? 'default' : 'outline'}
                            onClick={() => setDecisions(d => ({...d, [i]: d[i] === 'b' ? undefined! : 'b'}))}
                            className="h-6 text-[10px]">采用 {branchB}</Button>
                          <Button size="sm" variant={decisions[i] === 'llm' ? 'default' : 'outline'}
                            onClick={() => setDecisions(d => ({...d, [i]: d[i] === 'llm' ? undefined! : 'llm'}))}
                            className="h-6 text-[10px]">使用建议</Button>
                          {decisions[i] !== undefined && decisions[i] !== 'a' && decisions[i] !== 'b' && decisions[i] !== 'llm' ? (
                            <div className="w-full mt-1">
                              <CodeMirror
                                value={decisions[i]}
                                onChange={val => setDecisions(d => ({...d, [i]: val}))}
                                height="80px"
                                theme="dark"
                                extensions={[getLangExt(c.file_path)]}
                                basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: false, closeBrackets: true }}
                                placeholder="输入合并后的代码..."
                                className="w-full text-[11px] border border-border rounded overflow-hidden"
                              />
                              <Button size="sm" variant="ghost" onClick={() => { const dd = {...decisions}; delete dd[i]; setDecisions(dd) }}
                                className="h-5 text-[9px] text-muted-foreground mt-1">取消编辑</Button>
                            </div>
                          ) : (
                            <Button size="sm" variant="ghost"
                              onClick={() => setDecisions(d => ({...d, [i]: ''}))}
                              className="h-6 text-[10px] text-muted-foreground">手动编辑</Button>
                          )}
                          {decisions[i] && (
                            <Button size="sm" variant="ghost"
                              onClick={() => { const dd = {...decisions}; delete dd[i]; setDecisions(dd) }}
                              className="h-6 text-[10px] text-muted-foreground">撤销</Button>
                          )}
                        </div>
                      </div>
                    )}
                  </Card>
                ))}
                {red === 0 && (
                  <div className="mt-3 flex gap-2">
                    <Button variant="destructive" onClick={handleResolve} disabled={loading}>
                      {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                      自动解决冲突
                    </Button>
                  </div>
                )}
                <div className="mt-2 flex gap-2">
                  <Button variant="outline" size="sm" onClick={exportReport} className="gap-1">
                    <Download className="h-3 w-3" />
                    导出报告
                  </Button>
                </div>
                {previewResult && (
                  <Card className="mb-4 border-accent-custom/30">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs flex items-center gap-2">
                        <FileCheck className="h-3.5 w-3.5 text-success" />
                        预览结果 — {previewResult.resolved_count}/{previewResult.total_conflicts} 个冲突已解决
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs space-y-1 max-h-32 overflow-y-auto">
                      {(previewResult.changes || []).map((ch: any, i: number) => (
                        <div key={i} className="flex gap-2 text-muted-foreground">
                          <span className="shrink-0">{ch.file_path}</span>
                          <span className="text-muted-foreground/50">·</span>
                          <span className="truncate">{ch.explanation}</span>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}
                {Object.keys(decisions).length > 0 && (
                  <div className="mt-3 p-3 border border-border rounded-lg bg-muted/20">
                    <div className="text-xs text-muted-foreground mb-2">{Object.keys(decisions).length} 个冲突已决策</div>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={handlePreviewResolve} disabled={loading} className="gap-1">
                        预览合并结果
                      </Button>
                      <Button variant="default" size="sm" onClick={handleApplyResolve} disabled={loading || !previewResult} className="gap-1">
                        应用修改至文件
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>⚠️ 确认应用修改</AlertDialogTitle>
              <AlertDialogDescription className="text-xs space-y-2">
                <p>此操作将修改以下文件的冲突标记：</p>
                <ul className="list-disc pl-4 text-muted-foreground">
                  {[...new Set((previewResult?.changes || []).map((ch: any) => ch.file_path).filter(Boolean))].map((f: any, i: number) => (
                    <li key={i}>{f as string}</li>
                  ))}
                </ul>
                <div className="mt-2 p-2 rounded bg-warning/10 border border-warning/20 text-warning text-[10px]">
                  修改后<strong>不会</strong>自动提交。请用 <code className="text-foreground">git diff</code> 审查变更，确认后再手动 commit。
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction onClick={() => { setConfirmOpen(false); executeApplyResolve() }}>确认修改</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
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
            {diffData && filteredConflicts.length > 1 && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <Button variant="ghost" size="sm" disabled={diffIndex <= 0}
                  onClick={() => { const prev = filteredConflicts[diffIndex - 1]; if (prev) openDiff(prev.file_path, diffIndex - 1) }}
                  className="h-5 px-1 text-[9px]">上一处</Button>
                <span className="text-[9px] text-muted-foreground tabular-nums">{diffIndex + 1}/{filteredConflicts.length}</span>
                <Button variant="ghost" size="sm" disabled={diffIndex >= filteredConflicts.length - 1}
                  onClick={() => { const next = filteredConflicts[diffIndex + 1]; if (next) openDiff(next.file_path, diffIndex + 1) }}
                  className="h-5 px-1 text-[9px]">下一处</Button>
              </div>
            )}
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
                          {unified.map((r, ri, arr) => {
                            // Check if this row is part of a replace pair
                            const isReplacePair = r.isDel && ri + 1 < arr.length && arr[ri + 1].isAdd
                            const isReplaceSecond = r.isAdd && ri > 0 && arr[ri - 1].isDel

                            if (isReplacePair || isReplaceSecond) {
                              const pairA = isReplacePair ? r : arr[ri - 1]
                              const pairB = isReplacePair ? arr[ri + 1] : r
                              if (ri % 2 === 1) return null  // skip second row (rendered by first)
                              const segs = wordDiff(pairA.content, pairB.content)
                              return (
                                <React.Fragment key={pairA.key}>
                                  <tr className="bg-red-950/15">
                                    <td className="w-5 text-center text-[10px] text-red-400 select-none">-</td>
                                    <td className="w-10 text-right text-muted-foreground/50 text-[10px] px-1 py-0 select-none">{pairA.num}</td>
                                    <td className="px-2.5 py-0 whitespace-pre overflow-x-auto">
                                      {segs.map((s, si) => (
                                        <span key={si} className={
                                          s.type === 'same' ? 'text-red-300/60' :
                                          s.type === 'del' ? 'bg-red-950/30 text-red-300' : ''
                                        }>{escHtml(s.text)}</span>
                                      ))}
                                    </td>
                                  </tr>
                                  <tr className="bg-green-950/15">
                                    <td className="w-5 text-center text-[10px] text-green-400 select-none">+</td>
                                    <td className="w-10 text-right text-muted-foreground/50 text-[10px] px-1 py-0 select-none">{pairB.num}</td>
                                    <td className="px-2.5 py-0 whitespace-pre overflow-x-auto">
                                      {segs.map((s, si) => (
                                        <span key={si} className={
                                          s.type === 'same' ? 'text-green-300/60' :
                                          s.type === 'add' ? 'bg-green-950/30 text-green-300' : ''
                                        }>{escHtml(s.text)}</span>
                                      ))}
                                    </td>
                                  </tr>
                                </React.Fragment>
                              )
                            }

                            return (
                              <tr key={r.key} className={r.isDel ? 'bg-red-950/15' : r.isAdd ? 'bg-green-950/15' : ''}>
                                <td className={`w-5 text-center select-none text-[10px] ${
                                  r.isDel ? 'text-red-400' : r.isAdd ? 'text-green-400' : 'text-muted-foreground/40'
                                }`}>{r.marker}</td>
                                <td className="w-10 text-right text-muted-foreground/50 text-[10px] px-1 py-0 select-none">{r.num}</td>
                                <td className="px-2.5 py-0 whitespace-pre overflow-x-auto">{escHtml(r.content)}</td>
                              </tr>
                            )
                          })}
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
