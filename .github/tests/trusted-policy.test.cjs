const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const workflow = fs.readFileSync('.github/workflows/trusted-branch-policy.yml', 'utf8');
const body = workflow.match(/script: \|\r?\n([\s\S]*?)      - name: Evaluate/)[1];
const script = body.split(/\r?\n/).map(line => line.replace(/^ {12}/, '')).join('\n');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFunction('github', 'context', 'require', 'Buffer', script);

function fixture({ source = 'dev', target = 'main', evidencePath = 'docs/report.md', mode = '100644', size = 10 } = {}) {
  const pr = {
    state: 'open',
    head: { ref: source, sha: 'current-sha', repo: { full_name: 'baolong06/recommender_system' } },
    base: { ref: target },
  };
  const written = new Map();
  const fetched = [];
  const contents = {
    'docs/research-readiness.json': JSON.stringify({ evidence: {
      data_manifest: evidencePath, split_manifest: evidencePath,
      results_manifest: evidencePath, report: evidencePath,
    } }),
    'configs/protocol.toml': '[research]\nstatus="approved"\nopen_decisions=[]',
    [evidencePath]: 'untrusted content; never executed',
    'src/recommender/branch_policy.py': 'raise RuntimeError("PR code must not run")',
  };
  const tree = Object.keys(contents).map(file => ({
    path: file, type: 'blob', sha: file,
    mode: file === evidencePath ? mode : '100644',
    size: file === evidencePath ? size : contents[file].length,
  }));
  const github = { rest: {
    pulls: { get: async () => ({ data: pr }) },
    git: {
      getTree: async args => {
        assert.equal(args.tree_sha, 'current-sha');
        return { data: { tree, truncated: false } };
      },
      getBlob: async args => {
        fetched.push(args.file_sha);
        return { data: { encoding: 'base64', content: Buffer.from(contents[args.file_sha]).toString('base64') } };
      },
    },
  } };
  const context = {
    repo: { owner: 'baolong06', repo: 'recommender_system' },
    payload: { pull_request: { number: 1, head: { sha: 'current-sha' }, base: { ref: target } } },
  };
  const fakeRequire = name => {
    if (name === 'node:path') return path.posix;
    if (name === 'node:fs/promises') return {
      mkdir: async () => {},
      writeFile: async (file, value) => { written.set(file, value); },
    };
    throw new Error(`Unexpected module: ${name}`);
  };
  return { execute: () => run(github, context, fakeRequire, Buffer), written, fetched, context };
}

test('trusted workflow never checks out or runs PR code', () => {
  assert.match(workflow, /ref: \$\{\{ github\.workflow_sha \}\}/);
  assert.match(workflow, /python -I \.\.\/policy\/src\/recommender\/branch_policy\.py/);
  assert.doesNotMatch(workflow, /pip install|download-artifact|ref:.*head/);
  assert.match(workflow, /types: \[opened, synchronize, reopened, edited, ready_for_review\]/);
});

test('rejects a personal branch retargeted to main before fetching evidence', async () => {
  const probe = fixture({ source: 'bao-long' });
  await assert.rejects(probe.execute, /Only dev/);
  assert.deepEqual(probe.fetched, []);
});

test('dev integration reads current metadata, not PR source files', async () => {
  const probe = fixture({ source: 'bao-long', target: 'dev' });
  await probe.execute();
  assert.deepEqual(probe.fetched, []);
  assert.equal(JSON.parse(probe.written.get('event.json')).pull_request.head.sha, 'current-sha');
});

test('stale queued checks cannot accept a retargeted PR', async () => {
  const probe = fixture({ source: 'bao-long', target: 'dev' });
  probe.context.payload.pull_request.base.ref = 'main';
  await assert.rejects(probe.execute, /newest run/);
});

test('promotion fetches evidence as data and never fetches the PR checker', async () => {
  const probe = fixture();
  await probe.execute();
  assert.ok(probe.written.has('inputs/docs/report.md'));
  assert.ok(!probe.fetched.includes('src/recommender/branch_policy.py'));
});

test('evidence cannot replace trusted event metadata', async () => {
  const probe = fixture({ evidencePath: 'event.json' });
  await probe.execute();
  assert.equal(JSON.parse(probe.written.get('event.json')).pull_request.head.ref, 'dev');
  assert.equal(probe.written.get('inputs/event.json').toString(), 'untrusted content; never executed');
});

for (const evidencePath of ['../policy/checker.py', '/absolute', 'C:\\escape', 'a/../../escape']) {
  test(`rejects evidence path ${evidencePath}`, async () => {
    await assert.rejects(fixture({ evidencePath }).execute, /Invalid evidence path/);
  });
}

test('rejects symlink evidence', async () => {
  await assert.rejects(fixture({ mode: '120000' }).execute, /regular file/);
});

test('rejects oversized evidence before downloading it', async () => {
  await assert.rejects(fixture({ size: 524289 }).execute, /regular file/);
});
