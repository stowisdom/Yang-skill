# -*- coding: utf-8 -*-
"""
DDL Auto Starter - Skill触发时自动启动监听器
- 检查是否已有监听器在运行
- 如果没有，在后台启动
- 如果已运行，返回当前状态
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

# 路径配置
SKILL_DIR = Path(__file__).parent
WATCHER_SCRIPT = SKILL_DIR / "ddl_watcher.py"
PID_FILE = SKILL_DIR / ".watcher_pid"
STATE_FILE = Path(__file__).parent.parent.parent / "sessions" / "260407-smart-sand" / "data" / ".ddl_watcher_state.json"

def is_watcher_running():
    """检查监听器是否已在运行"""
    # 方法1: 检查PID文件
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            if sys.platform == 'win32':
                # Windows
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                    capture_output=True, text=True
                )
                if str(pid) in result.stdout and 'python' in result.stdout.lower():
                    return True
            else:
                # Linux/Mac
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    pass
        except:
            pass
    
    # 方法2: 检查状态文件的时间戳
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 如果状态是 ready 且更新时间在过去5分钟内，认为正在运行
            if state.get('status') == 'ready':
                last_update = state.get('last_update', '')
                if last_update:
                    last_time = datetime.fromisoformat(last_update)
                    elapsed = (datetime.now() - last_time).total_seconds()
                    if elapsed < 300:  # 5分钟内更新过
                        return True
        except:
            pass
    
    return False

def save_pid(pid):
    """保存PID到文件"""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
    except:
        pass

def start_watcher_daemon():
    """在后台启动监听器"""
    try:
        if sys.platform == 'win32':
            # Windows: 使用creationflags创建后台进程
            process = subprocess.Popen(
                [sys.executable, str(WATCHER_SCRIPT)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            # Linux/Mac: 使用nohup或disown
            process = subprocess.Popen(
                [sys.executable, str(WATCHER_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        # 保存PID
        save_pid(process.pid)
        
        # 等待一小段时间确保启动成功
        time.sleep(1)
        
        return process.pid
    except Exception as e:
        return None

def get_watcher_status():
    """获取监听器状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None

def main():
    """主函数"""
    # 检查是否已在运行
    if is_watcher_running():
        status = get_watcher_status()
        if status:
            return {
                "status": "already_running",
                "message": "监听器已在运行",
                "last_update": status.get('last_update', 'unknown'),
                "report_path": status.get('report_path', '')
            }
        else:
            return {
                "status": "already_running",
                "message": "监听器已在运行"
            }
    
    # 启动监听器
    pid = start_watcher_daemon()
    
    if pid:
        return {
            "status": "started",
            "message": f"监听器已启动 (PID: {pid})",
            "pid": pid,
            "note": "文件修改后将自动刷新报告"
        }
    else:
        return {
            "status": "error",
            "message": "启动监听器失败"
        }

if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
