# 🚀 快捷启动脚本使用指南

## 📋 脚本列表

项目提供了现代化启动脚本，适用于 Windows10/11：

### **start.ps1** - PowerShell 版本
**现代化 PowerShell 启动脚本**

```powershell
# 右键点击 -> 使用 PowerShell 运行
# 或在 PowerShell 中执行
.\start.ps1
```

**特性：**
- 🎨 彩色控制台输出
- 🔍 智能检测 Conda 路径
- ⚡ 更好的错误处理
- 💡 详细的安装指导
- 🖥️ 适合 Windows 10/11

**首次使用可能需要设置执行策略：**
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## 📖 使用场景推荐

| 场景 | 推荐脚本 | 原因 |
|------|---------|------|
| 日常使用 | `start.ps1` | 稳定可靠，有错误提示 |
| PowerShell 用户 | `start.ps1` | 更现代的体验 |

---

## 🔧 手动启动命令

如果不想使用脚本，也可以手动执行：

### Windows CMD
```cmd
conda activate agent
python start_app.py
```

### PowerShell
```powershell
conda activate agent
python start_app.py
```

---

## ⚙️ 配置选项

项目使用 `.env` 文件进行配置。请参考 `.env.example` 创建并配置您的环境变量。

---

## ❓ 常见问题 (FAQ)

### Q: 启动脚本闪退怎么办？
**A**: 这通常是因为 Conda 环境未正确配置或 activate 命令失败。
请尝试：
1. 手动打开 PowerShell
2. 运行 `conda activate agent`
3. 如果失败，请先创建环境：`conda create -n agent python=3.10`

### Q: 提示 "ExecutionPolicy" 错误？
**A**: 这是 PowerShell 的安全策略限制。
请以管理员身份运行 PowerShell 并输入：
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
输入 `Y` 确认即可。

### Q: 端口被占用？
**A**: 脚本会自动尝试清理端口，如果失败，您可以：
- **方法 1**: 重启电脑（最简单）
- **方法 2**: 手动查找占用端口的进程并结束
    - `netstat -ano | findstr :3000`
    - `taskkill /PID <PID> /F`

---

## 🔗 相关链接

- [Python 官网](https://www.python.org/)
- [Conda 官网](https://docs.conda.io/)
- [Next.js 文档](https://nextjs.org/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
