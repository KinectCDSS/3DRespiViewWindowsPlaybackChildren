@echo off
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk http://localhost:5173/ --edge-kiosk-type=fullscreen
python "E:\KinectExe\Backend.py"