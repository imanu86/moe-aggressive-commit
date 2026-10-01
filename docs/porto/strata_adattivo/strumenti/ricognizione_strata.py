"""Fotografa upstream, PR aperte e fork (ramo predefinito), solo letture GitHub API."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

REPO = "Niko1221/Strata"


def api(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=90,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:400])
    return json.loads(result.stdout)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    a = parser.parse_args()
    a.out.mkdir(parents=True, exist_ok=a.resume)
    def save(name, value):
        (a.out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    repo = api("repos/" + REPO)
    head = (json.loads((a.out / "upstream_head.json").read_text(encoding="utf-8")) if a.resume
            else api("repos/" + REPO + "/commits/main"))
    save("upstream_head.json", head)
    metadata = (json.loads((a.out / "metadata.json").read_text(encoding="utf-8")) if a.resume else
                {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                "repo": REPO, "forks_count_at_start": repo["forks_count"], "main_sha": head["sha"],
                "scope": "all paginated accessible direct forks, default branch comparison and open PR metadata; other fork branches not enumerated"})
    save("metadata.json", metadata)
    pulls = (json.loads((a.out / "pulls_open.json").read_text(encoding="utf-8")) if a.resume else
             api("repos/" + REPO + "/pulls?state=open&per_page=100"))
    save("pulls_open.json", pulls)
    print("UPSTREAM", head["sha"], head["commit"]["message"].splitlines()[0], "OPEN_PRS", len(pulls), flush=True)
    forks = json.loads((a.out / "forks.json").read_text(encoding="utf-8")) if a.resume else []
    if not a.resume:
        for page in range(1, 20):
            batch = api(f"repos/{REPO}/forks?per_page=100&sort=newest&page={page}")
            forks.extend(batch)
            if len(batch) < 100:
                break
    save("forks.json", forks)
    print("FORKS", len(forks), flush=True)
    detail_dir = a.out / "fork_comparisons"
    detail_dir.mkdir(exist_ok=True)
    parts = a.out / "fork_status_parts"
    parts.mkdir(exist_ok=True)
    def compare(fork):
        name = fork["full_name"]
        filename = name.replace("/", "__") + ".json"
        if a.resume and (parts / filename).exists():
            return json.loads((parts / filename).read_text(encoding="utf-8")), None
        target = fork["owner"]["login"] + ":" + fork["default_branch"]
        row = {"fork": name, "branch": fork["default_branch"], "pushed_at": fork["pushed_at"],
               "stars": fork["stargazers_count"], "url": fork["html_url"]}
        try:
            comparison = (json.loads((detail_dir / filename).read_text(encoding="utf-8"))
                          if a.resume and (detail_dir / filename).exists() else
                          api(f"repos/{REPO}/compare/{head['sha']}...{quote(target, safe=':')}"))
            row.update(ahead_by=comparison["ahead_by"], behind_by=comparison["behind_by"],
                       status=comparison["status"],
                       commits=[{"sha": c["sha"], "message": c["commit"]["message"],
                                 "url": c["html_url"]} for c in comparison.get("commits", [])],
                       files=[f["filename"] for f in comparison.get("files", [])])
            (parts / filename).write_text(json.dumps(row, indent=2), encoding="utf-8")
            if row["ahead_by"] > 0:
                (detail_dir / filename).write_text(json.dumps(comparison, indent=2), encoding="utf-8")
            return row, None
        except Exception as error:
            row["error"] = str(error)
            (parts / filename).write_text(json.dumps(row, indent=2), encoding="utf-8")
            return row, None
    rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(compare, fork) for fork in forks]
        for future in as_completed(futures):
            row, detail = future.result()
            rows.append(row)
            if row.get("ahead_by", 0) > 0:
                print("AHEAD", row["fork"], row["ahead_by"], row["behind_by"],
                      [c["message"].splitlines()[0][:100] for c in row["commits"][:3]], flush=True)
            if len(rows) % 40 == 0:
                print("CHECKED", len(rows), "/", len(forks), flush=True)
    rows.sort(key=lambda r: r["fork"].lower())
    save("fork_status.json", rows)
    save("fork_ahead.json", [r for r in rows if r.get("ahead_by", 0) > 0])
    metadata.update(forks_checked=len(rows), ahead_forks=sum(r.get("ahead_by", 0) > 0 for r in rows),
                    comparison_errors=sum("error" in r for r in rows))
    save("metadata.json", metadata)
    print("DONE", json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()
