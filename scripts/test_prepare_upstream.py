import pathlib
import tempfile
import unittest

from prepare_upstream import patch_source, UnsupportedSource


class PatchTests(unittest.TestCase):
    def fixture(self, root, value="True"):
        base = root / "Plain Craft Launcher 2"
        secret = base / "Modules/ModSecret.vb"
        secret.parent.mkdir(parents=True)
        secret.write_text(f'''Friend Module ModSecret
    Public Const RestrictMcDownload As Boolean = {value}
    Friend Sub UpdateCheckByButton()
        Hint("old")
    End Sub
    Public ServerLoader As New LoaderTask(Of Integer, Integer)("PCL 配置更新", Sub() Logger.Info("old"), Priority:=ThreadPriority.BelowNormal) With
        {{.ReloadTimeout = 3600000}}
End Module
''', encoding="utf-8")
        for name, count in {
            "Pages/PageDownload/PageDownloadInstall.xaml.vb": 1,
            "Modules/Minecraft/ModModpack.vb": 2,
            "Pages/PageDownload/PageDownloadModify.vb": 1,
            "Pages/PageDownload/Resource/PageDownloadCompDetail.xaml.vb": 1,
            "FormMain.xaml.vb": 1,
        }.items():
            p = base / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("RestrictMcDownload\n" * count, encoding="utf-8")
        return secret

    def test_true_and_false(self):
        for value in ["True", "False"]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                root = pathlib.Path(d)
                secret = self.fixture(root, value)
                patch_source(root, "ritadie/PCL", "abc-123")
                text = secret.read_text(encoding="utf-8-sig")
                self.assertIn("RestrictMcDownload As Boolean = False", text)
                self.assertIn('ForkRepository As String = "ritadie/PCL"', text)
                self.assertIn("Sub() ForkCheckUpdate(False)", text)
                self.assertNotIn("@@", text)

    def test_unsupported_is_not_modified(self):
        for old, new in [("Public Const", "Public ReadOnly"), ("UpdateCheckByButton()", "ChangedHook()"), ("False", "0")]:
            with self.subTest(old=old), tempfile.TemporaryDirectory() as d:
                root = pathlib.Path(d)
                secret = self.fixture(root, "False")
                secret.write_text(secret.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                before = secret.read_bytes()
                with self.assertRaises(UnsupportedSource):
                    patch_source(root, "ritadie/PCL", "abc-123")
                self.assertEqual(before, secret.read_bytes())

    def test_changed_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            secret = self.fixture(root)
            before = secret.read_bytes()
            (root / "Plain Craft Launcher 2/FormMain.xaml.vb").write_text("Changed", encoding="utf-8")
            with self.assertRaises(UnsupportedSource):
                patch_source(root, "ritadie/PCL", "abc-123")
            self.assertEqual(before, secret.read_bytes())


if __name__ == "__main__":
    unittest.main()
