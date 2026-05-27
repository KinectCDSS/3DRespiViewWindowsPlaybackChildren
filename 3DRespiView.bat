@echo off
title Lancement de 3DRespiView

:: 1. LANCEMENT DU BACKEND PYTHON FLASK
echo [1/3] Demarrage du Backend Flask...
cd /d "C:\Users\kinec\OneDrive\Documents\KinectV1-Respiration-offline\Kinect_V1\bin\Release\net8.0"
start "Backend_Flask" cmd /c "py Backend.py"

:: Attente de 0.1 seconde pour laisser Flask s'initialiser
timeout /t 0.1 /nobreak >nul

:: 2. LANCEMENT DU FRONTEND (REACT / VITE / ETC.)
echo [2/3] Demarrage du Frontend UI...
cd /d "C:\Users\kinec\OneDrive\Documents\KinectV1-Respiration-offline\FrontEnd"
start "Frontend_React" cmd /c "npm run dev"

:: Attente de 0.1 seconde pour que le serveur de dev démarre
timeout /t 0.1 /nobreak >nul

:: 3. OUVERTURE EN PLEIN ÉCRAN MAXIMISÉ (MÉTHODE NATIVE)
echo [3/3] Ouverture de l'application en plein ecran...
:: Le flag /max force Windows à maximiser la fenêtre immédiatement au lancement
start /max msedge --app=http://localhost:5173

echo.
echo =======================================================
echo   3DRespiView est lance avec succes !
echo =======================================================
timeout /t 0.1 >nul