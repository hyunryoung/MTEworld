import os
import subprocess
import sys

def main():
    """v0.2.0 onefile 빌드 스크립트"""
    
    # 현재 디렉토리 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    
    print("🔨 카페 수정발행 v0.2.0 onefile 빌드 시작...")
    
    # PyInstaller 명령어 구성
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--noconsole',
        '--name', 'CafePostingAutomation_v0.2.0',
        '--add-data', 'license_manager_modern.py;.',
        '--hidden-import', 'numpy',
        '--hidden-import', 'customtkinter',
        '--hidden-import', 'selenium',
        '--hidden-import', 'pandas',
        '--hidden-import', 'openpyxl',
        '--hidden-import', 'webdriver_manager',
        '--hidden-import', 'PIL',
        '--hidden-import', 'requests',
        '--hidden-import', 'psutil',
        '--hidden-import', 'openai',
        '--exclude-module', 'PyQt5',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'scipy',
        '--clean',
        '카페 수정발행.py'
    ]
    
    # 빌드 실행
    try:
        result = subprocess.run(cmd, check=True)
        print("✅ 빌드 성공!")
        print(f"📁 실행 파일 위치: {os.path.join(current_dir, 'dist', 'CafePostingAutomation_v0.2.0.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"❌ 빌드 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
