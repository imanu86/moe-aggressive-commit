import json, re, time, urllib.request, urllib.parse

UA = {'User-Agent': 'curl/8.5', 'Accept': 'application/json'}


def get(url, headers=UA, raw=False):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    return data.decode('utf-8', 'replace') if raw else json.loads(data.decode('utf-8'))


# ---------- 1) HF: tutti i derivati V4.1 ----------
seen = {}
for q in ['V4.1-Flash', 'V41-Flash', 'DeepSeek-V4.1', 'dsv41', 'deepseek-v41', 'V4.1-Flash-GGUF']:
    url = 'https://huggingface.co/api/models?' + urllib.parse.urlencode(
        {'search': q, 'sort': 'createdAt', 'direction': '-1', 'limit': '200', 'full': 'true'})
    try:
        for m in get(url):
            seen[m['id']] = m
    except Exception as e:
        print('ERR search', q, e)

print('=== repo trovati:', len(seen))
gguf_repos = []
for mid, m in sorted(seen.items(), key=lambda kv: kv[1].get('createdAt', ''), reverse=True):
    tags = m.get('tags', [])
    base = [t for t in tags if t.startswith('base_model:') and 'V4.1' in t]
    files = [s['rfilename'] for s in m.get('siblings', [])]
    ggufs = [f for f in files if f.endswith('.gguf')]
    iq2 = [f for f in ggufs if re.search(r'iq2', f, re.I)]
    is_gguf = bool(ggufs) or 'gguf' in tags
    print('%-78s %s dl=%-5s likes=%-4s %s gguf=%d iq2=%d %s' % (
        mid, (m.get('createdAt') or '')[:16], m.get('downloads'), m.get('likes'),
        'GGUF' if is_gguf else '    ', len(ggufs), len(iq2), 'base' if base else ''))
    if is_gguf and ('v4.1' in mid.lower() or 'v41' in mid.lower() or base):
        gguf_repos.append(mid)

# ---------- 2) dimensioni per quant dei repo GGUF ----------
for mid in gguf_repos:
    try:
        t = get('https://huggingface.co/api/models/%s/tree/main?recursive=1' % mid)
    except Exception as e:
        print('ERR tree', mid, e)
        continue
    groups = {}
    for x in t:
        if x.get('type') != 'file' or not x['path'].endswith('.gguf'):
            continue
        key = re.sub(r'-\d{5}-of-(\d{5})\.gguf$', r' [split \1]', x['path'])
        g = groups.setdefault(key, [0, 0])
        g[0] += x.get('size') or 0
        g[1] += 1
    print('\n=== %s' % mid)
    for k, (sz, n) in sorted(groups.items()):
        print('   %-95s parti=%-2d %8.2f GiB' % (k, n, sz / 2**30))
    try:
        rd = get('https://huggingface.co/%s/resolve/main/README.md' % mid, raw=True)
        body = re.sub(r'^---.*?---', '', rd, flags=re.S).strip()
        print('   --- README (%d char) ---' % len(rd))
        print('   ' + body[:2500].replace('\n', '\n   '))
    except Exception as e:
        print('   README: ERR', e)

# ---------- 3) GitHub: runtime ----------
GH = {'User-Agent': 'curl/8.5', 'Accept': 'application/vnd.github+json'}
for q in ['repo:ggml-org/llama.cpp V4.1', 'repo:ggml-org/llama.cpp deepseek41', 'repo:ggml-org/llama.cpp engram',
          'repo:ikawrakow/ik_llama.cpp V4.1', 'repo:kvcache-ai/ktransformers V4.1']:
    url = 'https://api.github.com/search/issues?' + urllib.parse.urlencode(
        {'q': q + ' created:>2026-09-09', 'sort': 'created', 'order': 'desc', 'per_page': '15'})
    try:
        d = get(url, GH)
        print('\n=== GH %s -> %s' % (q, d.get('total_count')))
        for i in d.get('items', []):
            print('   #%s %s %s pr=%s | %s' % (i['number'], i['state'], i['created_at'][:16], 'pull_request' in i, i['title']))
    except Exception as e:
        print('ERR gh', q, e)
    time.sleep(3)
try:
    pr = get('https://api.github.com/repos/ggml-org/llama.cpp/pulls/28696', GH)
    print('\n=== PR 28696: state=%s draft=%s merged=%s updated=%s commits=%s +%s -%s files=%s' % (
        pr['state'], pr['draft'], pr['merged'], pr['updated_at'], pr['commits'], pr['additions'], pr['deletions'], pr['changed_files']))
except Exception as e:
    print('ERR pr', e)
