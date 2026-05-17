@echo off
chcp 65001 >nul
cd /d D:\杰哥复盘数据
D:\ProgramData\anaconda3\python.exe auto_update.py --sync-only >> auto_update_daily.log 2>&1
