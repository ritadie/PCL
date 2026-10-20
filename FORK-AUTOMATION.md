# 自动跟踪上游

本仓库的 `Upstream build and release` 工作流每 6 小时检查
<https://github.com/Meloong-Git/PCL> 默认分支，也可从 Actions 手动运行。
首次在 fork 使用时，需要在 Actions 页面启用工作流。定时任务需位于默认分支；GitHub 可能延迟调度，公开仓库长时间无活动时可能暂停定时任务。

每次构建在临时目录克隆上游和固定的子模块版本，不合并或覆盖本仓库的自动化代码。
仅在 `ModSecret.vb` 中存在唯一的 `Public Const RestrictMcDownload As Boolean = True/False`，
且已知入口和更新挂钩结构匹配时，才将开关设为 `False`，安装本分支的更新检查，编译 Release。
源码检查不等同于证明以后上游不会引入其他限制；遇到结构变化需要人工审查。

发布内容：编译好的 `PCL2.exe`、完整运行目录 `PCL2.zip`、不含注入密钥的 `patched-source.zip` 和 `SHA256SUMS.txt`。
成功发布后才更新 `update-channel` 预发布中的 `channel.json`。
上游 SHA 和自动化脚本指纹相同则跳过；手动运行勾选 force 可重试同一版本。
网络、还原、编译失败会令 Actions 失败，保留上一份更新通道。
源码不兼容则发布 `blocked` 通道状态，不发布新应用程序。

客户端启动时检查本仓库通道，“检查更新”按钮也可手动触发。
发现新构建时提示打开本仓库 Release 下载页，用户完整解压替换；不会后台替换运行文件。
收到 `blocked` 后弹窗，引导用户前往上游仓库查看解决办法，当前安装版本可继续使用。
此功能仅适用于带本更新检查的构建，已经发出的旧版无法追补弹窗。

工作流只使用本仓库 `GITHUB_TOKEN` 的 `contents: write` 权限，无需 PAT。
如仓库策略禁止此权限，需要仓库管理员在 Settings → Actions 中允许发布。
可选的仓库 Secrets 沿用现有名称：`CLIENT_ID` 和 `CURSEFORGE_API_KEY`。
未配置时，仍依赖客户端环境变量；微软登录和 CurseForge 功能可能不可用。
这些凭据若嵌入 EXE，将能被最终用户提取，应使用允许分发的凭据。

修改脚本后的验证：`python -m unittest discover -s scripts -p "test_*.py"`。
支持性检测通过不代表实际下载已验证；发布前可从 Actions 日志确认构建结果。
