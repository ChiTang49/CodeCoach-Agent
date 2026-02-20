# CodeCoach Agent - PowerShell 启动脚本
# 使用方法: 右键点击 -> 使用 PowerShell 运行

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "CodeCoach Agent - 启动中..."

# 设置颜色
$ProgressColor = "Cyan"
$SuccessColor = "Green"
$ErrorColor = "Red"
$WarningColor = "Yellow"

# 清屏
Clear-Host

# 显示欢迎信息
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor $ProgressColor
Write-Host "║                                                               ║" -ForegroundColor $ProgressColor
Write-Host "║           🚀 CodeCoach Agent - AI 算法学习系统 🚀              ║" -ForegroundColor $ProgressColor
Write-Host "║                                                               ║" -ForegroundColor $ProgressColor
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor $ProgressColor
Write-Host ""

# 第一步：检查并激活 Conda 环境
Write-Host "[1/3] 🔍 检查 Conda 环境..." -ForegroundColor $ProgressColor

# 初始化 Conda（如果需要）
$condaPath = (Get-Command conda -ErrorAction SilentlyContinue).Source
if (-not $condaPath) {
    # 尝试常见的 Conda 安装路径
    $possiblePaths = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $condaPath = $path
            break
        }
    }
}

if (-not $condaPath) {
    Write-Host ""
    Write-Host "   ❌ 错误：未找到 Conda" -ForegroundColor $ErrorColor
    Write-Host ""
    Write-Host "   💡 请先安装 Anaconda 或 Miniconda" -ForegroundColor $WarningColor
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

# 激活 Conda 环境
$activateScript = Split-Path $condaPath | Join-Path -ChildPath "..\condabin\conda-hook.ps1"
if (Test-Path $activateScript) {
    . $activateScript
}

try {
    conda activate agent 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Environment not found"
    }
    Write-Host "   ✅ Conda 环境 'agent' 已激活" -ForegroundColor $SuccessColor
} catch {
    Write-Host ""
    Write-Host "   ❌ 错误：未找到 conda 环境 'agent'" -ForegroundColor $ErrorColor
    Write-Host ""
    Write-Host "   💡 请先创建环境：" -ForegroundColor $WarningColor
    Write-Host "      conda create -n agent python=3.10" -ForegroundColor White
    Write-Host "      conda activate agent" -ForegroundColor White
    Write-Host "      pip install -r requirements.txt" -ForegroundColor White
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

Write-Host ""

# 第二步：检查环境配置
Write-Host "[2/3] 🔍 检查环境配置..." -ForegroundColor $ProgressColor

if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "   ⚠️  警告：未找到 .env 文件" -ForegroundColor $WarningColor
    Write-Host ""
    Write-Host "   💡 请创建 .env 文件并配置以下变量：" -ForegroundColor $WarningColor
    Write-Host "      - LLM_MODEL_ID" -ForegroundColor White
    Write-Host "      - LLM_API_KEY" -ForegroundColor White
    Write-Host "      - LLM_BASE_URL" -ForegroundColor White
    Write-Host "      - EMBED_API_KEY" -ForegroundColor White
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "   ✅ 环境配置文件已就绪" -ForegroundColor $SuccessColor
Write-Host ""

# 第三步：启动 App
Write-Host "[3/3] 🚀 启动 CodeCoach Agent..." -ForegroundColor Cyan
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "   📱 应用将在浏览器中自动打开" -ForegroundColor Cyan
Write-Host "   🌐 默认地址: " -NoNewline -ForegroundColor Cyan
Write-Host "http://localhost:3000" -ForegroundColor Green
Write-Host "   ⏹️  停止应用: 按 " -NoNewline -ForegroundColor Cyan
Write-Host "Ctrl+C" -ForegroundColor Yellow
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$Host.UI.RawUI.WindowTitle = "CodeCoach Agent - 运行中"

# 启动 App
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:HF_HUB_OFFLINE = "1" 
$env:TRANSFORMERS_OFFLINE = "1"
python start_app.py

# 退出信息
Write-Host ""
Write-Host "👋 感谢使用 CodeCoach Agent！" -ForegroundColor $SuccessColor
Read-Host "按回车键退出"
