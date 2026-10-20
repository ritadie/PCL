"""GitHub Actions release orchestration. API credentials stay in GH_TOKEN."""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import zipfile

from prepare_upstream import patch_source, UnsupportedSource

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / ".build-state.json"
UPSTREAM = "Meloong-Git/PCL"


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()


def gh(*args):
    return run("gh", *args)


def latest_channel(repo):
    result = subprocess.run(["gh", "api", f"repos/{repo}/releases/tags/update-channel"], capture_output=True, text=True)
    if result.returncode:
        if "404" in result.stderr:
            return {}
        raise RuntimeError(result.stderr)
    release = json.loads(result.stdout)
    asset = next((a for a in release["assets"] if a["name"] == "channel.json"), None)
    if not asset:
        return {}
    return json.loads(gh("api", "-H", "Accept: application/octet-stream", f"repos/{repo}/releases/assets/{asset['id']}"))


def output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def prepare():
    repo = os.environ["GITHUB_REPOSITORY"]
    if repo.lower() == UPSTREAM.lower():
        raise RuntimeError("This workflow must run in a fork")
    source = ROOT / "_upstream"
    run("git", "clone", "--depth=1", "--recurse-submodules", f"https://github.com/{UPSTREAM}.git", str(source))
    sha = run("git", "-C", str(source), "rev-parse", "HEAD")
    # Script/template/workflow changes receive their own build identity.
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob("scripts/*"), ROOT / ".github/workflows/upstream-release.yml"]):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    build_id = sha[:12] + "-" + digest.hexdigest()[:12]
    previous = latest_channel(repo)
    if previous.get("build_id") == build_id and os.environ.get("FORCE_BUILD") != "true":
        output("status", "unchanged")
        return
    state = {"schema": 1, "repository": repo, "upstream": UPSTREAM, "upstream_sha": sha, "build_id": build_id}
    try:
        patch_source(source, repo, build_id)
    except UnsupportedSource as ex:
        state.update(status="blocked", reason=str(ex))
    else:
        state.update(status="ready", tag="fork-" + build_id)
        # Embed user-provided API credentials without putting them in shell code or logs.
        secret = source / "Plain Craft Launcher 2/Modules/ModSecret.vb"
        text = secret.read_text(encoding="utf-8-sig")
        for env, field in [("PCL_MS_CLIENT_ID", "OAuthClientId"), ("PCL_CURSEFORGE_API_KEY", "CurseForgeAPIKey")]:
            value = os.environ.get(env, "").replace('"', '""').replace("\r", "").replace("\n", "")
            if value:
                text = text.replace(f'Public {field} As String = If(Environment.GetEnvironmentVariable("{env}"), "")',
                                    f'Public {field} As String = If(Environment.GetEnvironmentVariable("{env}"), "{value}")')
        # Source asset is created before credentials are embedded.
        with zipfile.ZipFile(ROOT / "patched-source.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for folder, dirs, files in os.walk(source):
                dirs[:] = [d for d in dirs if d not in (".git", "bin", "obj")]
                for name in files:
                    if name != ".git":
                        path = pathlib.Path(folder) / name
                        z.write(path, path.relative_to(source))
        secret.write_text(text, encoding="utf-8-sig")
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    output("status", state["status"])


def publish():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    repo = state["repository"]
    if state["status"] == "ready":
        source = ROOT / "_upstream/Plain Craft Launcher 2/bin"
        exe = source / "Plain Craft Launcher 2.exe"
        if not exe.is_file():
            raise RuntimeError("Build executable missing; channel will not be changed")
        archive = ROOT / "PCL-fork.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for path in source.iterdir():
                if path.is_file() and path.suffix.lower() not in (".pdb", ".xml"):
                    z.write(path, path.name)
        state["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        tag = state["tag"]
        # A rerun may resume an existing draft after an interrupted upload.
        existing = subprocess.run(["gh", "release", "view", tag, "--repo", repo], capture_output=True)
        if existing.returncode:
            gh("release", "create", tag, "--repo", repo, "--target", os.environ["GITHUB_SHA"], "--draft", "--title", f"PCL fork {state['upstream_sha'][:12]}", "--notes",
               f"Upstream: https://github.com/{UPSTREAM}/commit/{state['upstream_sha']}\nRestrictMcDownload = False. Updates use {repo}.\nDownload PCL-fork.zip and extract all files.\nBuild: {state['build_id']}")
        checksums = ROOT / "SHA256SUMS.txt"
        checksums.write_text(f"{state['sha256']}  PCL-fork.zip\n", encoding="utf-8")
        gh("release", "upload", tag, str(archive), str(ROOT / "patched-source.zip"), str(checksums), "--repo", repo, "--clobber")
        gh("release", "edit", tag, "--repo", repo, "--draft=false", "--latest")
    channel = ROOT / "channel.json"
    channel.write_text(json.dumps(state, indent=2), encoding="utf-8")
    previous = subprocess.run(["gh", "release", "view", "update-channel", "--repo", repo], capture_output=True)
    if previous.returncode:
        gh("release", "create", "update-channel", "--repo", repo, "--target", os.environ["GITHUB_SHA"], "--prerelease", "--latest=false", "--title", "Fork update channel", "--notes", "Machine-readable update status. Download application builds from the latest regular release.")
    gh("release", "upload", "update-channel", str(channel), "--repo", repo, "--clobber")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(f"Status: {state['status']}\n\nUpstream: `{state['upstream_sha']}`\n\n")
        if state["status"] == "blocked":
            f.write(f"Publishing paused: {state['reason']}. Existing clients will show the upstream notice.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "publish"])
    args = parser.parse_args()
    {"prepare": prepare, "publish": publish}[args.stage]()
