"""Strictly patch supported upstream source; never guess a new restriction mechanism."""
import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


class UnsupportedSource(Exception):
    pass


def patch_source(source, repository, build_id):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", build_id):
        raise ValueError("Invalid build ID")
    secret = source / "Plain Craft Launcher 2/Modules/ModSecret.vb"
    if not secret.is_file():
        raise UnsupportedSource("ModSecret.vb missing")
    text = secret.read_text(encoding="utf-8-sig")
    switch = r"(?m)^([ \t]*Public Const RestrictMcDownload As Boolean = )(True|False)[ \t]*$"
    if len(re.findall(switch, text)) != 1:
        raise UnsupportedSource("Expected exactly one RestrictMcDownload Boolean constant")
    update = r"(?ms)^    Friend Sub UpdateCheckByButton\(\).*?^    End Sub[ \t]*\n?"
    loader = r'(?m)^    Public ServerLoader As New LoaderTask\(Of Integer, Integer\)\("PCL 配置更新", Sub\(\).*?, Priority:=ThreadPriority.BelowNormal\) With'
    if len(re.findall(update, text)) != 1 or len(re.findall(loader, text)) != 1:
        raise UnsupportedSource("Update hooks changed; manual review required")
    # Validate that all known gates still consult this switch.
    gates = {
        "Pages/PageDownload/PageDownloadInstall.xaml.vb": 1,
        "Modules/Minecraft/ModModpack.vb": 2,
        "Pages/PageDownload/PageDownloadModify.vb": 1,
        "Pages/PageDownload/Resource/PageDownloadCompDetail.xaml.vb": 1,
        "FormMain.xaml.vb": 1,
    }
    for name, count in gates.items():
        path = source / "Plain Craft Launcher 2" / name
        if not path.is_file() or path.read_text(encoding="utf-8-sig").count("RestrictMcDownload") != count:
            raise UnsupportedSource(f"Restriction gate changed: {name}")
    template = (ROOT / "scripts/fork-update.vb").read_text(encoding="utf-8")
    template = template.replace("@@REPOSITORY@@", repository).replace("@@BUILD_ID@@", build_id)
    text = re.sub(switch, r"\g<1>False", text)
    text = re.sub(update, lambda _: template + "\n", text)
    text = re.sub(loader, '    Public ServerLoader As New LoaderTask(Of Integer, Integer)("PCL 配置更新", Sub() ForkCheckUpdate(False), Priority:=ThreadPriority.BelowNormal) With', text)
    secret.write_text(text, encoding="utf-8-sig")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=pathlib.Path)
    p.add_argument("--repository", required=True)
    p.add_argument("--build-id", required=True)
    args = p.parse_args()
    try:
        patch_source(args.source, args.repository, args.build_id)
    except UnsupportedSource as ex:
        print(f"UNSUPPORTED: {ex}")
        raise SystemExit(42)
