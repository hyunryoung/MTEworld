@echo off
chcp 65001 > nul
title MTE WORLD 카페 수정발행 - 빌드 스크립트
color 0A

echo.
echo ═══════════════════════════════════════════════════════════
echo   🔨 MTE WORLD 카페 수정발행 빌드 시작
echo ═══════════════════════════════════════════════════════════
echo.

REM Python 및 PyInstaller 확인
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Python이 설치되어 있지 않거나 PATH에 없습니다.
    pause
    exit /b 1
)

where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  PyInstaller가 설치되어 있지 않습니다. 설치를 시작합니다...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo ❌ PyInstaller 설치 실패
        pause
        exit /b 1
    )
)

echo ✅ Python 환경 확인 완료
echo.

REM 버전 정보 (수동 설정)
set VERSION=0.3.1
echo 📦 빌드 버전: v%VERSION%
echo.

REM 이전 빌드 파일 정리
echo 🧹 이전 빌드 파일 정리 중...
if exist "dist" (
    rmdir /s /q "dist"
    echo    - dist 폴더 삭제
)
if exist "build" (
    rmdir /s /q "build"
    echo    - build 폴더 삭제
)
if exist "*.spec" (
    del /q "*.spec"
    echo    - spec 파일 삭제
)
echo.

REM PyInstaller로 빌드
echo 🔧 PyInstaller 빌드 시작...
echo.

pyinstaller --onefile --noconsole --name "카페_수정발행_v%VERSION%" --hidden-import=PySide6 --hidden-import=openai --hidden-import=pandas --hidden-import=PIL --hidden-import=win32clipboard --hidden-import=win32con --hidden-import=psutil --hidden-import=tkinter --exclude-module=PyQt5 --exclude-module=PyQt6 --collect-all PySide6 "카페 수정발행.py"

if %errorlevel% neq 0 (
    echo.
    echo ❌ 빌드 실패!
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════
echo   ✅ 빌드 완료!
echo ═══════════════════════════════════════════════════════════
echo.
echo 📂 빌드 파일: dist\카페_수정발행_v%VERSION%.exe
echo 📊 파일 크기:
dir "dist\카페_수정발행_v%VERSION%.exe" | findstr "카페_수정발행"
echo.
echo 💡 다음 단계:
echo    1. dist 폴더에서 exe 파일을 테스트하세요
echo    2. 정상 작동 확인 후 release.bat을 실행하세요
echo.
pause

