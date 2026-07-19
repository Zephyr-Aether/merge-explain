const API = 'http://127.0.0.1:13920';

async function post(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function loadRepo(path: string) {
  return post('/api/load', { path });
}

export async function analyze(repo: string, branchA: string, branchB: string, target: string) {
  return post('/api/analyze', { repo, branch_a: branchA, branch_b: branchB, target });
}

export async function resolve(repo: string, source: string, target: string, decisions: Record<string, string>, apply: boolean, commit: boolean) {
  return post('/api/resolve', { repo, source, target, decisions, apply, commit });
}

export async function listDirs(path: string) {
  return post('/api/list-dirs', { path });
}

export async function compare(repo: string, refA: string, refB: string, file: string) {
  return post('/api/compare', { repo, ref_a: refA, ref_b: refB, file });
}

export async function pickFolder() {
  return post('/api/pick-folder', {});
}
