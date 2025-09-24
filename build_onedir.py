"""
PyInstaller onedir 빌드 스크립트
카페 수정발행 프로그램을 단일 폴더로 빌드
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime

def build_application():
    """애플리케이션 빌드"""
    print("🏗️ PyInstaller onedir 빌드 시작...")
    
    # 빌드 설정
    main_script = "카페 수정발행.py"
    app_name = "CafePostingAutomation"
    version = "0.0.1"
    
    # 빌드 명령어 구성
    build_command = [
        "pyinstaller",
        "--onedir",                    # 단일 폴더로 빌드
        "--windowed",                  # GUI 모드 (콘솔 창 숨김)
        "--name", app_name,            # 실행 파일 이름
        "--icon=icon.ico",             # 아이콘 (있는 경우)
        "--add-data", "license_manager_modern.py;.",  # 라이선스 관리자 포함
        "--add-data", "라이선스_사용법.txt;.",         # 사용법 파일 포함
        "--hidden-import", "customtkinter",           # CustomTkinter 포함
        "--hidden-import", "selenium",                # Selenium 포함
        "--hidden-import", "pandas",                  # Pandas 포함
        "--hidden-import", "openpyxl",               # Excel 지원
        "--hidden-import", "webdriver-manager",      # WebDriver 관리자
        "--hidden-import", "PIL",                    # Pillow
        "--hidden-import", "requests",               # Requests
        "--hidden-import", "psutil",                 # 프로세스 유틸
        "--hidden-import", "openai",                 # OpenAI API
        "--exclude-module", "matplotlib",           # 불필요한 모듈 제외
        "--exclude-module", "scipy",                 # 불필요한 모듈 제외
        "--exclude-module", "numpy",                 # 불필요한 모듈 제외 (필요시 제거)
        "--clean",                                   # 이전 빌드 정리
        "--noconfirm",                              # 확인 없이 진행
        main_script
    ]
    
    try:
        # 이전 빌드 폴더 정리
        if os.path.exists("dist"):
            print("🗑️ 이전 빌드 폴더 정리 중...")
            shutil.rmtree("dist")
        
        if os.path.exists("build"):
            shutil.rmtree("build")
        
        # PyInstaller 실행
        print("⚙️ PyInstaller 실행 중...")
        result = subprocess.run(build_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 빌드 성공!")
            
            # 빌드된 폴더 이름 변경
            old_path = f"dist/{app_name}"
            new_path = f"dist/{app_name}_v{version}"
            
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                print(f"📁 빌드 폴더: {new_path}")
                
                # 추가 파일들 복사
                copy_additional_files(new_path)
                
                # 배포용 ZIP 생성
                create_distribution_zip(new_path, version)
                
                print("\n🎉 빌드 완료!")
                print(f"📂 실행 파일: {new_path}/{app_name}.exe")
                print(f"📦 배포 파일: dist/{app_name}_v{version}.zip")
                
        else:
            print("❌ 빌드 실패!")
            print(f"오류: {result.stderr}")
            
    except Exception as e:
        print(f"❌ 빌드 중 오류 발생: {e}")

def copy_additional_files(build_path):
    """추가 파일들 복사"""
    print("📋 추가 파일 복사 중...")
    
    additional_files = [
        "README.md",
        "requirements.txt",
        "라이선스_사용법.txt"
    ]
    
    for file in additional_files:
        if os.path.exists(file):
            try:
                shutil.copy2(file, build_path)
                print(f"  ✅ {file}")
            except Exception as e:
                print(f"  ⚠️ {file} 복사 실패: {e}")

def create_distribution_zip(build_path, version):
    """배포용 ZIP 파일 생성"""
    print("📦 배포용 ZIP 생성 중...")
    
    try:
        import zipfile
        
        app_name = "CafePostingAutomation"
        zip_path = f"dist/{app_name}_v{version}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 빌드 폴더의 모든 파일 추가
            for root, dirs, files in os.walk(build_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_path = os.path.relpath(file_path, build_path)
                    zipf.write(file_path, arc_path)
        
        print(f"✅ ZIP 생성 완료: {zip_path}")
        
        # ZIP 파일 크기 확인
        zip_size = os.path.getsize(zip_path) / (1024 * 1024)  # MB
        print(f"📏 ZIP 크기: {zip_size:.1f} MB")
        
    except Exception as e:
        print(f"❌ ZIP 생성 실패: {e}")

def create_spec_file():
    """PyInstaller spec 파일 생성 (고급 설정용)"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['카페 수정발행.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('license_manager_modern.py', '.'),
        ('라이선스_사용법.txt', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'selenium',
        'pandas',
        'openpyxl',
        'webdriver-manager',
        'PIL',
        'requests',
        'psutil',
        'openai'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CafePostingAutomation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CafePostingAutomation'
)
'''
    
    with open('build_config.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("📄 PyInstaller spec 파일 생성: build_config.spec")

def install_requirements():
    """필요한 패키지 설치"""
    print("📦 필요한 패키지 확인 중...")
    
    required_packages = [
        "pyinstaller",
        "customtkinter",
        "selenium",
        "pandas",
        "openpyxl",
        "webdriver-manager",
        "Pillow",
        "requests",
        "psutil"
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - 설치 필요")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", package], 
                             check=True, capture_output=True)
                print(f"  ✅ {package} 설치 완료")
            except subprocess.CalledProcessError as e:
                print(f"  ❌ {package} 설치 실패: {e}")

def main():
    """메인 함수"""
    print("🏗️ 카페 수정발행 프로그램 빌드 도구")
    print("=" * 50)
    
    # 필요한 패키지 확인
    install_requirements()
    
    print("\n" + "=" * 50)
    
    # spec 파일 생성 (선택사항)
    create_spec_file()
    
    # 빌드 실행
    build_application()
    
    print("\n🎯 빌드 완료!")
    print("📋 다음 단계:")
    print("1. dist 폴더의 실행 파일 테스트")
    print("2. ZIP 파일을 GitHub Release에 업로드")
    print("3. 사용자에게 배포")

if __name__ == "__main__":
    main()
