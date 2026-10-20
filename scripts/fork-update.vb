    '此区域由 scripts/prepare_upstream.py 安装；仅访问本分支的更新通道。
    Public Const ForkRepository As String = "@@REPOSITORY@@"
    Public Const ForkBuildId As String = "@@BUILD_ID@@"
    Private ForkUpdateBusy As Integer = 0
    Private ForkBlockedShown As Boolean = False

    Friend Sub UpdateCheckByButton()
        RunInNewThread(Sub() ForkCheckUpdate(True), "Fork update check")
    End Sub

    Private Sub ForkCheckUpdate(Manual As Boolean)
        If System.Threading.Interlocked.Exchange(ForkUpdateBusy, 1) <> 0 Then Return
        Try
            Dim Json As String
            Using Client As New System.Net.Http.HttpClient()
                Client.Timeout = TimeSpan.FromSeconds(20)
                Client.DefaultRequestHeaders.UserAgent.ParseAdd("PCL-Fork-Updater/1.0")
                Dim Url = "https://github.com/" & ForkRepository & "/releases/download/update-channel/channel.json?t=" & DateTime.UtcNow.Ticks.ToString()
                Json = Client.GetStringAsync(Url).GetAwaiter().GetResult()
            End Using
            Dim Info = JObject.Parse(Json)
            If CInt(Info("schema")) <> 1 Then Throw New Exception("不支持的更新通道格式")
            Dim Status = CStr(Info("status"))
            If Status = "blocked" Then
                RunInUi(Sub()
                            If ForkBlockedShown AndAlso Not Manual Then Return
                            ForkBlockedShown = True
                            If MyMsgBox("上游源码已无法通过 RestrictMcDownload = False 的方式继续自动构建。本分支已暂停发布，请前往上游仓库查看说明并解决。" & vbCrLf &
                                        "当前已安装版本可以继续使用。", "上游兼容性变化", "前往上游仓库", "稍后") = 1 Then
                                OpenWebsite("https://github.com/Meloong-Git/PCL")
                            End If
                        End Sub)
            ElseIf Status = "ready" Then
                If CStr(Info("build_id")) <> ForkBuildId Then
                    RunInUi(Sub()
                                If MyMsgBox("本分支有新的编译版本。请下载 ZIP，退出启动器后完整解压替换。", "发现更新", "打开本仓库下载页", "稍后") = 1 Then
                                    OpenWebsite("https://github.com/" & ForkRepository & "/releases/latest")
                                End If
                            End Sub)
                ElseIf Manual Then
                    RunInUi(Sub() Hint("当前已是本分支最新版本。"))
                End If
            Else
                Throw New Exception("未知的更新通道状态")
            End If
        Catch ex As Exception
            Logger.Warn(ex, "检查本分支更新失败")
            If Manual Then RunInUi(Sub()
                                      If MyMsgBox("暂时无法读取本分支更新通道。可以前往发布页手动检查。", "检查更新失败", "打开发布页", "取消") = 1 Then
                                          OpenWebsite("https://github.com/" & ForkRepository & "/releases")
                                      End If
                                  End Sub)
        Finally
            System.Threading.Interlocked.Exchange(ForkUpdateBusy, 0)
        End Try
    End Sub

