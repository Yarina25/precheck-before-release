<#
=====================================================================
 项目：D:\projects\D_projects_stage 一键推送到 GitHub
 适用：Windows 10 / 11，PowerShell 5.1（系统自带）
 说明：本脚本不会使用账号密码登录 GitHub；认证走 gh 浏览器授权
       或 Windows Git 凭据管理器弹窗，令牌/密码不会写进脚本。
=====================================================================
#>

# ===================== 配置区（按实际情况修改） =====================
$ProjectDir    = "D:\projects\D_projects_stage"
$GitHubUser    = "Yarina25"

# 本地尚未配置 origin 时使用的默认仓库地址；
# 如果你的仓库名不是 D_projects_stage，请先在这里改成真实 URL，
# 例如：https://github.com/Yarina25/你的仓库名.git
$DefaultRemote = "https://github.com/Yarina25/D_projects_stage.git"

$CommitMessage = "chore: 同步本地 D_projects_stage 到 GitHub"
# ====================================================================

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "`n===== $msg =====" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "[成功] $msg" -ForegroundColor Green
}
function Write-Warn2([string]$msg) {
    Write-Host "[注意] $msg" -ForegroundColor Yellow
}
function Fail([string]$msg) {
    Write-Host "[失败] $msg" -ForegroundColor Red
    exit 1
}

# ---------- 1. 环境与目录检查 ----------
Write-Step "1/8 检查 Git 环境"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "未检测到 Git。请先安装 Git for Windows：https://git-scm.com/download/win ，安装完成后重开终端再运行本脚本。"
}
git --version | Out-Host

if (-not (Test-Path $ProjectDir)) {
    Fail "目录不存在：$ProjectDir 。请打开本脚本，把配置区里的 `$ProjectDir 改成你的真实路径。"
}
Set-Location $ProjectDir
Write-Ok "当前工作目录：$ProjectDir"

if (-not (Test-Path ".git")) {
    Fail "当前目录不是 Git 仓库（未找到 .git 文件夹）。与“已有提交历史”的前提不符，请确认路径正确。"
}

# ---------- 2. 读取当前分支 ----------
Write-Step "2/8 读取当前分支"
$branch = git symbolic-ref --short HEAD 2>$null
if (-not $branch) { $branch = git branch --show-current 2>$null }
if (-not $branch) { Fail "无法获取当前分支名，请在终端先执行 git branch 确认。" }
Write-Ok "当前分支：$branch"

# ---------- 3. 配置 Git 身份（仅在本地未配置时写入兜底值） ----------
Write-Step "3/8 检查 Git 用户身份"
$name  = git config user.name
$email = git config user.email
if (-not $name)  { git config user.name  $GitHubUser; Write-Warn2 "已写入本地 user.name=$GitHubUser，可用 git config user.name 修改。" }
if (-not $email) {
    git config user.email "$GitHubUser@users.noreply.github.com"
    Write-Warn2 "已写入兜底邮箱 $GitHubUser@users.noreply.github.com；建议执行：git config user.email 你的真实邮箱"
}

# ---------- 4. GitHub 认证 ----------
Write-Step "4/8 检查 GitHub 登录状态"
$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    gh auth status
    if ($LASTEXITCODE -ne 0) {
        Write-Host "未登录 GitHub，接下来将打开浏览器授权（设备码登录，无需输入密码）。" -ForegroundColor Yellow
        gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { Fail "GitHub 授权失败，请按终端提示重试或改用 PAT，详见操作步骤文档。" }
    }
    Write-Ok "GitHub CLI 已登录"
} else {
    Write-Warn2 "未安装 GitHub CLI。推送时会弹出 Windows Git 凭据管理器，在浏览器里点授权即可；"
    Write-Warn2 "也可以先安装：winget install --id GitHub.cli ，再重跑本脚本。"
}

# ---------- 5. 关联远程仓库 ----------
Write-Step "5/8 检查远程仓库 origin"
$originUrl = $null
$remotes = @(git remote)
if ($remotes -contains "origin") {
    $originUrl = (git remote get-url origin)
    Write-Ok "已存在 origin：$originUrl"
} else {
    Write-Host "未配置 origin。默认地址：$DefaultRemote" -ForegroundColor Yellow
    $ans = Read-Host "回车使用默认地址，或粘贴你的真实仓库 URL 后回车"
    if ([string]::IsNullOrWhiteSpace($ans)) {
        $originUrl = $DefaultRemote
    } else {
        $originUrl = $ans.Trim()
    }
    git remote add origin $originUrl
    Write-Ok "已添加 origin：$originUrl"
}

