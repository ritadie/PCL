    '此区域由 scripts/prepare_upstream.py 安装；仅访问本分支的更新通道。
    Public Const ForkRepository As String = "@@REPOSITORY@@"
    Public Const ForkBuildId As String = "@@BUILD_ID@@"
    Private ForkUpdateBusy As Integer = 0
    Private ForkAutoChecked As Integer = 0
    Private ForkBlockedShown As Boolean = False

    Friend Sub UpdateCheckByButton()
        RunInNewThread(Sub() ForkCheckUpdate(True), "Fork update check")
    End Sub

    Private Sub ForkCheckUpdate(Manual As Boolean)
        '自动检查每次启动只尝试一次；断网也不重试，不参与游戏启动或下载流程。
        If Not Manual AndAlso System.Threading.Interlocked.Exchange(ForkAutoChecked, 1) <> 0 Then Return
        If System.Threading.Interlocked.Exchange(ForkUpdateBusy, 1) <> 0 Then Return
        Try
            Dim Json As String
            Using Client As New System.Net.Http.HttpClient()
                Client.Timeout = TimeSpan.FromSeconds(5)
                Client.DefaultRequestHeaders.UserAgent.ParseAdd("PCL-Fork-Updater/1.0")
                Dim Url = "https://github.com/" & ForkRepository & "/releases/download/update-channel/channel.json?t=" & DateTime.UtcNow.Ticks.ToString()
                Json = Client.GetStringAsync(Url).GetAwaiter().GetResult()
            End Using
            Dim Info = JObject.Parse(Json)
            If CInt(Info("schema")) <> 1 Then Throw New Exception("不支持的更新通道格式")
            Dim Status = CStr(Info("status"))
            If Status = "blocked" Then
                If Not ForkShouldShowCompatibilityNotice() Then Return
                RunInUi(Sub()
                            If MyMsgBox("检测到上游兼容性变化，当前方式暂时无法继续自动构建。你可以前往上游仓库查看解决办法，也可以关闭此提示继续使用。" & vbCrLf &
                                        "此提醒仅显示一次，不限制启动器的其他功能。", "兼容性提醒（可忽略）", "前往上游仓库", "继续使用") = 1 Then
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

    Private Function ForkShouldShowCompatibilityNotice() As Boolean
        If ForkBlockedShown Then Return False
        ForkBlockedShown = True
        Try
            Dim Folder = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCL2", ForkRepository.Replace("/", "_"))
            Dim Marker = System.IO.Path.Combine(Folder, "compatibility-notice-shown")
            If System.IO.File.Exists(Marker) Then Return False
            System.IO.Directory.CreateDirectory(Folder)
            System.IO.File.WriteAllText(Marker, "shown")
        Catch ex As Exception
            '无法保存提醒记录时也继续使用，当前进程内仍只提醒一次。
            Logger.Warn(ex, "保存兼容性提醒记录失败")
        End Try
        Return True
    End Function

