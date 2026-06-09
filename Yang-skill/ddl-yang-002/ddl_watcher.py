# -*- coding: utf-8 -*-
"""
DDL Watcher - 文件监听自动刷新
当 Task.txt 发生变化时，自动重新生成 PDF 报告
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# 尝试导入 watchdog

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[警告] watchdog 未安装，使用轮询模式")
    print("安装命令: pip install watchdog")

# 配置路径
TASK_FILE = Path("C:/Users/lenovo/Desktop/Task.txt")
DATA_DIR = Path(__file__).parent.parent.parent / "sessions" / "260407-smart-sand" / "data"
REPORT_FILE = DATA_DIR / "DDL_Report.pdf"

# 状态文件
STATE_FILE = DATA_DIR / ".ddl_watcher_state.json"


class DDLHandler(FileSystemEventHandler):
    """文件变化处理器"""
    
    def __init__(self):
        self.last_modified = 0
        self.debounce_seconds = 1  # 防抖秒数
        
    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).name == TASK_FILE.name:
            current_time = time.time()
            # 防抖：避免短时间内重复触发
            if current_time - self.last_modified < self.debounce_seconds:
                return
            self.last_modified = current_time
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [检测到] Task.txt 变化")
            self.regenerate_report()
    
    def on_created(self, event):
        if not event.is_directory and Path(event.src_path).name == TASK_FILE.name:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [检测到] Task.txt 创建")
            self.regenerate_report()
    
    def regenerate_report(self):
        """重新生成报告"""
        try:
            # 保存状态
            self.save_state("regenerating")
            
            # 调用处理脚本
            process_script = DATA_DIR / "process_tasks.py"
            generate_script = DATA_DIR / "generate_pdf.py"
            data_file = DATA_DIR / "tasks_data.json"
            
            # 步骤1: 处理任务数据
            result1 = subprocess.run(
                [sys.executable, str(process_script), str(data_file)],
                capture_output=True
            )
            
            if result1.returncode != 0:
                try:
                    err = result1.stderr.decode('utf-8', errors='ignore')
                except:
                    err = "未知错误"
                print(f"[错误] 数据处理失败: {err}")
                self.save_state("error")
                return
            
            # 步骤2: 生成PDF
            result2 = subprocess.run(
                [sys.executable, str(generate_script), str(data_file), str(REPORT_FILE)],
                capture_output=True
            )
            
            if result2.returncode != 0:
                try:
                    err = result2.stderr.decode('utf-8', errors='ignore')
                except:
                    err = "未知错误"
                print(f"[错误] PDF生成失败: {err}")
                self.save_state("error")
                return
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] 报告已更新: {REPORT_FILE}")
            self.save_state("ready")
            
            # 显示简要摘要
            self.show_summary(data_file)
            
        except Exception as e:
            print(f"[错误] {e}")
            self.save_state("error")
    
    def save_state(self, status):
        """保存状态"""
        try:
            state = {
                "status": status,
                "last_update": datetime.now().isoformat(),
                "report_path": str(REPORT_FILE)
            }
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def show_summary(self, data_file):
        """显示简要摘要"""
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            tasks = data.get('tasks', [])
            categories = data.get('categories', {})
            
            # 统计
            expired = sum(1 for t in tasks if t['during_hours'] <= 0)
            urgent = sum(1 for t in tasks if t['category'] == 'C类' and t['during_hours'] > 0)
            
            print(f"   [统计] 总计: {len(tasks)}项 | 已过期: {expired}项 | C类紧急: {urgent}项")
            
        except:
            pass


class PollingWatcher:
    """轮询模式（当watchdog不可用时）"""
    
    def __init__(self, interval=2):
        self.interval = interval
        self.last_mtime = 0
        self.handler = DDLHandler()
    
    def start(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [开始] 开始轮询监听 (每{self.interval}秒检查一次)")
        print(f"   监听文件: {TASK_FILE}")
        
        # 初始化状态
        if TASK_FILE.exists():
            self.last_mtime = TASK_FILE.stat().st_mtime
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [文件] 初始文件已存在，生成首份报告...")
            self.handler.regenerate_report()
        
        try:
            while True:
                time.sleep(self.interval)
                
                if not TASK_FILE.exists():
                    continue
                
                current_mtime = TASK_FILE.stat().st_mtime
                if current_mtime != self.last_mtime:
                    self.last_mtime = current_mtime
                    # 模拟文件修改事件
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📝 检测到 Task.txt 变化 (轮询)")
                    self.handler.regenerate_report()
                    
        except KeyboardInterrupt:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [停止]  监听已停止")


def start_watching():
    """启动监听"""
    print("=" * 50)
    print("🎯 DDL Watcher - 任务文件自动监听")
    print("=" * 50)
    
    if not TASK_FILE.exists():
        print(f"[错误] 任务文件不存在: {TASK_FILE}")
        print("请创建该文件后再启动监听")
        return
    
    if WATCHDOG_AVAILABLE:
        # 使用 watchdog 事件驱动
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [开始] 开始事件监听模式")
        print(f"   监听文件: {TASK_FILE}")
        
        event_handler = DDLHandler()
        observer = Observer()
        observer.schedule(event_handler, str(TASK_FILE.parent), recursive=False)
        
        # 先生成首份报告
        event_handler.regenerate_report()
        
        observer.start()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] 监听已启动 (按 Ctrl+C 停止)")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [停止]  监听已停止")
        
        observer.join()
    else:
        # 使用轮询模式
        watcher = PollingWatcher(interval=2)
        watcher.start()


def get_status():
    """获取当前状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"status": "unknown"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DDL Watcher - 任务文件自动监听")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    args = parser.parse_args()
    
    if args.status:
        status = get_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        start_watching()