# ---------- 6. 同步远程历史（防止非快进冲突） ----------
Write-Step "6/8 拉取远程最新提交"
git fetch origin --prune
if ($LASTEXITCODE -ne 0) {
    Write-Warn2 "fetch 失败：远程仓库可能为空或网络不通，将跳过历史比对，直接尝试推送。"
} else {
    $remoteRef = "origin/$branch"
    git rev-parse --verify --quiet $remoteRef 2>$null
    if ($LASTEXITCODE -eq 0) {
        $mergeBase = (git merge-base HEAD $remoteRef 2>$null)
        $remoteSha = (git rev-parse $remoteRef)
        if (-not $mergeBase) {
            Write-Warn2 "本地与远程历史互不关联（远程可能是带 README/.gitignore 的新建仓库）。"
            $go = Read-Host "是否执行 git pull --rebase origin $branch --allow-unrelated-histories 进行合并？(Y/N)"
            if ($go -match '^[Yy]') {
                git pull --rebase origin $branch --allow-unrelated-histories
                if ($LASTEXITCODE -ne 0) { Fail "变基失败：请先解决终端提示的冲突文件，保存后执行 git rebase --continue，再重跑本脚本。" }
                Write-Ok "远程历史已同步（互不关联历史已合并）"
            } else {
                Fail "已取消：为避免覆盖远程提交，脚本退出。确认要强制覆盖时再手动执行 git push -f，后果自负。"
            }
        } elseif ($mergeBase -ne $remoteSha) {
            Write-Warn2 "远程 $remoteRef 有本地尚未包含的提交，直接推送会被拒绝。"
            $go = Read-Host "是否执行 git pull --rebase origin $branch 同步后继续？(Y/N)"
            if ($go -match '^[Yy]') {
                git pull --rebase origin $branch
                if ($LASTEXITCODE -ne 0) { Fail "变基失败：请先解决终端提示的冲突文件，保存后执行 git rebase --continue，再重跑本脚本。" }
                Write-Ok "远程历史已同步"
            } else {
                Fail "已取消：为避免覆盖远程提交，脚本退出。确认要强制覆盖时再手动执行 git push -f，后果自负。"
            }
        } else {
            Write-Ok "本地与远程历史一致，无需变基"
        }
    } else {
        Write-Warn2 "远程还没有 $branch 分支（新仓库首次推送），稍后将建立上游关联。"
    }
}

# ---------- 7. 生成 .gitignore 并提交本地变更 ----------
Write-Step "7/8 检查 .gitignore 并提交"
$tpl = Join-Path $PSScriptRoot ".gitignore.template"
if (-not (Test-Path ".gitignore")) {
    if (Test-Path $tpl) {
        Copy-Item $tpl ".gitignore"
        Write-Ok "已按模板生成 .gitignore（node_modules、虚拟环境、密钥、日志等已排除）"
    } else {
        Write-Warn2 "未找到 .gitignore.template，保持现有状态不生成 .gitignore。"
    }
} else {
    Write-Ok ".gitignore 已存在，保持不动"
}

git add -A
$pending = @(git status --porcelain)
if ($pending.Count -gt 0) {
    git commit -m $CommitMessage
    if ($LASTEXITCODE -ne 0) { Fail "提交失败，请查看终端报错信息。" }
    Write-Ok "本地变更已提交（共 $($pending.Count) 项）"
} else {
    Write-Ok "没有待提交的本地变更"
}

# ---------- 8. 推送到 GitHub ----------
Write-Step "8/8 推送到 origin/$branch"
git push -u origin $branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n推送被拒绝，常见原因与处理方式：" -ForegroundColor Red
    Write-Host "  1) 403/认证失败：运行 gh auth login 重新授权，或在 Git 凭据管理器里重新登录；"
    Write-Host "  2) non-fast-forward：远程有新提交，按第 6 步提示执行 git pull --rebase origin $branch；"
    Write-Host "  3) 文件超过 100MB：GitHub 禁止单文件 100MB 直接推送，需用 Git LFS 或移出仓库；"
    Write-Host "  4) 仓库地址错误：执行 git remote set-url origin 真实URL 后重跑脚本。"
    exit 1
}

Write-Step "完成"
Write-Ok "已推送到 $originUrl （分支 $branch）"
Write-Host "`n最近 5 条提交记录：" -ForegroundColor Cyan
git log --oneline -5
Write-Host "`n浏览器打开仓库核对代码：$($originUrl -replace '\.git$','')" -ForegroundColor Cyan
