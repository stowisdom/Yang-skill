# -*- coding: utf-8 -*-
"""
DDL Main - Skill触发入口
自动启动监听器 + 生成当前报告
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 路径配置
SKILL_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent.parent / "sessions" / "260407-smart-sand" / "data"
TASK_FILE = Path("C:/Users/lenovo/Desktop/Task.txt")

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    """输出日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_script(script_name, *args):
    """运行脚本"""
    script_path = SKILL_DIR / script_name
    cmd = [sys.executable, str(script_path)] + list(args)
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0, result.stdout.decode('utf-8', errors='ignore')
    except Exception as e:
        return False, str(e)

def check_and_start_watcher():
    """检查并启动监听器"""
    # 检查是否已在运行
    pid_file = SKILL_DIR / ".watcher_pid"
    
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
            log(f"[Watcher] 监听器已在运行 (PID: {pid})")
            return True
        except:
            pass
    
    # 启动新监听器（在独立窗口中）
    watcher_script = SKILL_DIR / "ddl_watcher.py"
    
    try:
        if sys.platform == 'win32':
            # Windows: 使用start命令在新窗口运行
            import ctypes
            ctypes.windll.kernel32.AllocConsole()
            
            process = subprocess.Popen(
                ['start', 'python', str(watcher_script)],
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            process = subprocess.Popen(
                [sys.executable, str(watcher_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # 保存PID
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        log(f"[Watcher] 监听器已启动 (PID: {process.pid})")
        return True
        
    except Exception as e:
        log(f"[Watcher] 启动失败: {e}")
        return False

def main():
    """主函数"""
    log("=" * 50)
    log("DDL Skill - 任务截止时间管理")
    log("=" * 50)
    
    # 1. 检查任务文件
    if not TASK_FILE.exists():
        log(f"[错误] 任务文件不存在: {TASK_FILE}")
        return {"error": "Task file not found"}
    
    # 2. 启动/检查监听器
    log("[Step 1] 启动文件监听器...")
    watcher_ok = check_and_start_watcher()
    
    # 3. 处理任务数据
    log("[Step 2] 处理任务数据...")
    data_file = DATA_DIR / "tasks_data.json"
    process_script = DATA_DIR / "process_tasks.py"
    ok, output = run_script(str(process_script), str(data_file))
    
    if not ok:
        log(f"[错误] 数据处理失败")
        return {"error": "Data processing failed"}
    
    log("[OK] 数据处理完成")
    
    # 4. 生成PDF
    log("[Step 3] 生成PDF报告...")
    report_file = DATA_DIR / "DDL_Report.pdf"
    generate_script = DATA_DIR / "generate_pdf.py"
    ok, output = run_script(str(generate_script), str(data_file), str(report_file))
    
    if not ok:
        log(f"[错误] PDF生成失败")
        return {"error": "PDF generation failed"}
    
    log("[OK] PDF报告已生成")
    
    # 5. 读取统计信息
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total = data.get('total_tasks', 0)
        categories = data.get('categories', {})
        
        expired = sum(1 for t in data.get('tasks', []) if t['during_hours'] <= 0)
        urgent = categories.get('C类', 0)
        
        log(f"[统计] 总计: {total}项 | 已过期: {expired}项 | C类紧急: {urgent}项")
        
    except Exception as e:
        log(f"[警告] 无法读取统计: {e}")
    
    # 6. 输出结果
    result = {
        "status": "success",
        "watcher_running": watcher_ok,
        "report_path": str(report_file),
        "data_path": str(data_file),
        "message": "报告已生成，监听器正在后台运行"
    }
    
    log("=" * 50)
    log("完成! 修改 Task.txt 后将自动刷新报告")
    log("=" * 50)
    
    return result

if __name__ == "__main__":
    result = main()
    # 输出JSON结果供skill解析
    print("\n" + "=" * 50)
    print("RESULT_JSON_START")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("RESULT_JSON_END")
    print("=" * 50)
