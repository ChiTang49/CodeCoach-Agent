import subprocess
import time
import webbrowser
import os
import signal
import sys
from threading import Thread

def stream_output(process, prefix):
    """Stream process output with filtering for cleaner logs"""
    for line in iter(process.stdout.readline, ''):
        line_stripped = line.strip()
        # Filter out repetitive INFO logs from uvicorn
        if 'INFO:     127.0.0.1' in line_stripped and 'GET /api/sessions' in line_stripped:
            continue  # Skip session polling logs
        if 'INFO:     127.0.0.1' in line_stripped and 'GET /api/memories' in line_stripped:
            continue  # Skip memory polling logs
        if line_stripped:  # Only print non-empty lines
            print(f"[{prefix}] {line_stripped}")
    process.stdout.close()

def kill_process_on_port(port):
    """Kills the process listening on the specified port (Windows only)."""
    try:
        # Use full path to netstat to ensure it works even if PATH is messed up
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        netstat_cmd = os.path.join(system_root, 'System32', 'netstat.exe')
        findstr_cmd = os.path.join(system_root, 'System32', 'findstr.exe')
        taskkill_cmd = os.path.join(system_root, 'System32', 'taskkill.exe')
        
        command = f'"{netstat_cmd}" -ano | "{findstr_cmd}" :{port}'
        
        # Use errors='ignore' to avoid decoding issues on Windows
        output = subprocess.check_output(command, shell=True).decode(errors='ignore')
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) > 4:
                pid = parts[-1]
                # Filter to ensure we are killing the process actually listening on the port
                if pid != "0": # Don't kill system idle process
                    print(f"⚠️ Port {port} is in use by PID {pid}. Killing it...")
                    subprocess.call(f'"{taskkill_cmd}" /F /PID {pid} >nul 2>&1', shell=True)
    except subprocess.CalledProcessError:
        pass # Port not in use
    except Exception as e:
        print(f"⚠️ Warning: Failed to clean port {port}: {e}")

def main():
    # 设置环境变量以解决 Hugging Face 连接超时问题
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    # 如果本地已有模型，强制离线模式可以极大提升速度
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    
    print("🚀 Starting CodeCoach Agent System...")
    
    # 0. Cleanup Ports
    print("🧹 Cleaning up ports 8000 and 3000...")
    kill_process_on_port(8000)
    kill_process_on_port(3000)
    
    # Detect Agent Python
    params_python = "F:\\Anaconda\\envs\\agent\\python.exe"
    target_python = sys.executable
    if os.path.exists(params_python):
        print(f"✅ Found Conda Agent Python at: {params_python}")
        target_python = params_python
    else:
        print(f"⚠️ Conda Agent Python not found at {params_python}, using: {sys.executable}")

    # 1. Start Backend
    print(f"🚀 Starting Backend Server with: {target_python}")
    print(f"   (Working Directory: {os.getcwd()})")
    
    # Check if backend file exists
    if not os.path.exists("server.py"):
        print("❌ Error: server.py not found in current directory!")
        return

    backend_env = os.environ.copy()
    # Explicitly set unbuffered output for Python
    backend_env["PYTHONUNBUFFERED"] = "1"
    # Force UTF-8 encoding for IO to prevent 'gbk' errors on Windows
    backend_env["PYTHONIOENCODING"] = "utf-8"
    
    backend_process = subprocess.Popen(
        [target_python, "server.py"],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8', 
        errors='replace',
        bufsize=1,
        env=backend_env
    )
    
    # Thread to print backend output
    Thread(target=stream_output, args=(backend_process, "Backend"), daemon=True).start()

    # 2. Start Frontend
    print("Starting Frontend Interface...")
    frontend_cwd = os.path.join(os.getcwd(), "frontend")
    
    # Use 'npm.cmd' on Windows, 'npm' on Unix
    npm_cmd = "npm.cmd" if os.name == 'nt' else "npm"
    
    frontend_process = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=frontend_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8', # Force UTF-8 for Node/Next.js output
        errors='replace', # Handle any encoding errors gracefully
        bufsize=1,
        env=backend_env
    )
    
    # Thread to print frontend output
    Thread(target=stream_output, args=(frontend_process, "Frontend"), daemon=True).start()

    print("⏳ Waiting for services to initialize...")
    time.sleep(5) # Give it a few seconds
    
    url = "http://localhost:3000"
    print(f"🌍 Opening {url}...")
    webbrowser.open(url)

    print("\n✅ System is running! Press Ctrl+C to stop.\n")

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
            if backend_process.poll() is not None:
                print("❌ Backend process exited unexpectedly.")
                break
            if frontend_process.poll() is not None:
                print("❌ Frontend process exited unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        # Terminate processes
        if backend_process.poll() is None:
            backend_process.terminate()
        if frontend_process.poll() is None:
            # On Windows, terminating the shell doesn't always kill the node process
            # But we'll try standard terminate first
            frontend_process.terminate()
            
        print("Goodbye!")

if __name__ == "__main__":
    main()
