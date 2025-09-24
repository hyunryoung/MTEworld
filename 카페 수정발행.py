"""
네이버 카페 포스팅 자동화 프로그램
- 게시글 URL에 답글 작성 → 답글 URL 수집 → 댓글 순차 작성
- 프록시 서버 지원 (답글용/댓글용 분리)
- 스레드 1-5개 동시 실행
- 중단/재시작 기능
- 라이선스 인증 시스템
- 자동 업데이트 기능

Version: 0.0.5
Author: License Manager
Last Updated: 2025-09-25
"""

# 🔢 버전 정보
__version__ = "0.0.5"
__build_date__ = "2025-09-25"
__author__ = "License Manager"

# 🔄 업데이트 관련 설정
GITHUB_REPO = "hyunryoung/MTEworld"  # GitHub 저장소 경로
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = __version__

import sys
import os
import time
import threading
import subprocess
import re
import random
import json
import tempfile
import shutil
import csv
import logging
from datetime import datetime
from PIL import Image
import win32clipboard
import win32con
import io
import requests
import pandas as pd
import traceback
import base64
try:
    import openai  # 캡차 해결용 OpenAI API
except ImportError:
    openai = None
    print("⚠️ openai 패키지를 찾을 수 없습니다. 캡차 해결 기능이 비활성화됩니다.")
import tkinter as tk
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid  # 🔥 고유 식별자 생성용 추가
import hashlib  # 🔐 라이선스 시스템용 추가
import platform  # 🔐 라이선스 시스템용 추가
import urllib.request  # 🔄 업데이트 체크용 추가
import zipfile  # 🔄 업데이트 파일 압축 해제용

# 🔐 === 라이선스 시스템 ===
def get_machine_id():
    """PC 고유 식별자 생성"""
    try:
        # CPU 정보
        cpu_id = platform.processor()
        
        # 마더보드 시리얼
        try:
            motherboard_cmd = "wmic baseboard get serialnumber /value"
            motherboard_result = subprocess.getoutput(motherboard_cmd)
            motherboard_id = ""
            for line in motherboard_result.split('\n'):
                if 'SerialNumber=' in line:
                    motherboard_id = line.split('=')[1].strip()
                    break
            if not motherboard_id:
                motherboard_id = "unknown"
        except:
            motherboard_id = "unknown"
        
        # MAC 주소
        try:
            mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0,8*6,8)][::-1])
        except:
            mac_address = "unknown"
        
        # 조합하여 해시 생성
        combined = f"{cpu_id}-{motherboard_id}-{mac_address}"
        machine_id = hashlib.sha256(combined.encode()).hexdigest()[:16].upper()
        return machine_id
    except:
        # 오류 시 대체 방법
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:16].upper()

def check_license():
    """라이선스 확인"""
    machine_id = get_machine_id()
    
    print(f"🔍 라이선스 체크 시작...")
    print(f"📍 현재 작업 디렉토리: {os.getcwd()}")
    print(f"🔑 현재 머신 ID: {machine_id}")
    
    # 여러 가능한 라이선스 파일명 확인
    possible_files = [
        "license.key",
        f"license_{machine_id[:8]}.key",
        f"license_나_{machine_id[:8]}.key"
    ]
    
    # 현재 폴더의 모든 .key 파일도 확인
    try:
        key_files = [f for f in os.listdir('.') if f.endswith('.key')]
        possible_files.extend(key_files)
        # 중복 제거
        possible_files = list(set(possible_files))
    except:
        pass
    
    license_file = None
    for file_name in possible_files:
        if os.path.exists(file_name):
            license_file = file_name
            print(f"📄 라이선스 파일 발견: {os.path.abspath(file_name)}")
            break
    
    if not license_file:
        print(f"❌ 라이선스 파일을 찾을 수 없습니다.")
        print(f"📋 확인한 파일들: {possible_files}")
        show_license_request_dialog(machine_id)
        return False
    
    try:
        print(f"📖 라이선스 파일 읽는 중...")
        with open(license_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
            print(f"📄 파일 내용 (첫 100자): {file_content[:100]}")
            
        # JSON 파싱 시도
        with open(license_file, 'r', encoding='utf-8') as f:
            license_data = json.load(f)
        
        print(f"📋 라이선스 파일 내용:")
        print(f"   - 사용자: {license_data.get('user_name', 'Unknown')}")
        print(f"   - 파일 머신 ID: {license_data.get('machine_id', 'Unknown')}")
        print(f"   - 발급일: {license_data.get('issued_date', 'Unknown')}")
        if 'expires' in license_data:
            print(f"   - 만료일: {license_data.get('expires')}")
        
        # 머신 ID 확인
        file_machine_id = license_data.get('machine_id')
        if file_machine_id != machine_id:
            print(f"❌ 머신 ID 불일치!")
            print(f"   현재 PC: {machine_id}")
            print(f"   파일 내용: {file_machine_id}")
            show_license_error_dialog(f"이 컴퓨터용 라이선스가 아닙니다.\n\n현재 PC: {machine_id}\n라이선스: {file_machine_id}")
            return False
        
        # 만료일 확인 (옵션)
        if 'expires' in license_data:
            try:
                expire_date = datetime.strptime(license_data['expires'], '%Y-%m-%d')
                if datetime.now() > expire_date:
                    print(f"❌ 라이선스가 만료되었습니다: {license_data['expires']}")
                    show_license_error_dialog("라이선스가 만료되었습니다.")
                    return False
                else:
                    print(f"✅ 만료일 확인 통과: {license_data['expires']}")
            except Exception as date_error:
                print(f"⚠️ 날짜 형식 오류: {date_error}")
        
        print(f"✅ 라이선스 인증 성공: {license_data.get('user_name', '사용자')}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ 라이선스 파일 JSON 형식 오류: {str(e)}")
        show_license_error_dialog(f"라이선스 파일이 손상되었습니다.\n새 라이선스 파일을 받아주세요.\n\n오류: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 라이선스 파일 처리 오류: {str(e)}")
        show_license_error_dialog(f"라이선스 파일 오류: {str(e)}")
        return False

def show_license_request_dialog(machine_id):
    """라이선스 요청 다이얼로그"""
    try:
        from tkinter import messagebox
        message = f"""프로그램 사용을 위해 라이선스가 필요합니다.

🔑 이 컴퓨터의 고유 키:
{machine_id}

위 키를 관리자에게 전달하여 라이선스 파일을 받으세요.
받은 license.key 파일을 프로그램과 같은 폴더에 넣어주세요."""
        
        # 클립보드에 머신 ID 복사
        try:
            import pyperclip
            pyperclip.copy(machine_id)
            message += "\n\n📋 머신 키가 클립보드에 복사되었습니다!"
        except:
            pass
        
        messagebox.showinfo("라이선스 필요", message)
    except:
        print(f"🔑 라이선스 필요 - 머신 키: {machine_id}")
        print("위 키를 관리자에게 전달하여 라이선스를 받으세요.")

def show_license_error_dialog(error_msg):
    """라이선스 오류 다이얼로그"""
    try:
        from tkinter import messagebox
        messagebox.showerror("라이선스 오류", error_msg)
    except:
        print(f"❌ 라이선스 오류: {error_msg}")

# 🔄 === 자동 업데이트 시스템 ===
def check_for_updates():
    """GitHub에서 새 버전 확인"""
    try:
        print("🔄 업데이트 확인 중...")
        
        # GitHub API에서 최신 릴리스 정보 가져오기
        with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=10) as response:
            if response.status == 200:
                import json
                data = json.loads(response.read().decode())
                print(f"📋 GitHub API 응답: {data.get('tag_name', 'Unknown')}")
                latest_version = data['tag_name'].replace('v', '')  # v1.0.0 -> 1.0.0
                download_url = None
                
                # assets에서 다운로드 파일 찾기 (.zip 또는 .exe)
                print(f"🔍 릴리스 assets 확인: {len(data.get('assets', []))}개")
                for asset in data.get('assets', []):
                    print(f"  📄 파일: {asset['name']}")
                    # 모든 .exe 파일을 다운로드 대상으로 인식 (더 유연하게)
                    if asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        print(f"  ✅ 다운로드 URL 발견: {download_url}")
                        break
                    # 백업: .zip 파일
                    elif asset['name'].endswith('.zip'):
                        download_url = asset['browser_download_url']
                        print(f"  ⚠️ 백업 다운로드 URL: {download_url}")
                        # break 하지 않고 계속 찾기 (exe 파일 우선)
                
                if compare_versions(CURRENT_VERSION, latest_version) < 0:
                    print(f"🆕 새 버전 발견: v{latest_version} (현재: v{CURRENT_VERSION})")
                    return {
                        'available': True,
                        'version': latest_version,
                        'download_url': download_url,
                        'release_notes': data.get('body', '업데이트 내용이 없습니다.')
                    }
                else:
                    print(f"✅ 최신 버전입니다: v{CURRENT_VERSION}")
                    return {'available': False}
            else:
                print(f"⚠️ 업데이트 확인 실패: HTTP {response.status}")
                return {'available': False, 'error': f'HTTP {response.status}'}
                
    except Exception as e:
        print(f"⚠️ 업데이트 확인 중 오류: {str(e)}")
        return {'available': False, 'error': str(e)}

def compare_versions(current, latest):
    """버전 비교 (semantic versioning)"""
    try:
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        
        current_tuple = version_tuple(current)
        latest_tuple = version_tuple(latest)
        
        if current_tuple < latest_tuple:
            return -1  # current < latest
        elif current_tuple > latest_tuple:
            return 1   # current > latest
        else:
            return 0   # current == latest
    except:
        return 0

def show_update_dialog(update_info):
    """업데이트 다이얼로그 표시"""
    try:
        from tkinter import messagebox
        
        message = f"""🆕 새 버전이 있습니다!

현재 버전: v{CURRENT_VERSION}
최신 버전: v{update_info['version']}

업데이트 내용:
{update_info['release_notes'][:200]}...

지금 업데이트하시겠습니까?
(프로그램이 재시작됩니다)"""
        
        return messagebox.askyesno("업데이트 알림", message)
    except:
        print(f"🆕 새 버전 v{update_info['version']} 사용 가능")
        return False

def download_and_install_update(download_url, version):
    """업데이트 다운로드 및 설치"""
    try:
        print(f"📥 업데이트 다운로드 중... v{version}")
        
        # 임시 폴더에 다운로드
        temp_dir = tempfile.mkdtemp()
        
        # 파일 확장자에 따라 처리 방식 결정
        if download_url.endswith('.exe'):
            # EXE 파일 직접 다운로드
            new_exe_path = os.path.join(temp_dir, "new_version.exe")
            
            print("📥 새 실행 파일 다운로드 중...")
            with urllib.request.urlopen(download_url) as response:
                with open(new_exe_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            # EXE 교체 스크립트 생성
            updater_script = create_exe_update_script(new_exe_path)
            
        else:
            # ZIP 파일 처리 (기존 방식)
            zip_path = os.path.join(temp_dir, f"update_v{version}.zip")
            
            # 다운로드
            with urllib.request.urlopen(download_url) as response:
                with open(zip_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            print("📦 업데이트 파일 압축 해제 중...")
            
            # 압축 해제
            extract_dir = os.path.join(temp_dir, "update")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 업데이트 스크립트 생성
            updater_script = create_update_script(extract_dir)
        
        print("🔄 업데이트 적용 중...")
        print("프로그램이 재시작됩니다...")
        
        # 업데이트 스크립트 실행 후 현재 프로그램 종료
        import subprocess
        subprocess.Popen([sys.executable, updater_script], 
                        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        
        # 현재 프로그램 종료
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ 업데이트 설치 실패: {str(e)}")
        try:
            from tkinter import messagebox
            messagebox.showerror("업데이트 오류", f"업데이트 설치에 실패했습니다:\n{str(e)}")
        except:
            pass

def create_update_script(source_dir):
    """업데이트 스크립트 생성"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(tempfile.gettempdir(), "updater.py")
    
    script_content = f'''
import os
import shutil
import time
import subprocess
import sys

def main():
    print("🔄 업데이트 적용 중...")
    time.sleep(2)  # 메인 프로그램 종료 대기
    
    source_dir = r"{source_dir}"
    target_dir = r"{current_dir}"
    
    try:
        # 기존 파일 백업
        backup_dir = os.path.join(target_dir, "backup_" + str(int(time.time())))
        os.makedirs(backup_dir, exist_ok=True)
        
        # 중요 파일들 백업
        important_files = ["license.key", "license_history.json", "app_config.json"]
        for file in important_files:
            src = os.path.join(target_dir, file)
            if os.path.exists(src):
                shutil.copy2(src, backup_dir)
        
        # 새 파일들 복사
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, source_dir)
                dst_file = os.path.join(target_dir, rel_path)
                
                # 디렉토리 생성
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                
                # 파일 복사
                shutil.copy2(src_file, dst_file)
        
        # 백업된 중요 파일들 복원
        for file in important_files:
            backup_file = os.path.join(backup_dir, file)
            target_file = os.path.join(target_dir, file)
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, target_file)
        
        print("✅ 업데이트 완료!")
        
        # 메인 프로그램 재시작
        main_script = os.path.join(target_dir, "카페 수정발행.py")
        if os.path.exists(main_script):
            subprocess.Popen([sys.executable, main_script])
        
    except Exception as e:
        print(f"❌ 업데이트 실패: {{e}}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    return script_path

def create_exe_update_script(new_exe_path):
    """EXE 파일 직접 교체 스크립트 생성"""
    current_exe = sys.executable if getattr(sys, 'frozen', False) else __file__
    current_dir = os.path.dirname(os.path.abspath(current_exe))
    script_path = os.path.join(tempfile.gettempdir(), "exe_updater.py")
    
    script_content = f'''
import os
import shutil
import time
import subprocess
import sys

def main():
    print("🔄 EXE 업데이트 적용 중...")
    time.sleep(3)  # 메인 프로그램 종료 대기
    
    new_exe_path = r"{new_exe_path}"
    current_exe = r"{current_exe}"
    
    try:
        # 기존 파일 백업
        backup_exe = current_exe + ".backup"
        if os.path.exists(current_exe):
            shutil.copy2(current_exe, backup_exe)
            print(f"💾 기존 파일 백업: {{backup_exe}}")
        
        # 새 파일로 교체
        shutil.copy2(new_exe_path, current_exe)
        print("✅ 업데이트 완료!")
        
        # 업데이트된 프로그램 재시작
        subprocess.Popen([current_exe])
        print("🚀 프로그램 재시작됨")
        
    except Exception as e:
        print(f"❌ 업데이트 실패: {{e}}")
        # 실패 시 백업 파일로 복구
        if os.path.exists(backup_exe):
            try:
                shutil.copy2(backup_exe, current_exe)
                print("🔄 백업 파일로 복구됨")
            except:
                pass
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    return script_path

def get_version_info():
    """버전 정보 반환"""
    return {
        'version': __version__,
        'build_date': __build_date__,
        'author': __author__
    }

def check_and_handle_updates():
    """업데이트 확인 및 처리 (백그라운드)"""
    try:
        # 2초 대기 (메인 UI 로딩 완료 후)
        time.sleep(2)
        
        update_info = check_for_updates()
        
        if update_info.get('available'):
            # 메인 스레드에서 다이얼로그 표시
            if show_update_dialog(update_info):
                if update_info.get('download_url'):
                    download_and_install_update(update_info['download_url'], update_info['version'])
                else:
                    print("❌ 다운로드 URL을 찾을 수 없습니다.")
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning("업데이트 오류", "다운로드 링크를 찾을 수 없습니다.\nGitHub에서 수동으로 다운로드해주세요.")
                    except:
                        pass
        
    except Exception as e:
        print(f"⚠️ 업데이트 처리 중 오류: {e}")

# 고유 식별자 생성 함수
def generate_unique_key(original_url, script_folder, thread_id):
    """작업별 고유 식별자 생성"""
    try:
        # URL에서 ID 부분만 추출 (안전한 문자열로 변환)
        url_id = re.sub(r'[^a-zA-Z0-9]', '_', original_url)[:50]  # 50자 제한
        
        # 스크립트 폴더명에서 키워드 추출
        folder_key = os.path.basename(script_folder) if script_folder else "unknown"
        folder_key = re.sub(r'[^a-zA-Z0-9가-힣]', '_', folder_key)[:30]  # 30자 제한
        
        # 현재 시간 (밀리초)
        timestamp = int(time.time() * 1000)
        
        # 고유 키 생성
        unique_key = f"{url_id}_{folder_key}_t{thread_id}_{timestamp}"
        
        return unique_key[:100]  # 전체 100자 제한
    except:
        # 오류 시 UUID 사용
        return f"fallback_{uuid.uuid4().hex[:20]}"

# 폴더명에서 키워드 부분 추출 함수
def extract_keyword_from_folder_name(folder_name):
    """폴더명에서 키워드 부분만 추출"""
    try:
        parts = folder_name.split('_')
        
        # 언더바로 구분된 부분이 3개 이상인 경우
        if len(parts) >= 3:
            # 빈 문자열이 아닌 중간 부분 찾기
            for i in range(1, len(parts) - 1):  # 첫째와 마지막 제외
                if parts[i].strip():  # 빈 문자열이 아닌 경우
                    return parts[i]
            
            # 모든 중간 부분이 비어있으면 두 번째 부분 반환
            return parts[1] if len(parts) > 1 else folder_name
        else:
            return folder_name  # 형식이 맞지 않으면 원본 반환
    except:
        return folder_name  # 오류 시 원본 반환

# 필요한 패키지 자동 설치
def install_required_packages():
    required_packages = [
        'PySide6',
        'selenium', 
        'pandas',
        'openpyxl',
        'webdriver-manager',
        'Pillow',
        'requests',
        'pyperclip',
        'openai',  # 캡차 해결용 OpenAI API
        'psutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PySide6':
                import PySide6
            elif package == 'selenium':
                import selenium
            elif package == 'pandas':
                import pandas
            elif package == 'openpyxl':
                import openpyxl
            elif package == 'webdriver-manager':
                import webdriver_manager
            elif package == 'Pillow':
                import PIL
            elif package == 'requests':
                import requests
            elif package == 'pyperclip':
                import pyperclip
            # elif package == 'openai':
            #     import openai
            elif package == 'psutil':
                import psutil
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("🔧 필요한 패키지를 설치합니다...")
        for package in missing_packages:
            try:
                print(f"📦 {package} 설치 중...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ {package} 설치 완료!")
            except subprocess.CalledProcessError:
                print(f"❌ {package} 설치 실패!")
                return False
        print("✅ 모든 패키지 설치 완료!")
        os.execv(sys.executable, ['python'] + sys.argv)
    
    return True

# 패키지 설치 확인
if not install_required_packages():
    input("패키지 설치에 실패했습니다. 엔터를 눌러 종료하세요...")
    sys.exit(1)

# 패키지 import
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
        QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, 
        QTextEdit, QCheckBox, QProgressBar, QFileDialog, QMessageBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
        QSplitter, QFrame, QSpinBox, QComboBox, QListWidget, QDialog,
        QDialogButtonBox, QAbstractItemView, QMenu
    )
    from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
    from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QTextCursor, QScreen
    
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import UnexpectedAlertPresentException
    
    import pyperclip
    import gc
    
except ImportError as e:
    print(f"패키지 import 오류: {e}")
    input("엔터를 눌러 종료하세요...")
    sys.exit(1)

# 이미지 클립보드 관련 함수들
def pil_to_dib_bytes(image):
    with io.BytesIO() as output:
        image.save(output, format="BMP")
        bmp_data = output.getvalue()
        return bmp_data[14:]

def set_clipboard_image(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        dib_data = pil_to_dib_bytes(image)
        
        # 이미지 객체 즉시 해제
        del image
        
        if dib_data:
            # 클립보드 열기 재시도 로직 추가
            for attempt in range(5):  # 최대 5번 시도
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
                    win32clipboard.CloseClipboard()
                    
                    # DIB 데이터도 사용 후 해제
                    del dib_data
                    return True
                except Exception as e:
                    if attempt < 4:  # 마지막 시도가 아니면
                        time.sleep(0.5)  # 0.5초 대기 후 재시도
                        continue
                    else:
                        print(f"이미지 클립보드 설정 오류 (5번 시도 실패): {e}")
                        return False
    except Exception as e:
        print(f"이미지 파일 열기 오류: {e}")
        return False

# 진행 상황 관리 클래스
class WorkProgress:
    def __init__(self, file_path="work_progress.json"):
        self.file_path = file_path
        self.data = {
            'current_url_index': 0,
            'current_reply_index': 0,
            'current_comment_index': 0,
            'completed_tasks': [],
            'reply_urls': {}  # {url_index: {reply_index: reply_url}}
        }
        self.max_completed_tasks = 1000  # 최대 보관할 완료 작업 수
    
    def save(self):
        # 오래된 데이터 정리
        self.cleanup_old_data()
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                # 로드 시에도 오래된 데이터 정리
                self.cleanup_old_data()
                return True
        except:
            return False
    
    def cleanup_old_data(self):
        """오래된 완료 작업 데이터 정리"""
        # completed_tasks가 너무 많으면 오래된 것부터 삭제
        if len(self.data['completed_tasks']) > self.max_completed_tasks:
            # 최신 1000개만 유지
            self.data['completed_tasks'] = self.data['completed_tasks'][-self.max_completed_tasks:]
        
        # reply_urls에서 완료된 작업 중 오래된 것 제거
        if self.data['reply_urls']:
            # 현재 completed_tasks에 있는 작업만 유지
            valid_tasks = set(self.data['completed_tasks'])
            new_reply_urls = {}
            
            for url_idx, replies in self.data['reply_urls'].items():
                new_replies = {}
                for reply_idx, reply_url in replies.items():
                    task_id = f"{url_idx}_{reply_idx}"
                    if task_id in valid_tasks or not self.is_task_completed(int(url_idx), int(reply_idx)):
                        new_replies[reply_idx] = reply_url
                
                if new_replies:
                    new_reply_urls[url_idx] = new_replies
            
            self.data['reply_urls'] = new_reply_urls
    
    def is_task_completed(self, url_index, reply_index):
        task_id = f"{url_index}_{reply_index}"
        return task_id in self.data['completed_tasks']
    
    def mark_task_completed(self, url_index, reply_index):
        task_id = f"{url_index}_{reply_index}"
        if task_id not in self.data['completed_tasks']:
            self.data['completed_tasks'].append(task_id)
        self.save()
    
    def save_reply_url(self, url_index, reply_index, reply_url):
        if str(url_index) not in self.data['reply_urls']:
            self.data['reply_urls'][str(url_index)] = {}
        self.data['reply_urls'][str(url_index)][str(reply_index)] = reply_url
        self.save()

# 워커 시그널 클래스
class WorkerSignals(QObject):
    progress = Signal(str)
    progress_with_thread = Signal(str, int)  # 메시지와 thread_id
    status = Signal(str)
    finished = Signal()
    error = Signal(str)
    result_saved = Signal(dict)

# 원고 파싱 클래스
class ScriptParser:
    def __init__(self):
        self.title = ""
        self.content = ""
        self.comments = []
        self.image_paths = []
    
    def parse_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            raise ValueError(f"파일 읽기 오류: {str(e)}")
        
        if not lines:
            raise ValueError("원고 파일이 비어있습니다.")
        
        # 📌 빈 줄들을 건너뛰고 첫 번째 내용 있는 줄을 제목으로 사용
        while lines and not lines[0].strip():
            lines.pop(0)  # 첫 번째 빈 줄 삭제
        
        if not lines:
            raise ValueError(f"❌ 원고 오류: 파일에 내용이 없습니다. 파일: {os.path.basename(file_path)}")
        
        # 제목 (첫 번째 비어있지 않은 줄)
        self.title = lines[0].strip()
        
        # BOM 문자 제거
        if self.title.startswith('\ufeff'):
            self.title = self.title[1:]
        
        # 제목이 여전히 비어있는지 체크 (BOM 제거 후)
        if not self.title or len(self.title.strip()) == 0:
            raise ValueError(f"❌ 원고 오류: 유효한 제목이 없습니다. 파일: {os.path.basename(file_path)}")
        
        # === 구분선 찾기
        sep_indices = []
        for i, line in enumerate(lines):
            if line.strip().startswith('==='):
                sep_indices.append(i)
        
        if len(sep_indices) < 2:
            raise ValueError("===으로 구분된 영역이 부족합니다. (제목/본문/댓글 구분 필요)")
        
        # 본문 추출
        content_lines = lines[sep_indices[0]+1:sep_indices[1]]
        self.content = ''.join(content_lines).strip()
        
        # 이미지 태그 처리
        self.content, self.image_paths = self.process_image_tags(self.content, os.path.dirname(file_path))
        
        # 댓글 추출
        comment_lines = lines[sep_indices[1]+1:]
        self.comments = self.parse_comments(comment_lines)
        
        return True
    
    def process_image_tags(self, content, base_dir):
        """<지정사진X> 태그를 <이미지마커:X>로 치환하고, 이미지 경로 반환"""
        processed = content
        image_paths = []
        pattern = r"지정사진(\d+)"
        
        matches = re.findall(pattern, processed)
        for idx, photo_number in enumerate(matches):
            possible_extensions = ['.jpg', '.jpeg', '.png']
            found_image = None
            
            for ext in possible_extensions:
                image_filename = f"지정사진{photo_number}{ext}"
                image_path = os.path.join(base_dir, image_filename)
                if os.path.exists(image_path):
                    found_image = image_path
                    break
            
            if found_image:
                image_paths.append(found_image)
                processed = processed.replace(f"지정사진{photo_number}", f"<이미지마커:{idx}>", 1)
            else:
                processed = processed.replace(f"지정사진{photo_number}", '', 1)
        
        return processed, image_paths
    
    def parse_comments(self, comment_lines):
        """댓글 파싱 (eoeotrmf.py 방식 - 빈줄로 그룹 구분, 여러줄 댓글 지원)"""
        comments = []
        group_idx = 0
        i = 0
        
        while i < len(comment_lines):
            # 빈 줄들을 건너뛰면서 그룹 구분
            while i < len(comment_lines) and comment_lines[i].strip() == '':
                i += 1
            
            if i >= len(comment_lines):
                break
                
            # 현재 그룹의 댓글들을 수집
            group_blocks = []
            current_block = None
            
            while i < len(comment_lines) and comment_lines[i].strip() != '':
                line = comment_lines[i].rstrip()  # 오른쪽 공백만 제거
                
                # 새로운 댓글 시작 패턴 확인
                is_new_comment = False
                match_type = None
                match_obj = None
                
                # 🔍 디버깅: 매칭 시도하는 라인 로그
                print(f"[DEBUG] 파싱 라인: '{line}'")
                
                # 아이디N: 패턴 (관대한 공백 허용: 아이디1:, 아이디 1:, 아이디 1 : 등)
                m = re.match(r'아이디\s*(\d+)\s*:\s*(.+)', line)
                if m:
                    is_new_comment = True
                    match_type = 'id_num'
                    match_obj = m
                    print(f"[DEBUG] 매칭됨: 아이디{m.group(1)} → 타입: {match_type}")
                else:
                    # 작성자: 패턴 (엄격한 매칭)
                    m = re.match(r'작성자\s*:\s*(.+)', line)
                    if m:
                        is_new_comment = True
                        match_type = 'author'
                        match_obj = m
                        print(f"[DEBUG] 매칭됨: 작성자 → 타입: {match_type}")
                    else:
                        print(f"[DEBUG] 매칭 실패: 패턴 없음")
                
                if is_new_comment:
                    # 이전 블록이 있으면 저장
                    if current_block:
                        group_blocks.append(current_block)
                    
                    # 새 블록 시작
                    if match_type == 'id_num':
                        current_block = {
                            'type': match_type,
                            'id_num': match_obj.group(1),
                            'content': [match_obj.group(2).strip()]
                        }
                    elif match_type == 'author':
                        current_block = {
                            'type': match_type,
                            'content': [match_obj.group(1).strip()]
                        }
                else:
                    # 패턴에 맞지 않는 줄은 이전 블록의 연속으로 처리 (여러줄 댓글)
                    if current_block:
                        current_block['content'].append(line)
                    else:
                        # 첫 줄이 패턴에 맞지 않으면 건너뛰기
                        pass
                
                i += 1
            
            # 마지막 블록 저장
            if current_block:
                group_blocks.append(current_block)
            
            # 블록들을 댓글 구조로 변환 (eoeotrmf.py 방식)
            if group_blocks:
                stack = []  # (idx, level, id_num)
                last_idx = None
                id_num_to_idx = {}
                
                for block_idx, block in enumerate(group_blocks):
                    # 여러 줄을 하나의 내용으로 합치기
                    content = '\n'.join(block['content']).strip()
                    if not content:
                        continue
                    
                    if block_idx == 0:
                        # 그룹의 첫 댓글 (항상 level = 0)
                        parent_idx = None
                        level = 0
                    else:
                        # 아이디N의 경우 같은 번호를 찾아서 대댓글로
                        if block['type'] == 'id_num' and block['id_num'] in id_num_to_idx:
                            parent_idx = id_num_to_idx[block['id_num']]
                            level = stack[-1][1] + 1 if stack else 1
                        else:
                            parent_idx = stack[-1][0] if stack else None
                            level = stack[-1][1] + 1 if stack else 1
                    
                    # 🔍 디버깅: 댓글 타입 변환 로그
                    final_type = 'author' if block['type'] == 'author' else 'comment'
                    print(f"[DEBUG] 블록 타입: {block['type']} → 최종 타입: {final_type}")
                    
                    comment = {
                        'level': level,
                        'type': final_type,
                        'content': content,
                        'parent_idx': parent_idx,
                        'group': group_idx
                    }
                    
                    # id_num이 있는 경우 추가
                    if block['type'] == 'id_num':
                        comment['id_num'] = block['id_num']
                    
                    comments.append(comment)
                    idx = len(comments) - 1
                    
                    # id_num 매핑 저장
                    if block['type'] == 'id_num':
                        id_num_to_idx[block['id_num']] = idx
                    
                    stack.append((idx, level, block.get('id_num')))
                    last_idx = idx
                
                group_idx += 1
        
        return comments

# 메인 워커 클래스
class CafePostingWorker(QThread):
    def __init__(self, config, main_window=None):
        super().__init__()
        self.config = config
        self.main_window = main_window  # 🔄 공용 풀 시스템을 위한 메인 윈도우 참조
        self.is_running = True
        self.signals = WorkerSignals()
        self.progress = WorkProgress()
        self.drivers = {}  # 스레드별 드라이버
        self.blocked_accounts = set()  # 차단된 계정 목록
        
        # 멀티쓰레드 안전성을 위한 Lock들
        self.blocked_accounts_lock = threading.Lock()
        self.drivers_lock = threading.Lock() 
        self.clipboard_lock = threading.Lock()
        
        # 쓰레드별 계정 할당
        self.thread_accounts = self.distribute_accounts_by_thread()
        
        # 쓰레드별 프록시 할당
        self.thread_proxies = self.distribute_proxies_by_thread()
        
        # 쓰레드별 크롬 프로세스 추적
        self.thread_chrome_pids = {}
        
        # 🔄 스레드별 아이디-계정 매핑 테이블 (같은 아이디는 같은 계정 사용)
        self.thread_id_account_mapping = {}  # {thread_id: {'아이디1': account, '아이디2': account, ...}}
        
        # 🆔 계정별 사용 횟수 추적
        self.account_usage_count = {}  # {account_id: 현재_사용_횟수}
        self.account_usage_lock = threading.Lock()  # 계정 사용 횟수 락
        
        # 네트워크 상태 캐싱
        self.network_cache = {
            'status': 'fast',
            'base_wait': 2,
            'adjusted_max_wait': 5,
            'last_check': 0,
            'cache_duration': 60  # 60초 동안 캐시 유효
        }
        
        # 폴더명 카운터 (preview와 동일한 번호 체계)
        self.folder_count = {}
        self.folder_count_lock = threading.Lock()
        self.network_cache_lock = threading.Lock()
    
    def distribute_proxies_by_thread(self):
        """스레드별 프록시 안전한 분배"""
        thread_count = self.config.get('thread_count', 1)
        
        # 답글 프록시 분배
        reply_proxies = self.config.get('reply_proxies', [])
        thread_reply_proxies = {i: [] for i in range(thread_count)}
        
        for idx, proxy in enumerate(reply_proxies):
            thread_id = idx % thread_count
            thread_reply_proxies[thread_id].append(proxy)
        
        # 댓글 프록시 분배
        comment_proxies = self.config.get('comment_proxies', [])
        thread_comment_proxies = {i: [] for i in range(thread_count)}
        
        for idx, proxy in enumerate(comment_proxies):
            thread_id = idx % thread_count
            thread_comment_proxies[thread_id].append(proxy)
        
        # 결과 로깅
        for thread_id in range(thread_count):
            reply_proxy_count = len(thread_reply_proxies[thread_id])
            comment_proxy_count = len(thread_comment_proxies[thread_id])
            # self.signals.progress.emit(f"🌐 스레드{thread_id}: 답글프록시 {reply_proxy_count}개, 댓글프록시 {comment_proxy_count}개 할당")
        
        return {
            'reply': thread_reply_proxies,
            'comment': thread_comment_proxies
        }
    
    def get_thread_proxies(self, thread_id, account_type):
        """스레드별 전용 프록시 목록 반환"""
        return self.thread_proxies[account_type].get(thread_id, [])
    
    def distribute_accounts_by_thread(self):
        """쓰레드별 계정 안전한 분배"""
        thread_count = self.config.get('thread_count', 1)
        
        # 🆕 답글 계정 분배 (메인 윈도우 풀에서 가져오기)
        if self.main_window and hasattr(self.main_window, 'available_reply_accounts'):
            reply_accounts = self.main_window.available_reply_accounts.copy()
        else:
            reply_accounts = self.config.get('reply_accounts', [])
        
        thread_reply_accounts = {i: [] for i in range(thread_count)}
        
        for idx, account in enumerate(reply_accounts):
            thread_id = idx % thread_count
            thread_reply_accounts[thread_id].append(account)
        
        # 댓글 계정 분배 (더 많으므로 균등 분배)
        comment_accounts = self.config.get('comment_accounts', [])
        thread_comment_accounts = {i: [] for i in range(thread_count)}
        
        for idx, account in enumerate(comment_accounts):
            thread_id = idx % thread_count
            thread_comment_accounts[thread_id].append(account)
        
        # 🔍 디버그 로깅
        total_reply_accounts = len(reply_accounts)
        self.signals.progress.emit(f"🔍 워커 디버그: 총 답글 계정 {total_reply_accounts}개")
        
        # 결과 로깅
        for thread_id in range(thread_count):
            reply_count = len(thread_reply_accounts[thread_id])
            comment_count = len(thread_comment_accounts[thread_id])
            self.signals.progress.emit(f"🎯 스레드{thread_id}: 답글계정 {reply_count}개, 댓글계정 {comment_count}개 할당")
        
        return {
            'reply': thread_reply_accounts,
            'comment': thread_comment_accounts
        }
    
    def get_thread_accounts(self, thread_id, account_type):
        """쓰레드별 전용 계정 목록 반환"""
        with self.blocked_accounts_lock:
            available_accounts = []
            thread_accounts = self.thread_accounts[account_type].get(thread_id, [])
            
            for account in thread_accounts:
                if account[0] not in self.blocked_accounts:
                    available_accounts.append(account)
            
            return available_accounts
    
    def check_network_health(self):
        """네트워크 상태 확인 및 대기 시간 반환 (캐싱 적용)"""
        with self.network_cache_lock:
            current_time = time.time()
            
            # 캐시가 유효한 경우 캐시된 값 반환
            if current_time - self.network_cache['last_check'] < self.network_cache['cache_duration']:
                return (
                    self.network_cache['status'],
                    self.network_cache['base_wait'],
                    self.network_cache['adjusted_max_wait']
                )
            
            # 캐시가 만료된 경우에만 실제 네트워크 체크
            try:
                start_time = time.time()
                response = requests.get("https://www.google.com", timeout=5)  # 타임아웃 줄임
                response_time = time.time() - start_time
                
                if response_time > 3:  # 3초 이상이면 느림
                    # self.signals.progress.emit(f"⚠️ 느린 네트워크 (응답시간: {response_time:.1f}초)")
                    status, base_wait, adjusted_max_wait = "slow", 3, 8
                elif response_time > 1.5:  # 1.5초 이상이면 보통
                    status, base_wait, adjusted_max_wait = "normal", 2, 5
                else:  # 1.5초 이하면 빠름
                    status, base_wait, adjusted_max_wait = "fast", 1, 3
                
                # 캐시 업데이트
                self.network_cache.update({
                    'status': status,
                    'base_wait': base_wait,
                    'adjusted_max_wait': adjusted_max_wait,
                    'last_check': current_time
                })
                
                return status, base_wait, adjusted_max_wait
                
            except Exception as e:
                # 네트워크 오류 시에도 캐시 업데이트
                self.network_cache.update({
                    'status': 'disconnected',
                    'base_wait': 5,
                    'adjusted_max_wait': 10,
                    'last_check': current_time
                })
                return 'disconnected', 5, 10
    
    def wait_for_page_load(self, driver, timeout=30):
        """페이지가 완전히 로드될 때까지 대기"""
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except Exception as e:
            # self.signals.progress.emit(f"⚠️ 페이지 로딩 시간 초과: {str(e)}")
            return False
    
    def wait_for_element_with_retry(self, driver, by, selector, max_wait=30, retry_count=3, element_name="요소"):
        """네트워크 상태에 따라 동적으로 대기하는 함수"""
        network_status, base_wait, adjusted_max_wait = self.check_network_health()
        
        for attempt in range(retry_count):
            try:
                # 네트워크 상태에 따른 대기 시간 조정 (📌 제한 해제)
                if network_status == "very_slow":
                    wait_time = max_wait * 2
                elif network_status == "slow":
                    wait_time = max_wait * 1.5
                elif network_status == "disconnected":
                    wait_time = max_wait * 3
                else:
                    wait_time = max_wait
                
                element = WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except Exception as e:
                if attempt < retry_count - 1:
                    # self.signals.progress.emit(f"⚠️ {element_name} 로딩 실패, 재시도 중... ({attempt + 1}/{retry_count})")
                    # 점진적으로 대기 시간 증가
                    time.sleep(base_wait * (attempt + 1))
                else:
                    # self.signals.progress.emit(f"❌ {element_name} 로딩 최종 실패: {str(e)}")
                    raise e
    
    def smart_sleep(self, base_time=1, reason="대기"):
        """스마트 대기 (네트워크 체크 캐싱 적용)"""
        network_status, _, _ = self.check_network_health()
        
        if network_status == "very_slow":
            sleep_time = base_time * 3
        elif network_status == "slow":
            sleep_time = base_time * 2
        elif network_status == "disconnected":
            sleep_time = base_time * 4
        else:
            sleep_time = base_time
        
        # 📌 최대 5초로 제한
        sleep_time = min(sleep_time, 5)
        
        # if sleep_time > base_time:
        #     self.signals.progress.emit(f"⏳ {reason} 중... (네트워크 상태: {network_status}, {sleep_time:.1f}초)")
        
        time.sleep(sleep_time)
    
    def wait_for_existing_comments_to_load(self, driver, max_wait=20):
        """기존 댓글들이 모두 로딩될 때까지 대기 (대댓글 찾기 안정성 향상)"""
        try:
            # self.signals.progress.emit("⏳ 기존 댓글들이 로딩될 때까지 대기 중...")
            
            # iframe 진입 시도
            try:
                iframe = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, "iframe#cafe_main", 
                    max_wait=5, element_name="iframe#cafe_main"
                )
                driver.switch_to.frame(iframe)
                iframe_entered = True
            except:
                self.signals.progress.emit("ℹ️ iframe 진입 불필요")
                iframe_entered = False
            
            # 댓글 목록 로딩 대기
            start_time = time.time()
            stable_count = 0  # 안정된 상태 카운터
            last_comment_count = -1
            
            while time.time() - start_time < max_wait:
                try:
                    # 로딩 스피너나 표시가 있는지 확인
                    loading_indicators = driver.find_elements(By.CSS_SELECTOR, 
                        '.loading, .spinner, [class*="loading"], [class*="spinner"]')
                    
                    if loading_indicators:
                        # 로딩 중이면 계속 대기
                        # self.signals.progress.emit("⏳ 댓글 로딩 중... (로딩 표시 확인됨)")
                        time.sleep(1)
                        stable_count = 0
                        continue
                    
                    # 댓글 요소들 개수 확인
                    comment_selectors = [
                        '.comment_list .comment_item',
                        '.comment_list li', 
                        '.comment_box',
                        '.comment_text_box',
                        'div[class*="comment"]'
                    ]
                    
                    current_comment_count = 0
                    for selector in comment_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                current_comment_count = len(elements)
                                break
                        except:
                            continue
                    
                    # 댓글 개수가 안정적이면 카운터 증가
                    if current_comment_count == last_comment_count:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_comment_count = current_comment_count
                        # self.signals.progress.emit(f"📊 댓글 {current_comment_count}개 확인됨)")
                    
                    # 3초 연속 안정적이면 로딩 완료로 판단
                    if stable_count >= 6:  # 0.5초 × 6 = 3초
                        elapsed = time.time() - start_time
                        self.signals.progress.emit(f"✅ 댓글 로딩 완료 확인 (총 {current_comment_count}개, {elapsed:.1f}초 대기)")
                        break
                    
                    time.sleep(0.5)  # 0.5초마다 체크
                    
                except Exception as e:
                    # 오류 발생시 계속 진행
                    time.sleep(0.5)
                    continue
            else:
                # 타임아웃 발생
                self.signals.progress.emit(f"⚠️ 댓글 로딩 대기 타임아웃 ({max_wait}초)")
            
            # iframe에서 나가기
            if iframe_entered:
                try:
                    driver.switch_to.default_content()
                except:
                    pass
            
            # 추가 안전 대기
            self.smart_sleep(2, "댓글 로딩 완료 후 안전 대기")
            
        except Exception as e:
            self.signals.progress.emit(f"⚠️ 댓글 로딩 대기 중 오류: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            self.smart_sleep(3, "댓글 로딩 대기 실패 후 기본 대기")
    
    def safe_click_with_retry(self, driver, element, max_retries=3, element_name="요소"):
        """안전한 클릭 함수 (재시도 포함, 새 탭 환경 최적화)"""
        for attempt in range(max_retries):
            try:
                # 요소를 뷰포트 중앙으로 스크롤
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    self.smart_sleep(1, "요소 스크롤 후 대기")
                except:
                    pass
                
                # 요소가 클릭 가능할 때까지 대기 (새 탭에서는 더 길게)
                WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable(element)
                )
                
                # 일반 클릭 시도
                element.click()
                return True
                
            except Exception as e:
                # JavaScript 클릭 시도
                try:
                    driver.execute_script("arguments[0].click();", element)
                    self.signals.progress.emit(f"✅ {element_name} JavaScript 클릭 성공")
                    return True
                except Exception as js_e:
                    if attempt < max_retries - 1:
                        self.signals.progress.emit(f"⚠️ {element_name} 클릭 실패, 재시도 중... ({attempt + 1}/{max_retries})")
                        self.smart_sleep(2, f"{element_name} 클릭 재시도")
                    else:
                        self.signals.progress.emit(f"❌ {element_name} 클릭 최종 실패: 일반클릭={str(e)}, JS클릭={str(js_e)}")
                        return False
    
    def safe_input_text(self, driver, element, text, element_name="입력 필드"):
        """안전한 텍스트 입력 함수"""
        try:
            # 기존 텍스트 삭제
            element.clear()
            self.smart_sleep(0.5, "텍스트 삭제 후 대기")
            
            # 네트워크 상태에 따른 입력 속도 조절
            network_status, _, _ = self.check_network_health()
            
            if network_status in ["very_slow", "slow"]:
                # 느린 네트워크에서는 한 번에 입력
                element.send_keys(text)
                self.signals.progress.emit(f"✅ {element_name} 입력 완료 (일괄 입력)")
            else:
                # 빠른 네트워크에서는 자연스럽게 입력
                for char in text:
                    element.send_keys(char)
                    time.sleep(0.02)  # 매우 짧은 대기
                self.signals.progress.emit(f"✅ {element_name} 입력 완료 (자연스러운 입력)")
            
            return True
        except Exception as e:
            self.signals.progress.emit(f"❌ {element_name} 입력 실패: {str(e)}")
            return False
        
    def run(self):
        try:
            self.signals.progress.emit("🚀 작업을 시작합니다...")
            self.progress.load()
            
            # 🎯 스레드별 계정 분배 실행
            self.thread_accounts = self.distribute_accounts_by_thread()
            self.signals.progress.emit("✅ 스레드별 계정 분배 완료")
            
            # 스레드별로 작업 분배 (답글 단위로 균등 분배)
            thread_count = self.config['thread_count']
            url_count = len(self.config['urls'])
            
            # 🆕 ID 기준 작업 목록 생성 (아이디별 원고 순서 → 스레드 순차 배정)
            # ID 기준 매핑 데이터 사용 (config에서 직접 접근)
            id_script_mapping = self.config.get('id_script_mapping', {})
            
            if id_script_mapping:
                # 새로운 ID 기준 방식
                all_tasks = []
                account_ids = list(id_script_mapping.keys())
                max_scripts_per_account = max(len(data['scripts']) for data in id_script_mapping.values()) if id_script_mapping else 0
                
                # 아이디별 1번 원고부터 순서대로 작업 생성
                for script_index in range(max_scripts_per_account):
                    for account_id in account_ids:
                        mapping_data = id_script_mapping[account_id]
                        if script_index < len(mapping_data['scripts']):
                            # (account_id, script_index, script_folder, assigned_url)
                            all_tasks.append((
                                account_id, 
                                script_index, 
                                mapping_data['scripts'][script_index],
                                mapping_data['assigned_url']
                            ))
                
                self.signals.progress.emit(f"📋 ID 기준 전체 작업: {len(all_tasks)}개")
                
                # 🆕 계정별 그룹화 후 스레드 분배 (같은 계정은 같은 스레드에서 처리)
                thread_work_list = [[] for _ in range(thread_count)]
                
                # 🆕 실제 계정명으로 작업 그룹화 (row 번호 제거)
                account_tasks = {}
                for task in all_tasks:
                    account_id = task[0]  # (account_id, script_index, script_folder, assigned_url)
                    # sat1926_row1 → sat1926으로 변환
                    real_account_id = account_id.split('_row')[0] if '_row' in account_id else account_id
                    
                    if real_account_id not in account_tasks:
                        account_tasks[real_account_id] = []
                    account_tasks[real_account_id].append(task)
                
                # 계정별 그룹을 스레드에 분배
                account_groups = list(account_tasks.items())
                for group_idx, (real_account_id, tasks) in enumerate(account_groups):
                    thread_id = group_idx % thread_count
                    thread_work_list[thread_id].extend(tasks)
                    self.signals.progress.emit(f"👤 계정 {real_account_id}: 스레드{thread_id+1}에 {len(tasks)}개 작업 할당")
                
            else:
                # 기존 URL 기준 방식 (호환성 유지)
                all_tasks = []
                for url_index in range(url_count):
                    url = self.config['urls'][url_index]
                    script_folders = self.config['url_script_mapping'].get(url, [])
                    for reply_index in range(len(script_folders)):
                        all_tasks.append((url_index, reply_index))
                
                self.signals.progress.emit(f"📋 URL 기준 전체 작업: {len(all_tasks)}개")
                
                # 라운드 로빈 방식 배정
                thread_work_list = [[] for _ in range(thread_count)]
                for task_idx, task in enumerate(all_tasks):
                    thread_id = task_idx % thread_count
                    thread_work_list[thread_id].append(task)
            
            # 빈 스레드 제거 및 작업 배분 현황 출력
            thread_work_list = [(thread_id, tasks) for thread_id, tasks in enumerate(thread_work_list) if tasks]
            
            for thread_id, tasks in thread_work_list:
                self.signals.progress.emit(f"📌 스레드{thread_id+1}: {len(tasks)}개 작업 할당")
            
            if not thread_work_list:
                self.signals.progress.emit("⚠️ 처리할 작업이 없습니다.")
                return
            
            # 진짜 멀티스레딩 실행!
            self.signals.progress.emit(f"🚀 {len(thread_work_list)}개 스레드로 병렬 작업 시작!")
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                # 각 스레드에 작업 할당
                future_to_thread = {}
                for idx, (thread_id, tasks) in enumerate(thread_work_list):
                    # 첫 번째 스레드는 바로 시작, 나머지는 지연 시작
                    if idx > 0:
                        delay = idx * 7  # 각 스레드마다 7초씩 지연
                        self.signals.progress.emit(f"⏳ 스레드{thread_id+1} {delay}초 후 시작 예정...")
                        time.sleep(delay)
                    
                    future = executor.submit(self.process_thread_work, thread_id, tasks)
                    future_to_thread[future] = thread_id
                    self.signals.progress.emit(f"🚀 스레드{thread_id+1} 작업 시작!")
                
                # 결과 수집 (완료되는 대로)
                for future in as_completed(future_to_thread):
                    thread_id = future_to_thread[future]
                    try:
                        future.result()  # 예외 발생 시 여기서 catch
                        self.signals.progress.emit(f"✅ 스레드{thread_id} 작업 완료!")
                    except Exception as e:
                        self.signals.progress.emit(f"❌ 스레드{thread_id} 작업 실패: {str(e)}")
            
            self.signals.progress.emit("🎉 모든 작업이 완료되었습니다!")
            self.signals.finished.emit()
            
        except Exception as e:
            self.signals.error.emit(f"작업 중 오류: {str(e)}")
        finally:
            self.cleanup()
    
    def process_thread_work(self, thread_id, task_list):
        """스레드별 작업 처리 (답글 작업 단위)"""
        self.emit_progress(f"🏃 스레드{thread_id+1} 작업 시작 - 총 {len(task_list)}개 작업", thread_id)
        
        for task_idx, task in enumerate(task_list):
            if not self.is_running:
                break
            
            # 🆕 새로운 ID 기준 task 형태 vs 기존 URL 기준 task 형태 구분
            if len(task) == 4:  # ID 기준: (account_id, script_index, script_folder, assigned_url)
                account_id, script_index, script_folder, assigned_url = task
                task_name = f"{account_id}-원고{script_index+1}"
                
                # 🔗 연쇄 URL 시스템: 이전 작업에서 생성된 새로운 URL이 있으면 사용
                if hasattr(self, 'next_urls') and thread_id in self.next_urls:
                    assigned_url = self.next_urls[thread_id]
                    self.emit_progress(f"🔗 [연쇄시스템] 새로운 URL 사용: {assigned_url[:50]}...", thread_id)
                
                # 🔧 로그 빈도 줄이기: 5개마다 한 번씩만 출력
                if task_idx % 5 == 0 or task_idx == len(task_list) - 1:
                    self.emit_progress(f"📍 스레드{thread_id+1} - 작업 {task_idx+1}/{len(task_list)} 진행 중 ({task_name})", thread_id)
                
                # ID 기준 완료 확인 (임시로 account_id를 문자열 해시로 변환)
                temp_url_index = hash(account_id) % 1000  # 임시 인덱스
                if self.progress.is_task_completed(temp_url_index, script_index):
                    # 🔥 로그 스팸 최적화: 스킵 로그 제거 (답글방식에서 가져온 최적화)
                    continue
                
                try:
                    # 🔍 디버그: 각 스레드가 처리하는 URL 확인
                    self.emit_progress(f"🔍 스레드{thread_id+1} - {account_id} → URL: {assigned_url[:50]}...", thread_id)
                    self.process_single_id_task(thread_id, account_id, script_index, script_folder, assigned_url)
                    
                    # 🔥 15초 안정화 대기 추가
                    self.smart_sleep(15, f"[스레드{thread_id+1}] {account_id}-원고{script_index+1} 완료 후 안정화 대기")
                    self.emit_progress(f"⏳ 작업 완료 후 15초 안정화 대기 중...", thread_id)
                    
                    self.progress.mark_task_completed(temp_url_index, script_index)
                    # 🔧 완료 로그도 5개마다만
                    if task_idx % 5 == 0 or task_idx == len(task_list) - 1:
                        self.emit_progress(f"✅ 스레드{thread_id+1} - 작업 {task_idx+1}/{len(task_list)} 완료", thread_id)
                    
                    # 🧹 10개마다 캐시 정리 (메모리 관리)
                    if (task_idx + 1) % 10 == 0:
                        self.emit_progress(f"🧹 [스레드{thread_id+1}] 10개 작업 완료 - 캐시 정리 중...", thread_id)
                        try:
                            import glob
                            temp_dirs = glob.glob(f"{tempfile.gettempdir()}/chrome_t{thread_id}_*")
                            for temp_dir in temp_dirs:
                                cache_path = os.path.join(temp_dir, "Cache")
                                if os.path.exists(cache_path):
                                    shutil.rmtree(cache_path, ignore_errors=True)
                        except:
                            pass
                    
                except Exception as e:
                    self.emit_progress(f"❌ 작업 실패: {task_name} - {str(e)}", thread_id)
                    continue
                    
            else:  # 기존 URL 기준: (url_index, reply_index)
                url_index, reply_index = task
                task_name = f"URL{url_index+1}-답글{reply_index+1}"
                
                # 🔗 연쇄 URL 시스템: 이전 작업에서 생성된 새로운 URL이 있으면 사용
                url = self.config['urls'][url_index]
                if hasattr(self, 'next_urls') and thread_id in self.next_urls:
                    url = self.next_urls[thread_id]
                    self.emit_progress(f"🔗 [연쇄시스템] 새로운 URL 사용: {url[:50]}...", thread_id)
                
                # 🔧 로그 빈도 줄이기: 5개마다 한 번씩만 출력
                if task_idx % 5 == 0 or task_idx == len(task_list) - 1:
                    self.emit_progress(f"📍 스레드{thread_id+1} - 작업 {task_idx+1}/{len(task_list)} 진행 중 ({task_name})", thread_id)
                
                if self.progress.is_task_completed(url_index, reply_index):
                    # 🔧 스킵 로그 제거 (너무 많음)
                    continue
                
                script_folders = self.config['url_script_mapping'].get(self.config['urls'][url_index], [])  # 원본 URL로 스크립트 찾기
                script_folder = script_folders[reply_index] if reply_index < len(script_folders) else None
                
                try:
                    self.process_single_task(thread_id, url_index, reply_index, url, script_folder)
                    
                    # 🔥 15초 안정화 대기 추가
                    self.smart_sleep(15, f"[스레드{thread_id+1}] URL{url_index+1}-답글{reply_index+1} 완료 후 안정화 대기")
                    self.emit_progress(f"⏳ 작업 완료 후 15초 안정화 대기 중...", thread_id)
                    
                    self.progress.mark_task_completed(url_index, reply_index)
                    # 🔧 완료 로그도 5개마다만
                    if task_idx % 5 == 0 or task_idx == len(task_list) - 1:
                        self.emit_progress(f"✅ 스레드{thread_id+1} - 작업 {task_idx+1}/{len(task_list)} 완료", thread_id)
                    
                    # 🧹 10개마다 캐시 정리 (메모리 관리)
                    if (task_idx + 1) % 10 == 0:
                        self.emit_progress(f"🧹 [스레드{thread_id+1}] 10개 작업 완료 - 캐시 정리 중...", thread_id)
                        try:
                            import glob
                            temp_dirs = glob.glob(f"{tempfile.gettempdir()}/chrome_t{thread_id}_*")
                            for temp_dir in temp_dirs:
                                cache_path = os.path.join(temp_dir, "Cache")
                                if os.path.exists(cache_path):
                                    shutil.rmtree(cache_path, ignore_errors=True)
                        except:
                            pass
                    
                except Exception as e:
                    self.emit_progress(f"❌ 작업 실패: {task_name} - {str(e)}", thread_id)
                    continue
        
        self.emit_progress(f"🎯 스레드{thread_id+1} 모든 작업 완료!", thread_id)
    
    def is_valid_reply_url(self, url):
        """🔥 유효한 답글 URL인지 검사 (답글방식에서 가져온 최적화)"""
        if not url:
            return False
        
        # 무효한 패턴들
        invalid_patterns = [
            "ca-fe/cafes",  # 답글 작성 페이지 패턴
            "/reply",       # 답글 작성 중 표시
            "iframe_url_utf8"  # iframe 파라미터
        ]
        
        for pattern in invalid_patterns:
            if pattern in url:
                return False
        
        # 유효한 패턴: https://cafe.naver.com/{카페별칭}/{글번호}
        import re
        valid_pattern = r"^https://cafe\.naver\.com/[^/]+/\d+$"
        return bool(re.match(valid_pattern, url))
    
    def emit_progress(self, message, thread_id=None):
        """스레드별 로그 전송 헬퍼 함수"""
        if thread_id is not None:
            self.signals.progress_with_thread.emit(message, thread_id)
        else:
            self.signals.progress.emit(message)
    
    def save_result_immediately(self, result):
        """🔥 실시간 결과 저장 - 작업 완료 즉시 백업 파일에 저장"""
        try:
            # 백업 파일 경로 생성
            timestamp = datetime.now().strftime("%Y%m%d")
            backup_file = f"실시간백업_{timestamp}.csv"
            
            # 기존 백업 파일이 있으면 읽기
            existing_results = []
            if os.path.exists(backup_file):
                try:
                    import pandas as pd
                    existing_df = pd.read_csv(backup_file, encoding='utf-8-sig')
                    existing_results = existing_df.to_dict('records')
                except:
                    pass
            
            # 새 결과 추가
            existing_results.append(result)
            
            # CSV로 저장
            import pandas as pd
            df = pd.DataFrame(existing_results)
            df.to_csv(backup_file, index=False, encoding='utf-8-sig')
            
            # 로그 출력 (빈도 제어)
            if len(existing_results) % 10 == 0:  # 10개마다 한 번씩만 로그
                self.emit_progress(f"💾 실시간 백업 저장: {len(existing_results)}개 결과 ({backup_file})")
            
        except Exception as e:
            self.emit_progress(f"⚠️ 실시간 저장 실패: {str(e)}")
            # 저장 실패해도 작업은 계속 진행
    
    def process_single_id_task(self, thread_id, account_id, script_index, script_folder, assigned_url):
        """🆕 ID 기준 단일 작업 처리 (답글 작성 + 모든 댓글 작성)"""
        self.emit_progress(f"📝 {account_id}-원고{script_index+1} 시작", thread_id)
        
        # 🔥 현재 카페명 가져오기
        cafe_name = getattr(self, 'current_cafe_name', '')
        if not cafe_name and hasattr(self, 'main_window'):
            cafe_name = getattr(self.main_window, 'current_cafe_name', '')
        
        # 🆕 account_id에서 실제 계정명 추출 (sat1926_row1 → sat1926)
        real_account_id = account_id.split('_row')[0] if '_row' in account_id else account_id
        target_account = None
        
        if hasattr(self.main_window, 'account_rows'):
            self.emit_progress(f"🔍 디버그: {account_id} → 실제계정: {real_account_id}, URL: {assigned_url[:30]}...", thread_id)
            for i, row_data in enumerate(self.main_window.account_rows):
                # URL 비교 시 카페 URL 기본 부분만 비교
                row_url_base = row_data['url'].split('/')[3] if len(row_data['url'].split('/')) > 3 else row_data['url']
                assigned_url_base = assigned_url.split('/')[3] if len(assigned_url.split('/')) > 3 else assigned_url
                
                # 계정 ID가 일치하고 같은 카페인 경우
                if row_data['account_id'] == real_account_id and row_url_base == assigned_url_base:
                    target_account = (row_data['account_id'], row_data['password'])
                    self.emit_progress(f"✅ 작업 전용 계정 찾음: {real_account_id} (행{i+1})", thread_id)
                    break
        
        if not target_account:
            self.emit_progress(f"❌ {real_account_id} 계정 정보를 찾을 수 없음", thread_id)
            # 🔍 디버그: 현재 카페의 계정 목록 확인
            current_cafe = getattr(self, 'current_cafe_name', 'Unknown')
            if hasattr(self.main_window, 'cafe_data') and current_cafe in self.main_window.cafe_data:
                cafe_accounts = self.main_window.cafe_data[current_cafe]['reply_accounts']
                account_ids = [acc[0] for acc in cafe_accounts]
                self.emit_progress(f"🔍 {current_cafe} 카페 보유 계정: {', '.join(account_ids[:10])}", thread_id)
                self.emit_progress(f"🔍 찾으려는 계정: {real_account_id}", thread_id)
            self.emit_progress(f"⚠️ 풀에서 다른 계정 사용하면 본인 글이 아닌 글 수정 시도로 실패 가능", thread_id)
        else:
            self.emit_progress(f"✅ target_account 설정됨: {target_account[0]} (비밀번호: {target_account[1][:3]}***)", thread_id)
        
        # ID별 댓글 차단 설정 확인
        id_script_mapping = self.config.get('id_script_mapping', {})
        should_block_comments = False
        if account_id in id_script_mapping:
            mapping_data = id_script_mapping.get(account_id, {})
            should_block_comments = mapping_data.get('block_comments', False)
        
        # 원고 폴더가 없는 경우 (원고 부족)
        if not script_folder:
            self.emit_progress(f"⚠️ {account_id}-원고{script_index+1} 원고 없음으로 완료", thread_id)
            # 🔥 고유 키 생성
            unique_key = generate_unique_key(assigned_url, script_folder or "no_script", thread_id)
            
            # 결과 저장 (원고 없음)
            result = {
                '폴더명': '원고 없음',
                '답글아이디': account_id,
                '답글아이디로그인아이피': '원고 없음',
                '답글등록상태': '-',
                '답글URL': '원고 없음',
                '원본URL': assigned_url,
                '댓글상황': '원고 없음',
                '댓글차단': '➖ 해당없음',
                'cafe_name': cafe_name,  # 🔥 카페명 추가
                'script_folder': script_folder,  # 🔥 스크립트 폴더 경로 추가
                'account_id': account_id,  # 🔥 계정 ID 추가
                'unique_key': unique_key  # 🔥 고유 식별자 추가
            }
            self.signals.result_saved.emit(result)
            # 🔥 실시간 저장: 즉시 엑셀/CSV 백업 저장
            self.save_result_immediately(result)
            return
        
        # 원고 파싱
        script_file = os.path.join(script_folder, os.path.basename(script_folder) + '.txt')
        if not os.path.exists(script_file):
            # .txt 파일 찾기
            txt_files = [f for f in os.listdir(script_folder) if f.endswith('.txt')]
            if not txt_files:
                raise Exception(f"원고 파일을 찾을 수 없습니다: {script_folder}")
            script_file = os.path.join(script_folder, txt_files[0])
        
        parser = ScriptParser()
        try:
            parser.parse_file(script_file)
            parser.folder_name = extract_keyword_from_folder_name(os.path.basename(script_folder))
        except ValueError as e:
            # 원고 파싱 오류 처리
            self.emit_progress(str(e), thread_id)
            
            # 🔥 고유 키 생성
            unique_key = generate_unique_key(assigned_url, script_folder, thread_id)
            
            # 결과 테이블에 오류 표시
            result = {
                '답글아이디': account_id,
                '답글아이디로그인아이피': '-',
                '답글등록상태': '원고 첫줄 비어있음',
                '폴더명': extract_keyword_from_folder_name(os.path.basename(script_folder)),
                '답글URL': '-',
                '원본URL': assigned_url,
                '댓글상황': '작업 안함',
                '댓글차단': '✅ 차단됨' if should_block_comments else '❌ 차단안됨',
                'cafe_name': cafe_name,  # 🔥 카페명 추가
                'script_folder': script_folder,  # 🔥 스크립트 폴더 경로 추가
                'account_id': account_id,  # 🔥 계정 ID 추가
                'unique_key': unique_key  # 🔥 고유 식별자 추가
            }
            self.signals.result_saved.emit(result)
            # 🔥 실시간 저장: 즉시 엑셀/CSV 백업 저장
            self.save_result_immediately(result)
            return
        
        # 실제 작업 수행은 기존 로직과 동일하므로 기존 함수 호출
        # assigned_url을 urls에서 찾아서 url_index로 변환
        url_index = 0
        if assigned_url in self.config['urls']:
            url_index = self.config['urls'].index(assigned_url)
        
        # 🆕 직접 write_reply 호출 (target_account 전달)
        try:
            # 🚨 target_account가 None이면 작업 중단 (다른 카페 계정 사용 방지)
            if not target_account:
                self.emit_progress(f"🛑 [스레드{thread_id+1}] {account_id} 전용 계정을 찾을 수 없어 작업 중단", thread_id)
                self.emit_progress(f"🔍 해당 계정이 현재 카페 Excel 파일에 있는지 확인하세요", thread_id)
                return  # 작업 중단
            
            reply_account, reply_url, reply_ip, current_row, next_reply_url = self.write_reply(
                thread_id, assigned_url, parser, script_folder,
                assigned_url=assigned_url, target_account=target_account
            )
            if not reply_url:
                raise Exception("답글 작성 실패")
            
            # 댓글 작성
            success_count, total_count = self.write_comments(thread_id, reply_url, parser, reply_account)
            
            # 댓글 결과 업데이트
            if total_count == 0:
                comment_status = "댓글 없음 ⭕"
            elif success_count == total_count:
                comment_status = f"{success_count}개 완료 ✅"
            elif success_count > 0:
                comment_status = f"{success_count}개 완료 ({total_count-success_count}개 실패) ⚠️"
            else:
                comment_status = f"전체 실패 ({total_count}개) ❌"
            
            comment_update = {'댓글상황': comment_status}
            self.main_window.update_result(current_row, comment_update)
            
            # 🆕 수정 모드인 경우 댓글 차단 처리
            if assigned_url:
                self.emit_progress(f"🚫 [스레드{thread_id+1}] 수정 모드 - 댓글 차단 처리 시작", thread_id)
                block_success = self.block_comments_after_completion(thread_id, reply_account, assigned_url)
                
                if block_success:
                    final_comment_block = '✅ 차단완료'
                else:
                    final_comment_block = '❌ 차단실패'
                
                final_update = {'댓글차단': final_comment_block}
                self.main_window.update_result(current_row, final_update)
            
            # 🔥 작업 완료 후 해당 스레드의 모든 드라이버 완전 정리 (크롬창 누적 방지)
            self.emit_progress(f"🧹 [스레드{thread_id+1}] 작업 완료 - 전체 드라이버 정리 시작", thread_id)
            self.safe_cleanup_thread_drivers(thread_id)
            
        except Exception as e:
            self.emit_progress(f"❌ 작업 실패: {account_id}-원고{script_index+1} - {str(e)}", thread_id)
            # 실패 결과 저장
            result = {
                '답글아이디': account_id,
                '답글아이디로그인아이피': '실패',
                '답글등록상태': 'X',
                '폴더명': extract_keyword_from_folder_name(os.path.basename(script_folder)),
                '답글URL': '실패',
                '원본URL': assigned_url,
                '댓글상황': '작업 실패',
                '댓글차단': '❌ 실패',
                'cafe_name': cafe_name,
                'script_folder': script_folder,
                'account_id': account_id,
                'unique_key': generate_unique_key(assigned_url, script_folder, thread_id)
            }
            self.signals.result_saved.emit(result)
            # 🔥 실시간 저장: 실패 결과도 즉시 백업 저장
            self.save_result_immediately(result)
            
            # 🔥 실패 시에도 해당 스레드의 모든 드라이버 완전 정리 (크롬창 누적 방지)
            self.emit_progress(f"🧹 [스레드{thread_id+1}] 작업 실패 - 전체 드라이버 정리", thread_id)
            self.safe_cleanup_thread_drivers(thread_id)

    def process_single_task(self, thread_id, url_index, reply_index, url, script_folder):
        """단일 작업 처리 (답글 작성 + 모든 댓글 작성)"""
        self.emit_progress(f"📝 URL{url_index+1}-답글{reply_index+1} 시작", thread_id)
        
        # 🆕 assigned_url 변수 정의 (호환성)
        assigned_url = url
        target_account = None  # 🆕 기본값 설정 (ID 기반 작업에서만 사용)
        
        # 🔥 현재 카페명 가져오기
        cafe_name = getattr(self, 'current_cafe_name', '')
        if not cafe_name and hasattr(self, 'main_window'):
            cafe_name = getattr(self.main_window, 'current_cafe_name', '')
        
        # URL별 댓글 차단 설정 확인
        should_block_comments = self.config.get('url_comment_block_settings', {}).get(url, True)
        
        # 원고 폴더가 없는 경우 (원고 부족)
        if not script_folder:
            self.emit_progress(f"⚠️ URL{url_index+1}-답글{reply_index+1} 원고 없음으로 완료", thread_id)
            
            # 🔥 고유 키 생성
            unique_key = generate_unique_key(url, script_folder or "no_script", thread_id)
            
            # 결과 저장 (원고 없음)
            result = {
                '폴더명': '원고 없음',
                '답글아이디': '원고 없음',
                '답글아이디로그인아이피': '원고 없음',
                '답글등록상태': '-',
                '답글URL': '원고 없음',
                '원본URL': url,
                '댓글상황': '원고 없음',
                '댓글차단': '➖ 해당없음',
                'cafe_name': cafe_name,  # 🔥 카페명 추가
                'script_folder': '',  # 🔥 스크립트 폴더 경로 추가 (원고 없음)
                'account_id': '원고 없음',  # 🔥 계정 ID 추가
                'unique_key': unique_key  # 🔥 고유 식별자 추가
            }
            self.signals.result_saved.emit(result)
            # 🔥 실시간 저장: 즉시 엑셀/CSV 백업 저장
            self.save_result_immediately(result)
            return
        
        # 원고 파싱
        script_file = os.path.join(script_folder, os.path.basename(script_folder) + '.txt')
        if not os.path.exists(script_file):
            # .txt 파일 찾기
            txt_files = [f for f in os.listdir(script_folder) if f.endswith('.txt')]
            if not txt_files:
                raise Exception(f"원고 파일을 찾을 수 없습니다: {script_folder}")
            script_file = os.path.join(script_folder, txt_files[0])
        
        parser = ScriptParser()
        try:
            parser.parse_file(script_file)
            parser.folder_name = extract_keyword_from_folder_name(os.path.basename(script_folder))  # 📌 폴더명에서 키워드만 추출
        except ValueError as e:
            # 원고 파싱 오류 처리
            self.emit_progress(str(e), thread_id)
            
            # 결과 테이블에 오류 표시
            base_folder_name = extract_keyword_from_folder_name(os.path.basename(script_folder))
            
            # 폴더명 카운터 업데이트 (preview와 동일한 방식)
            with self.folder_count_lock:
                count = self.folder_count.get(base_folder_name, 0) + 1
                self.folder_count[base_folder_name] = count
                
                # 2번째부터 번호 추가
                if count > 1:
                    folder_name = f"{base_folder_name}({count})"
                else:
                    folder_name = base_folder_name
            
            # 🔥 고유 키 생성
            unique_key = generate_unique_key(url, script_folder, thread_id)
            
            result = {
                '답글아이디': '원고오류',
                '답글아이디로그인아이피': '-',
                '답글등록상태': '원고 첫줄 비어있음',
                '폴더명': folder_name,
                '답글URL': '-',
                '원본URL': url,
                '댓글상황': '작업 안함',
                'cafe_name': cafe_name,  # 🔥 카페명 추가
                'script_folder': script_folder,  # 🔥 스크립트 폴더 경로 추가
                'account_id': '원고오류',  # 🔥 계정 ID 추가
                'unique_key': unique_key  # 🔥 고유 식별자 추가
            }
            self.signals.result_saved.emit(result)
            # 🔥 실시간 저장: 즉시 엑셀/CSV 백업 저장
            self.save_result_immediately(result)
            
            # 이 작업은 건너뛰고 다음으로
            return
        
        # 1단계: 답글 작성 및 답글 계정 저장
        reply_account, reply_url, reply_ip, current_row, next_reply_url = self.write_reply(thread_id, url, parser, script_folder, assigned_url=assigned_url, target_account=target_account)
        if not reply_url:
            raise Exception("답글 작성 실패")
        
        # 🔗 연쇄 시스템: 다음 작업을 위해 새로운 URL 저장
        if next_reply_url and next_reply_url != url:
            self.emit_progress(f"🔗 [연쇄시스템] 다음 작업용 URL 업데이트: {next_reply_url[:50]}...", thread_id)
            # URL 매니저나 글로벌 변수에 저장하여 다음 작업에서 사용 가능하게 함
            if not hasattr(self, 'next_urls'):
                self.next_urls = {}
            self.next_urls[thread_id] = next_reply_url
        
        self.progress.save_reply_url(url_index, reply_index, reply_url)
        self.emit_progress(f"✅ 답글 작성 완료: {reply_url}", thread_id)
        self.emit_progress(f"📌 답글 작성 계정: {reply_account[0]} (작성자 댓글용으로 저장)", thread_id)
        self.emit_progress(f"🌐 답글 작성 IP: {reply_ip}", thread_id)
        
        # 1.5단계: 브라우저 완전 재시작 (답글→댓글 작업 분리)
        self.restart_browser_for_comments(thread_id)
        
        # 2단계: 댓글들 작성 (답글 계정 정보 전달)
        success_count, total_count = self.write_comments(thread_id, reply_url, parser, reply_account)
        
        # 📌 댓글 작성 완료 후 결과 테이블 업데이트
        if total_count == 0:
            comment_status = "댓글 없음 ⭕"
        elif success_count == total_count:
            comment_status = f"{success_count}개 완료 ✅"
        elif success_count > 0:
            comment_status = f"{success_count}개 완료 ({total_count-success_count}개 실패) ⚠️"
        else:
            comment_status = f"전체 실패 ({total_count}개) ❌"
        
        comment_update = {'댓글상황': comment_status}
        self.main_window.update_result(current_row, comment_update)
        self.emit_progress(f"📊 댓글 결과 업데이트: {comment_status}", thread_id)
        
        # 🆕 4단계: 답글 계정으로 댓글 허용 설정 해제 (차단 설정된 URL만)
        comment_block_update = {}
        if should_block_comments:
            # 댓글 차단 재시도 로직 (최대 3번 시도)
            max_retries = 3
            comment_success = False
            
            for attempt in range(max_retries):
                try:
                    if attempt == 0:
                        self.emit_progress("🔧 4단계: 댓글 허용 설정 해제 중...", thread_id)
                    else:
                        self.emit_progress(f"🔧 4단계: 댓글 허용 설정 해제 재시도 {attempt+1}/{max_retries}...", thread_id)
                    
                    self.disable_comment_permission_final(thread_id, reply_url, reply_account)
                    self.emit_progress("✅ 댓글 허용 설정 해제 완료!", thread_id)
                    comment_block_update['댓글차단'] = '✅ 차단됨'
                    comment_success = True
                    break  # 성공하면 루프 종료
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.emit_progress(f"⚠️ 댓글 설정 해제 실패 (시도 {attempt+1}/{max_retries}): {str(e)} - 재시도", thread_id)
                        # 브라우저 정리 후 재시도
                        try:
                            self.safe_cleanup_thread_drivers(thread_id)
                        except:
                            pass
                        self.smart_sleep(2, "재시도 전 대기")
                    else:
                        self.emit_progress(f"⚠️ 댓글 설정 해제 최종 실패 ({max_retries}번 시도): {str(e)}", thread_id)
            
            if not comment_success:
                comment_block_update['댓글차단'] = '❌ 실패'
                # 댓글 설정 실패는 치명적이지 않으므로 계속 진행
        else:
            self.emit_progress("ℹ️ 이 URL은 댓글 차단 설정이 없어 4단계를 건너뜁니다", thread_id)
            comment_block_update['댓글차단'] = '➖ 해당없음'
        
        # 댓글 차단 결과 업데이트
        self.main_window.update_result(current_row, comment_block_update)
        self.emit_progress(f"📊 댓글 차단 결과 업데이트: {comment_block_update['댓글차단']}", thread_id)
        
        # 🆕 5단계: 수정 모드인 경우 댓글 차단 처리
        if assigned_url and assigned_url != url:
            self.emit_progress(f"🚫 [스레드{thread_id+1}] 수정 모드 - 댓글 차단 처리 시작", thread_id)
            block_success = self.block_comments_after_completion(thread_id, reply_account, assigned_url)
            
            if block_success:
                final_comment_block = '✅ 차단완료'
                self.emit_progress(f"✅ [스레드{thread_id+1}] 댓글 차단 처리 완료", thread_id)
            else:
                final_comment_block = '❌ 차단실패'
                self.emit_progress(f"❌ [스레드{thread_id+1}] 댓글 차단 처리 실패", thread_id)
            
            # 최종 댓글 차단 상태 업데이트
            final_update = {'댓글차단': final_comment_block}
            self.main_window.update_result(current_row, final_update)
        
        # 6단계: 해당 URL 작업 완료 후 스레드 정리
        self.emit_progress(f"🧹 [스레드{thread_id+1}] URL{url_index+1}-답글{reply_index+1} 완료 - 스레드 정리 시작", thread_id)
        self.safe_cleanup_thread_drivers(thread_id)
        self.emit_progress(f"💀 [스레드{thread_id+1}] URL{url_index+1}-답글{reply_index+1} 전체 완료 - 모든 크롬 종료", thread_id)
        
        # 결과는 이미 write_reply와 write_comments에서 update_result로 처리했으므로
        # 여기서 다시 emit할 필요 없음 (중복 방지)
    
    def find_edit_button_with_scroll(self, driver, thread_id):
        """📌 스마트 수정 버튼 찾기 (조건부 스크롤 포함)"""
        # 수정 버튼 셀렉터들 - 실제 HTML 구조에 맞게 수정
        edit_btn_selectors = [
            "//a[contains(@class, 'BaseButton') and contains(@class, 'skinGray')]//span[@class='BaseButton__txt' and normalize-space()='수정']/..",
            "//a[contains(@class, 'BaseButton')]//span[normalize-space(text())='수정']/..",
            "//div[contains(@class, 'ArticleBottomBtns')]//a[contains(@href, '/edit')]",
            "//a[@role='button']//span[normalize-space()='수정']/..",
            "//button[@role='button']//span[normalize-space()='수정']/.."
        ]
        
        # 1단계: 현재 화면에서 수정 버튼 찾기 시도
        self.emit_progress("🔍 수정 버튼 찾는 중...", thread_id)
        edit_btn = self._find_edit_button(driver, edit_btn_selectors)
        
        if edit_btn:
            self.emit_progress("✅ 수정 버튼 발견! (현재 화면)", thread_id)
            return edit_btn
        
        # 2단계: 페이지 끝까지 스크롤 후 다시 시도
        self.emit_progress("📜 수정 버튼이 안 보임 - 페이지 끝까지 스크롤 중...", thread_id)
        try:
            # 페이지 끝까지 스크롤
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.smart_sleep(2, "스크롤 후 동적 콘텐츠 로딩 대기")
            
            # 다시 수정 버튼 찾기
            edit_btn = self._find_edit_button(driver, edit_btn_selectors)
            
            if edit_btn:
                self.emit_progress("✅ 수정 버튼 발견! (스크롤 후)", thread_id)
                return edit_btn
            else:
                self.emit_progress("❌ 스크롤 후에도 수정 버튼을 찾을 수 없음", thread_id)
                return None
                
        except Exception as e:
            self.emit_progress(f"⚠️ 스크롤 중 오류: {str(e)}", thread_id)
            return None
    
    def _find_edit_button(self, driver, selectors):
        """수정 버튼 찾기 (내부 메서드)"""
        for selector in selectors:
            try:
                edit_btn = self.wait_for_element_with_retry(
                    driver, By.XPATH, selector, max_wait=3,
                    element_name="수정 버튼"
                )
                if edit_btn:
                    return edit_btn
            except:
                continue
        return None

    def block_comments_after_completion(self, thread_id, account_info, edit_url):
        """🚫 댓글 작성 완료 후 댓글 차단 처리 (개선된 안정성)"""
        driver = None
        original_window = None
        new_window = None
        
        try:
            self.emit_progress(f"🚫 [스레드{thread_id+1}] 댓글 차단 처리 시작 - 작성자 계정 재로그인", thread_id)
            
            # 🔒 스레드별 드라이버 생성 Lock 추가
            driver_key = f"{thread_id}_edit_block_{account_info[0]}"
            
            # 다른 드라이버와 충돌 방지를 위한 대기
            time.sleep(2)
            
            # 작성자 계정으로 새 드라이버 생성 (고유 키 사용)
            driver = self.create_chrome_driver('reply', account_info[0], thread_id)
            if driver is None:
                self.emit_progress(f"🛑 [스레드{thread_id+1}] 댓글 차단용 드라이버 생성 실패", thread_id)
                return False
            
            # 드라이버 딕셔너리에 임시 등록 (정리용)
            with self.drivers_lock:
                self.drivers[driver_key] = driver
            
            # 작성자 계정으로 로그인
            login_result = self.login_naver(driver, account_info[0], account_info[1], thread_id)
            if not login_result[0]:
                self.emit_progress(f"❌ [스레드{thread_id+1}] 댓글 차단용 로그인 실패: {login_result[1]}", thread_id)
                return False
            
            # 수정할 게시글로 이동
            self.emit_progress(f"📝 [스레드{thread_id+1}] 댓글 차단용 게시글 접속: {edit_url}", thread_id)
            driver.get(edit_url)
            
            # 페이지 로딩 대기
            if not self.wait_for_page_load(driver):
                self.emit_progress("⚠️ 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
            
            self.smart_sleep(5, "페이지 로딩 후 대기")
            
            # iframe 진입
            iframe_entered = False
            try:
                iframe = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, "iframe#cafe_main", 
                    max_wait=5, element_name="iframe#cafe_main"
                )
                driver.switch_to.frame(iframe)
                iframe_entered = True
                self.emit_progress("🔄 iframe(cafe_main) 내부로 진입했습니다.", thread_id)
            except Exception as e:
                self.emit_progress("ℹ️ iframe(cafe_main) 없음 또는 진입 불필요.", thread_id)
            
            # 🔍 페이지 상태 디버깅
            try:
                page_title = driver.title
                current_url = driver.current_url
                self.emit_progress(f"🔍 댓글차단 페이지 상태 - 제목: {page_title[:30]}...", thread_id)
                self.emit_progress(f"🔍 댓글차단 현재 URL: {current_url[:50]}...", thread_id)
                
                # 페이지 소스에서 수정 버튼 텍스트 확인
                page_source = driver.page_source
                if "수정" in page_source:
                    self.emit_progress("✅ 페이지에 '수정' 텍스트 존재함", thread_id)
                else:
                    self.emit_progress("❌ 페이지에 '수정' 텍스트 없음", thread_id)
                    
            except Exception as e:
                self.emit_progress(f"⚠️ 페이지 상태 확인 실패: {e}", thread_id)
            
            # 수정 버튼 찾기
            edit_btn = self.find_edit_button_with_scroll(driver, thread_id)
            if not edit_btn:
                self.emit_progress("❌ 수정 버튼을 찾을 수 없음 - 상세 디버깅 시작", thread_id)
                
                # 모든 버튼 요소 확인
                try:
                    all_buttons = driver.find_elements(By.TAG_NAME, "button")
                    all_links = driver.find_elements(By.TAG_NAME, "a")
                    self.emit_progress(f"🔍 페이지의 모든 버튼: {len(all_buttons)}개, 링크: {len(all_links)}개", thread_id)
                    
                    for i, btn in enumerate(all_buttons[:5]):  # 처음 5개만
                        try:
                            btn_text = btn.text.strip()
                            if btn_text:
                                self.emit_progress(f"🔍 버튼{i+1}: '{btn_text}'", thread_id)
                        except:
                            pass
                            
                except Exception as e:
                    self.emit_progress(f"⚠️ 버튼 디버깅 실패: {e}", thread_id)
                
                raise Exception("수정 버튼을 찾을 수 없습니다")
            
            # 현재 탭 저장
            original_window = driver.current_window_handle
            original_tabs = driver.window_handles
            
            # 수정 버튼 클릭
            if not self.safe_click_with_retry(driver, edit_btn, element_name="수정 버튼"):
                raise Exception("수정 버튼 클릭 실패")
            
            # 새 탭 대기 및 전환 (개선된 처리)
            try:
                from selenium.webdriver.support.ui import WebDriverWait as WDW
                
                # 새 탭이 열릴 때까지 대기 (최대 20초)
                WDW(driver, 20).until(
                    lambda d: len(d.window_handles) > len(original_tabs)
                )
                
                # 새로 열린 탭 찾기
                new_tabs = [tab for tab in driver.window_handles if tab not in original_tabs]
                if new_tabs:
                    new_window = new_tabs[0]
                    driver.switch_to.window(new_window)
                    self.emit_progress("🆕 댓글 차단용 수정 탭으로 전환 완료", thread_id)
                    
                    # 새 탭 로딩 완료 대기
                    self.smart_sleep(8, "수정 페이지 로딩 대기")
                    
                    # 페이지 완전 로딩 확인
                    try:
                        WDW(driver, 15).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                        self.emit_progress("✅ 수정 페이지 로딩 완료", thread_id)
                    except:
                        self.emit_progress("⚠️ 수정 페이지 로딩 시간 초과, 계속 진행", thread_id)
                        
                else:
                    raise Exception("새 탭을 찾을 수 없습니다")
                    
            except Exception as e:
                self.emit_progress(f"❌ 새 탭 처리 실패: {e}", thread_id)
                raise Exception(f"새 탭 처리 실패: {e}")
            
            # 댓글 허용 체크박스 찾기 및 해제 (재시도 로직 추가)
            checkbox_success = False
            max_checkbox_retries = 3
            
            for checkbox_attempt in range(max_checkbox_retries):
                try:
                    if checkbox_attempt > 0:
                        self.emit_progress(f"🔄 댓글 허용 체크박스 재시도 {checkbox_attempt+1}/{max_checkbox_retries}", thread_id)
                        self.smart_sleep(2, "체크박스 재시도 전 대기")
                    
                    self.emit_progress("🔍 댓글 허용 체크박스 찾는 중...", thread_id)
                    comment_checkbox = self.wait_for_element_with_retry(
                        driver, By.ID, "coment",
                        max_wait=8, element_name="댓글 허용 체크박스"
                    )
                    
                    # JavaScript 클릭 사용 (더 안정적)
                    if comment_checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", comment_checkbox)
                        self.emit_progress("✅ 댓글 비허용 설정 완료", thread_id)
                        self.smart_sleep(2, "체크박스 클릭 후 대기")
                    else:
                        self.emit_progress("ℹ️ 댓글이 이미 비허용 상태입니다", thread_id)
                    
                    checkbox_success = True
                    break
                    
                except Exception as e:
                    if checkbox_attempt < max_checkbox_retries - 1:
                        self.emit_progress(f"⚠️ 댓글 체크박스 처리 실패 (시도 {checkbox_attempt+1}): {str(e)}", thread_id)
                    else:
                        self.emit_progress(f"❌ 댓글 체크박스 처리 최종 실패: {str(e)}", thread_id)
                        raise Exception(f"댓글 체크박스 처리 실패: {str(e)}")
            
            if not checkbox_success:
                raise Exception("댓글 허용 체크박스 처리 실패")
            
            # 저장 버튼 클릭 (재시도 로직 추가)
            save_success = False
            max_save_retries = 3
            
            for save_attempt in range(max_save_retries):
                try:
                    if save_attempt > 0:
                        self.emit_progress(f"🔄 저장 버튼 재시도 {save_attempt+1}/{max_save_retries}", thread_id)
                        self.smart_sleep(2, "저장 재시도 전 대기")
                    
                    self.emit_progress("💾 설정 저장 중...", thread_id)
                    save_btn = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'a.BaseButton--skinGreen[role="button"]',
                        max_wait=10, element_name="저장 버튼"
                    )
                    
                    if not self.safe_click_with_retry(driver, save_btn, element_name="저장 버튼"):
                        raise Exception("저장 버튼 클릭 실패")
                    
                    self.emit_progress("✅ 댓글 차단 설정 저장 완료", thread_id)
                    self.smart_sleep(5, "댓글 차단 설정 저장 대기")
                    
                    save_success = True
                    break
                    
                except Exception as e:
                    if save_attempt < max_save_retries - 1:
                        self.emit_progress(f"⚠️ 저장 버튼 처리 실패 (시도 {save_attempt+1}): {str(e)}", thread_id)
                    else:
                        self.emit_progress(f"❌ 저장 버튼 처리 최종 실패: {str(e)}", thread_id)
                        raise Exception(f"저장 버튼 처리 실패: {str(e)}")
            
            if not save_success:
                raise Exception("저장 처리 실패")
                
            return True
            
        except Exception as e:
            self.emit_progress(f"❌ [스레드{thread_id+1}] 댓글 차단 처리 실패: {str(e)}", thread_id)
            return False
            
        finally:
            # 🔒 안전한 드라이버 정리 (스레드별 Lock 사용)
            try:
                if driver:
                    # 새 창이 열렸다면 원래 창으로 돌아가기 시도
                    if new_window and original_window:
                        try:
                            driver.switch_to.window(original_window)
                            self.emit_progress("🔄 원래 창으로 복귀", thread_id)
                        except:
                            pass
                    
                    # iframe에서 나가기
                    try:
                        driver.switch_to.default_content()
                    except:
                        pass
                    
                    # 로그아웃 시도
                    try:
                        self.logout_naver(driver)
                    except:
                        pass
                    
                    # 드라이버 종료
                    try:
                        driver.quit()
                        self.emit_progress(f"🧹 [스레드{thread_id+1}] 댓글 차단용 드라이버 정리 완료", thread_id)
                    except Exception as quit_error:
                        self.emit_progress(f"⚠️ [스레드{thread_id+1}] 드라이버 종료 중 오류: {quit_error}", thread_id)
                    
                    # 드라이버 딕셔너리에서 제거
                    with self.drivers_lock:
                        if driver_key in self.drivers:
                            del self.drivers[driver_key]
                
                # 메모리 정리
                import gc
                gc.collect()
                
            except Exception as cleanup_error:
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] 댓글 차단 정리 중 오류: {cleanup_error}", thread_id)

    def find_reply_button_with_scroll(self, driver, thread_id):
        """📌 스마트 답글 버튼 찾기 (조건부 스크롤 포함)"""
        # 답글 버튼 셀렉터들 - 실제 HTML 구조에 맞게 수정
        reply_btn_selectors = [
            "//a[contains(@class, 'BaseButton') and contains(@class, 'skinGray')]//span[@class='BaseButton__txt' and normalize-space()='답글']/..",
            "//a[contains(@class, 'BaseButton')]//span[normalize-space(text())='답글']/..",
            "//div[contains(@class, 'ArticleBottomBtns')]//a[contains(@href, '/reply')]"
        ]
        
        # 1단계: 현재 화면에서 답글 버튼 찾기 시도
        self.emit_progress("🔍 답글 버튼 찾는 중...", thread_id)
        reply_btn = self._find_reply_button(driver, reply_btn_selectors)
        
        if reply_btn:
            self.emit_progress("✅ 답글 버튼 발견! (현재 화면)", thread_id)
            return reply_btn
        
        # 2단계: 페이지 끝까지 스크롤 후 다시 시도
        self.emit_progress("📜 답글 버튼이 안 보임 - 페이지 끝까지 스크롤 중...", thread_id)
        try:
            # 페이지 끝까지 스크롤
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.smart_sleep(2, "스크롤 후 동적 콘텐츠 로딩 대기")
            
            # 다시 답글 버튼 찾기
            reply_btn = self._find_reply_button(driver, reply_btn_selectors)
            
            if reply_btn:
                self.emit_progress("✅ 답글 버튼 발견! (스크롤 후)", thread_id)
                return reply_btn
            else:
                self.emit_progress("❌ 스크롤 후에도 답글 버튼을 찾을 수 없음", thread_id)
                return None
                
        except Exception as e:
            self.emit_progress(f"⚠️ 스크롤 중 오류: {str(e)}", thread_id)
            return None
    
    def _find_reply_button(self, driver, selectors):
        """답글 버튼 찾기 (내부 메서드)"""
        for selector in selectors:
            try:
                reply_btn = self.wait_for_element_with_retry(
                    driver, By.XPATH, selector, max_wait=3,
                    element_name="답글 버튼"
                )
                if reply_btn:
                    return reply_btn
            except:
                continue
        return None
    
    def restart_browser_for_comments(self, thread_id):
        """답글 작성 후 댓글 작성을 위한 답글용 드라이버만 정리"""
        self.emit_progress(f"🔄 [쓰레드{thread_id}] 답글 작성 완료 - 답글용 브라우저만 정리 중...", thread_id)
        
        try:
            # 답글용 드라이버만 정리 (댓글용은 유지)
            with self.drivers_lock:
                drivers_to_remove = []
                for key in self.drivers.keys():
                    if key.startswith(f"{thread_id}_reply"):
                        drivers_to_remove.append(key)
                
                for key in drivers_to_remove:
                    try:
                        driver = self.drivers[key]
                        driver.quit()
                        # 🔧 드라이버 정리 로그 제거 (너무 빈번함)
                    except Exception as e:
                        self.emit_progress(f"⚠️ [쓰레드{thread_id}] 드라이버 {key} 정리 오류: {e}", thread_id)
                    
                    del self.drivers[key]
            
            # 짧은 대기 시간
            self.emit_progress(f"⏳ [쓰레드{thread_id}] 답글용 브라우저 정리 완료 - 댓글 작성 준비", thread_id)
            time.sleep(1)  # 짧은 대기
            
            # 가비지 컬렉션으로 메모리 정리
            gc.collect()
            
        except Exception as e:
            self.emit_progress(f"❌ [쓰레드{thread_id}] 답글용 브라우저 정리 중 오류: {e}", thread_id)
            # 오류가 발생해도 계속 진행
    
    def write_reply(self, thread_id, url, parser, script_folder=None, assigned_url=None, target_account=None):
        """답글 작성 및 답글 계정 반환"""
        # 🔍 디버그: target_account 확인
        if target_account:
            self.emit_progress(f"🔍 write_reply 받은 target_account: {target_account[0]}", thread_id)
        else:
            self.emit_progress(f"🔍 write_reply target_account가 None임", thread_id)
        
        # 🔄 여러 계정으로 로그인 시도 (실패한 계정은 차단하고 다음 계정으로 재시도)
        successful_account = None
        driver = None
        max_attempts = 5  # 최대 5개 계정까지 시도 (각 계정당 1번씩만)
        
        for attempt in range(max_attempts):
            # 🆕 전용 계정이 지정된 경우 해당 계정만 사용 (강제)
            if target_account:
                reply_account = target_account
                self.emit_progress(f"🔒 [스레드{thread_id+1}] 전용 계정 강제 사용: {reply_account[0]}", thread_id)
            else:
                # 스레드별 전용 풀에서 답글 계정 가져오기
                reply_account = self.main_window.get_reply_account_from_pool(thread_id)
                self.emit_progress(f"🎯 [스레드{thread_id+1}] 풀에서 계정 할당: {reply_account[0] if reply_account else 'None'} (시도 {attempt+1}/{max_attempts})", thread_id)
            
            if not reply_account:
                if target_account:
                    # 전용 계정이 실패한 경우 더 이상 시도하지 않음
                    self.emit_progress(f"❌ [스레드{thread_id+1}] 전용 계정 {target_account[0]} 사용 불가", thread_id)
                    break
                else:
                    # 🆘 일반 계정이 없으면 여분용 계정 시도
                    self.emit_progress(f"🆘 [스레드{thread_id+1}] 일반 답글 계정 없음 - 여분용 계정 시도 (시도 {attempt+1}/{max_attempts})", thread_id)
                    spare_account = self.get_spare_account_for_replacement(thread_id)
                    
                    if spare_account:
                        reply_account = spare_account
                        self.emit_progress(f"🎯 [스레드{thread_id+1}] 여분용 계정 할당: {reply_account[0]} (시도 {attempt+1}/{max_attempts})", thread_id)
                    else:
                        self.emit_progress(f"🚫 [스레드{thread_id+1}] 여분용 계정도 없습니다 (시도 {attempt+1}/{max_attempts})", thread_id)
                        break
            
            self.emit_progress(f"🎯 [스레드{thread_id+1}] 답글 계정 할당: {reply_account[0]} (시도 {attempt+1}/{max_attempts})", thread_id)
            
            try:
                # 🆕 백업 파일 방식: 안정적인 드라이버 생성
                try:
                    driver = self.create_chrome_driver('reply', reply_account[0], thread_id)
                    self.emit_progress(f"✅ [스레드{thread_id+1}] 드라이버 생성 성공", thread_id)
                except Exception as driver_error:
                    self.emit_progress(f"🛑 [스레드{thread_id+1}] 드라이버 생성 실패: {str(driver_error)}", thread_id)
                    continue
                
                self.emit_progress(f"🔑 [스레드{thread_id+1}] 답글 계정 로그인 시도: {reply_account[0]}", thread_id)
                
                # 로그인 시도
                login_result = self.login_naver(driver, reply_account[0], reply_account[1], thread_id)
                if login_result[0]:  # 로그인 성공
                    successful_account = reply_account
                    self.emit_progress(f"✅ [스레드{thread_id+1}] 답글 계정 로그인 성공: {successful_account[0]}", thread_id)
                    break  # 성공하면 루프 종료
                else:
                    failure_reason = login_result[1]  # 실패 원인
                    
                    # 🆕 전용 계정인 경우 차단하지 않고 바로 종료
                    if target_account:
                        self.emit_progress(f"❌ [스레드{thread_id+1}] 전용 계정 {reply_account[0]} 로그인 실패: {failure_reason}", thread_id)
                        self.emit_progress(f"🚫 [스레드{thread_id+1}] 전용 계정 실패 - 다른 계정 시도 안 함", thread_id)
                        self.safe_cleanup_thread_drivers(thread_id)
                        driver = None
                        break  # 전용 계정 실패 시 바로 종료
                    else:
                        # 🎯 일반 계정: 실패하면 바로 차단하고 다음 계정으로
                        self.main_window.mark_reply_account_blocked(reply_account[0])
                        self.emit_progress(f"❌ [스레드{thread_id+1}] 계정 {reply_account[0]} 로그인 실패: {failure_reason}", thread_id)
                        self.emit_progress(f"🚫 [스레드{thread_id+1}] 계정 {reply_account[0]} 차단 목록 추가", thread_id)
                        
                        # 실패한 드라이버 정리 후 다음 계정으로 재시도
                        self.safe_cleanup_thread_drivers(thread_id)
                        driver = None
                        continue  # 다음 계정으로 재시도
                    
            except Exception as e:
                self.emit_progress(f"❌ [스레드{thread_id+1}] 답글 계정 {reply_account[0]} 처리 중 오류: {str(e)}", thread_id)
                # 오류 발생 시에도 드라이버 정리 후 다음 계정으로
                self.safe_cleanup_thread_drivers(thread_id)
                driver = None
                continue
        
        if not successful_account:
            # 모든 계정 시도 실패
            self.emit_progress(f"🧹 [스레드{thread_id+1}] 모든 답글 계정 로그인 실패 - 크롬창 정리 중...", thread_id)
            self.safe_cleanup_thread_drivers(thread_id)
            raise Exception(f"[스레드{thread_id+1}] 모든 답글 계정 로그인 실패 또는 계정 부족")
        
        try:
            # 📌 답글 시작 시 부분 결과 추가 (직접 메서드 호출)
            base_folder_name = getattr(parser, 'folder_name', '알 수 없음')
            
            # 폴더명 카운터 업데이트 (preview와 동일한 방식)
            with self.folder_count_lock:
                count = self.folder_count.get(base_folder_name, 0) + 1
                self.folder_count[base_folder_name] = count
                
                # 2번째부터 번호 추가
                if count > 1:
                    folder_name = f"{base_folder_name}({count})"
                else:
                    folder_name = base_folder_name
            
            partial_result = {
                '답글아이디': successful_account[0],
                '폴더명': folder_name,
                '원본URL': url,
                'account_id': successful_account[0],  # account_id 추가
                'cafe_name': getattr(self, 'current_cafe_name', ''),  # cafe_name 추가
                'script_folder': script_folder,  # 🔥 함수 파라미터에서 직접 가져오기
                'thread_id': thread_id  # 🔥 thread_id도 추가
            }
            current_row = self.main_window.add_partial_result(partial_result)
            self.emit_progress(f"📊 결과 테이블에 {successful_account[0]} 답글 시작 표시됨 (행 {current_row+1})", thread_id)
            
            # 🆕 할당된 URL 사용 (매칭 데이터에서 전달받은 URL 우선)
            account_id = successful_account[0]
            if assigned_url:
                edit_url = assigned_url
                self.emit_progress(f"🎯 매칭된 전용 URL 사용: {edit_url}", thread_id)
            else:
                # 백업: 계정별 첫 번째 URL 사용
                account_urls_list = self.main_window.account_urls.get(account_id, [])
                edit_url = account_urls_list[0] if account_urls_list else url
                self.emit_progress(f"🔄 백업 URL 사용: {edit_url}", thread_id)
            
            if edit_url != url:
                self.emit_progress(f"📝 계정 {account_id}의 전용 수정 URL로 이동: {edit_url}", thread_id)
            else:
                self.emit_progress(f"📝 게시글 페이지로 이동: {url}", thread_id)
            
            driver.get(edit_url)
            
            # 페이지 로딩 완료 대기
            if not self.wait_for_page_load(driver):
                self.emit_progress("⚠️ 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
            
            self.smart_sleep(10, "페이지 로딩 후 대기")
            
            # iframe 진입
            try:
                iframe = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, "iframe#cafe_main", 
                    element_name="iframe#cafe_main"
                )
                driver.switch_to.frame(iframe)
                self.emit_progress("🔄 iframe(cafe_main) 내부로 진입했습니다.", thread_id)
            except Exception as e:
                self.emit_progress("ℹ️ iframe(cafe_main) 없음 또는 진입 불필요.", thread_id)
            
            # 🆕 수정 모드 감지: 계정별 전용 URL이 있는지 확인
            account_id = successful_account[0]
            has_account_url = (account_id in self.main_window.account_urls and 
                             len(self.main_window.account_urls[account_id]) > 0)
            
            if has_account_url:
                # 계정별 전용 URL이 있는 경우 수정 모드
                self.emit_progress(f"🔧 수정 모드: {account_id} 전용 URL 감지 → 수정 버튼 찾기", thread_id)
                action_btn = self.find_edit_button_with_scroll(driver, thread_id)
                action_name = "수정"
                
                if not action_btn:
                    raise Exception("수정 버튼을 찾을 수 없습니다")
            else:
                # 전용 URL이 없는 경우 답글 모드
                self.emit_progress(f"💬 답글 모드: 기존 방식 → 답글 버튼 찾기", thread_id)
                action_btn = self.find_reply_button_with_scroll(driver, thread_id)
                action_name = "답글"
                
                if not action_btn:
                    raise Exception("답글 버튼을 찾을 수 없습니다")
            
            # 버튼 클릭
            original_tabs = driver.window_handles
            if not self.safe_click_with_retry(driver, action_btn, element_name=f"{action_name} 버튼"):
                raise Exception(f"{action_name} 버튼 클릭 실패")
            
            # 새 탭 열릴 때까지 대기
            try:
                from selenium.webdriver.support.ui import WebDriverWait as WDW
                WDW(driver, 15).until(
                    lambda d: len(d.window_handles) > len(original_tabs)
                )
                new_tab = list(set(driver.window_handles) - set(original_tabs))[0]
                driver.switch_to.window(new_tab)
                self.emit_progress(f"🆕 {action_name} 작성 탭으로 전환 완료", thread_id)
                
                # 새 탭에서 페이지 로딩 완료까지 충분히 대기
                self.smart_sleep(10, "새 탭 초기 로딩 대기")
                
                # document.readyState 체크
                try:
                    WDW(driver, 20).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    self.emit_progress("✅ 새 탭 페이지 로딩 완료", thread_id)
                except:
                    self.emit_progress("⚠️ 새 탭 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
                
                # JavaScript 및 DOM 완전 로딩 대기
                self.smart_sleep(3, "새 탭 JavaScript 로딩 대기")
                
                # 페이지 상호작용 가능 상태 체크
                try:
                    driver.execute_script("return document.body !== null")
                    self.emit_progress("✅ 새 탭 상호작용 준비 완료", thread_id)
                except:
                    self.emit_progress("⚠️ 새 탭 상호작용 준비 실패", thread_id)
                    
            except Exception as e:
                self.emit_progress(f"ℹ️ 새 탭 감지 실패 또는 새 탭이 열리지 않음: {e}", thread_id)

            # 작성 페이지는 단일 페이지 구조이므로 iframe 전환 불필요
            self.emit_progress(f"ℹ️ {action_name} 작성 페이지 (단일 페이지 구조)", thread_id)

            # 📌 제목 입력 처리
            try:
                title_input = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, 'textarea[placeholder="제목을 입력해 주세요."]',
                    element_name="제목 입력 필드"
                )
                
                # 🆕 수정 모드인 경우 기존 내용 지우기
                if action_name == "수정":
                    self.emit_progress("🗑️ 기존 제목 내용 지우는 중...", thread_id)
                    title_input.clear()  # 기존 내용 지우기
                    self.smart_sleep(1, "제목 지우기 후 대기")
                
                if not self.safe_input_text(driver, title_input, parser.title, "제목"):
                    raise Exception("제목 입력 실패")
                
                self.signals.progress.emit("✅ 제목 입력 성공")
            except Exception as e:
                self.signals.progress.emit(f"❌ 제목 입력 실패: {e}")
            
            # 답글 작성 페이지는 단일 페이지 구조이므로 iframe 전환 불필요
            self.signals.progress.emit("ℹ️ 본문 입력 준비 (단일 페이지 구조)")

            # 📌 에디터 로딩 완료 대기 (10초씩 5번 시도)
            try:
                self.signals.progress.emit("⏳ 에디터 로딩 대기 중...")
                # contenteditable 요소가 나타날 때까지 대기
                self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, '[contenteditable="true"], div[role="textbox"], div[data-placeholder]',
                    max_wait=10, retry_count=5, element_name="에디터"
                )
                self.smart_sleep(3, "에디터 완전 로딩 대기")  # 추가 대기
                self.signals.progress.emit("✅ 에디터 로딩 완료")
            except Exception as e:
                self.signals.progress.emit(f"⚠️ 에디터 로딩 대기 실패: {e}, 계속 진행")

            # 📌 본문 입력 처리 (ActionChains 기반, 다양한 에디터 대응)
            self.signals.progress.emit(f"🧾 입력 예정 본문 (앞 20자): {parser.content[:20]}")
            
            # 🆕 수정 모드인 경우 기존 본문 내용 지우기
            if action_name == "수정":
                self.emit_progress("🗑️ 기존 본문 내용 지우는 중...", thread_id)
                success = self.clear_and_input_content(driver, parser.content, parser.image_paths)
            else:
                success = self.input_content_with_images(driver, parser.content, parser.image_paths)
            if not success:
                # iframe 전체 순회 시도
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    try:
                        driver.switch_to.frame(iframe)
                        if action_name == "수정":
                            success = self.clear_and_input_content(driver, parser.content, parser.image_paths)
                        else:
                            success = self.input_content_with_images(driver, parser.content, parser.image_paths)
                        driver.switch_to.default_content()
                        if success:
                            break
                    except Exception as e:
                        self.signals.progress.emit(f"iframe 진입 실패: {e}")
                        driver.switch_to.default_content()
                if not success:
                    raise Exception("본문 입력 실패")
            

            
            # 🔥 본문 입력 완료 후 15초 대기
            self.smart_sleep(15, "본문 입력 완료 후 등록 준비 대기")
            self.signals.progress.emit(f"⏳ 본문 입력 완료 - 15초 후 {action_name} 등록 진행...")

            # 🆕 공개 설정 확인 및 변경 (수정 모드일 때만)
            if action_name == "수정":
                self.check_and_set_public_visibility(driver, thread_id)

            # 📌 등록 버튼 클릭 및 제목 팝업 재시도 처리 (최대 3번)
            max_submit_retries = 3
            submit_success = False
            
            for submit_attempt in range(max_submit_retries):
                try:
                    self.signals.progress.emit(f"📝 등록 버튼 클릭 시도 {submit_attempt + 1}/{max_submit_retries}")
                    
                    submit_btn = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'a.BaseButton--skinGreen[role="button"]',
                        element_name="등록 버튼"
                    )
                    
                    if not self.safe_click_with_retry(driver, submit_btn, element_name="등록 버튼"):
                        raise Exception("등록 버튼 클릭 실패")
                    
                    self.signals.progress.emit("✅ 등록 버튼 클릭 완료 (새 탭)")
                    self.smart_sleep(10, "등록 버튼 클릭 후 안정화 대기")
                    
                    # 등록 후 제목 관련 팝업 확인 및 처리
                    popup_occurred = self.handle_title_popup(driver)
                    
                    if popup_occurred:
                        if submit_attempt < max_submit_retries - 1:
                            self.signals.progress.emit(f"⚠️ 제목 누락 팝업 발생 - 제목 재입력 후 재시도 {submit_attempt + 2}/{max_submit_retries}")
                            
                            # 팝업 처리 후 페이지 안정화 대기
                            self.smart_sleep(3, "팝업 처리 후 페이지 안정화 대기")
                            
                            # 제목 다시 입력
                            try:
                                title_input = self.wait_for_element_with_retry(
                                    driver, By.CSS_SELECTOR, 'textarea[placeholder="제목을 입력해 주세요."]',
                                    element_name="제목 입력 필드"
                                )
                                
                                # 제목 필드 클릭으로 포커스 설정
                                self.safe_click_with_retry(driver, title_input, element_name="제목 입력 필드")
                                self.smart_sleep(1, "제목 필드 포커스 후 대기")
                                
                                # 직접 입력 방식 사용 (safe_input_text 대신)
                                self.signals.progress.emit("🔧 제목 직접 입력 방식 사용")
                                
                                # 전체 선택 후 삭제
                                title_input.send_keys(Keys.CONTROL + 'a')
                                self.smart_sleep(1.5, "전체 선택 후 대기")
                                title_input.send_keys(Keys.DELETE)
                                self.smart_sleep(1.5, "삭제 후 대기")
                                
                                # 제목 입력
                                title_input.send_keys(parser.title)
                                self.smart_sleep(1.5, "제목 입력 후 대기")
                                
                                # 입력 확인
                                input_value = title_input.get_attribute('value')
                                if not input_value:
                                    input_value = title_input.text
                                
                                # 공백 제거 후 확인
                                input_value_cleaned = input_value.strip() if input_value else ""
                                expected_title_cleaned = parser.title.strip()
                                
                                self.signals.progress.emit(f"📋 입력된 값: '{input_value_cleaned}' (길이: {len(input_value_cleaned)})")
                                self.signals.progress.emit(f"📋 예상 제목: '{expected_title_cleaned}' (길이: {len(expected_title_cleaned)})")
                                
                                if input_value_cleaned and expected_title_cleaned in input_value_cleaned:
                                    self.signals.progress.emit(f"✅ 제목 재입력 성공")
                                else:
                                    self.signals.progress.emit(f"❌ 제목 재입력 실패 - 입력값이 비어있거나 일치하지 않음")
                                    # 한 번 더 시도
                                    self.signals.progress.emit("🔄 제목 재입력 재시도...")
                                    title_input.clear()
                                    time.sleep(0.5)
                                    title_input.click()
                                    time.sleep(0.5)
                                    title_input.send_keys(parser.title)
                                    time.sleep(0.5)
                                
                                self.signals.progress.emit("✅ 제목 재입력 완료")
                                self.smart_sleep(2, "제목 재입력 후 대기")
                                continue  # 다시 등록 버튼 클릭 시도
                                
                            except Exception as title_error:
                                self.signals.progress.emit(f"❌ 제목 재입력 실패: {title_error}")
                                if submit_attempt == max_submit_retries - 1:
                                    raise Exception(f"제목 재입력 최종 실패: {title_error}")
                                continue
                        else:
                            raise Exception("등록 최종 실패 - 제목 팝업 지속 발생")
                    
                    # 📌 답글 작성 폼 사라짐 확인으로 등록 성공 여부 판단
                    self.smart_sleep(2, "등록 완료 확인 대기")
                    
                    try:
                        # 답글 작성 폼이 아직 있는지 확인
                        title_form = driver.find_element(By.CSS_SELECTOR, 'textarea[placeholder="제목을 입력해 주세요."]')
                        
                        if title_form.is_displayed():
                            # 작성 폼이 아직 있음 = 등록 실패
                            if submit_attempt < max_submit_retries - 1:
                                self.signals.progress.emit(f"⚠️ 답글 등록 실패 - 작성 폼이 아직 존재 (재시도 {submit_attempt + 2}/{max_submit_retries})")
                                continue
                            else:
                                raise Exception("답글 등록 최종 실패 - 작성 폼이 계속 존재")
                        else:
                            # 작성 폼이 보이지 않음 = 등록 성공
                            submit_success = True
                            self.signals.progress.emit("✅ 답글 등록 성공 - 작성 폼 사라짐 확인")
                            break
                            
                    except Exception:
                        # 작성 폼을 찾을 수 없음 = 등록 성공 (페이지가 변경됨)
                        submit_success = True
                        self.signals.progress.emit("✅ 답글 등록 성공 - 작성 페이지 이탈 확인")
                        break
                    
                except Exception as e:
                    if submit_attempt < max_submit_retries - 1:
                        self.signals.progress.emit(f"⚠️ 등록 실패 (시도 {submit_attempt + 1}/{max_submit_retries}): {e}")
                        self.smart_sleep(2, "등록 재시도 전 대기")
                    else:
                        self.signals.progress.emit(f"❌ 등록 최종 실패: {e}")
                        raise Exception(f"등록 {max_submit_retries}번 모두 실패: {e}")
            
            if not submit_success:
                raise Exception("등록 처리 실패")
            
            # 📌 답글 등록 완료 후 페이지 안정화 대기
            self.emit_progress("⏳ 답글 등록 완료, 페이지 안정화 대기 중...", thread_id)
            self.smart_sleep(10, "답글 등록 완료 후 안정화 대기")  # 5초에서 10초로 증가
            
            # 🔥 URL 추출 안정성 강화: 답글방식의 개선된 재시도 로직 적용
            reply_url = None
            valid_url_found = False
            max_url_attempts = 5  # 최대 5회 시도 (답글방식에서 가져온 최적화)
            
            for url_attempt in range(max_url_attempts):
                self.emit_progress(f"🔍 유효한 URL 추출 시도 {url_attempt + 1}/{max_url_attempts}", thread_id)
                
                try:
                    # iframe 내부인 경우 다시 진입 시도
                    try:
                        driver.switch_to.default_content()
                        iframe = driver.find_element(By.CSS_SELECTOR, "iframe#cafe_main")
                        driver.switch_to.frame(iframe)
                        if url_attempt == 0:
                            self.emit_progress("🔄 iframe 재진입 완료", thread_id)
                    except:
                        # iframe이 없거나 이미 내부에 있는 경우
                        pass
                    
                    # #spiButton에서 data-url 추출 시도
                    def check_spi_button(driver):
                        """#spiButton의 data-url 속성을 확인하는 함수"""
                        try:
                            return driver.execute_script("""
                                const spiButton = document.querySelector('#spiButton');
                                if (spiButton && spiButton.getAttribute('data-url')) {
                                    return spiButton.getAttribute('data-url');
                                }
                                return null;
                            """)
                        except:
                            return None
                    
                    # 25초 동안 #spiButton 확인 (3초마다) - 답글방식의 더 안정적인 간격
                    start_time = time.time()
                    while time.time() - start_time < 25:
                        candidate_url = check_spi_button(driver)
                        if candidate_url and self.is_valid_reply_url(candidate_url):
                            reply_url = candidate_url
                            valid_url_found = True
                            elapsed_time = round(time.time() - start_time, 1)
                            self.emit_progress(f"✅ 유효한 답글 URL 추출 성공 ({elapsed_time}초 소요): {reply_url}", thread_id)
                            break
                        elif candidate_url:
                            self.emit_progress(f"⚠️ 무효한 URL 감지: {candidate_url}", thread_id)
                        time.sleep(3)  # 3초마다 확인 (답글방식의 더 안정적인 간격)
                    
                    if valid_url_found:
                        break
                        
                    # 다른 방법 시도: 현재 URL 확인
                    current_url = driver.current_url
                    if self.is_valid_reply_url(current_url):
                        reply_url = current_url
                        valid_url_found = True
                        self.emit_progress(f"✅ 현재 페이지 URL이 유효함: {reply_url}", thread_id)
                        break
                    else:
                        self.emit_progress(f"❌ 현재 URL도 무효함: {current_url}", thread_id)
                        
                except Exception as e:
                    self.emit_progress(f"⚠️ URL 추출 시도 {url_attempt + 1} 실패: {str(e)}", thread_id)
                
                # 재시도 전 대기
                if url_attempt < max_url_attempts - 1:
                    self.smart_sleep(3, f"URL 추출 재시도 전 대기")
            
            # 유효한 URL을 얻지 못한 경우 답글 작성 실패로 처리
            if not valid_url_found or not reply_url:
                self.emit_progress("❌ 유효한 답글 URL을 추출할 수 없습니다", thread_id)
                reply_url = driver.current_url  # 최후 수단으로 현재 URL 사용
            
            self.emit_progress(f"📝 최종 답글 URL 수집: {reply_url}", thread_id)
            
            # IP 주소 수집
            reply_ip = self.get_current_ip(driver)
            self.emit_progress(f"🌐 답글 작성 IP: {reply_ip}", thread_id)
            
            # 📌 답글 완료 시 결과 업데이트 (직접 메서드 호출)
            update_data = {
                '답글아이디로그인아이피': reply_ip,
                '답글URL': reply_url,
                '댓글상황': '작성 중...',  # 댓글 작성 시작 표시
                '폴더명': folder_name,  # 폴더명 유지
                'account_id': successful_account[0],  # account_id 유지
                'cafe_name': getattr(self, 'current_cafe_name', ''),  # cafe_name 유지
                'script_folder': getattr(parser, 'script_folder', '')  # script_folder 유지
            }
            self.main_window.update_result(current_row, update_data)
            self.emit_progress(f"✅ 결과 테이블 업데이트 완료 (행 {current_row+1}): {reply_url[:50]}...", thread_id)
            
            # 🆔 답글 작성 성공 시 계정 사용 횟수 증가
            if successful_account:
                self.main_window.increment_account_usage(successful_account[0])
            
            # 📌 답글 성공한 계정 상태 기록
            if successful_account and not hasattr(self, 'account_status_log'):
                self.account_status_log = {}
            if successful_account:
                self.account_status_log[successful_account[0]] = {
                    'status': '카페 가입됨 (답글 작성 성공)',
                    'type': 'reply',
                    'thread_id': thread_id,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            # 🔗 1단계에서 얻은 URL을 바로 사용 (2단계 연쇄시스템 제거)
            next_reply_url = reply_url
            self.emit_progress(f"✅ 답글 URL을 다음 작업용으로 설정: {next_reply_url[:50]}...", thread_id)
            
            # 로그아웃
            self.logout_naver(driver)
            
            return successful_account, reply_url, reply_ip, current_row, next_reply_url
            
        except Exception as e:
            # 📌 답글 실패 시 결과 테이블 업데이트
            try:
                if 'current_row' in locals():
                    update_data = {
                        '답글아이디로그인아이피': '실패',
                        '답글URL': f'오류: {str(e)[:30]}...'
                    }
                    self.main_window.update_result(current_row, update_data)
                    self.signals.progress.emit(f"❌ 결과 테이블에 실패 표시됨 (행 {current_row+1})")
                
                # 📌 실패한 계정 상태 기록
                if 'successful_account' in locals() and successful_account:
                    if not hasattr(self, 'account_status_log'):
                        self.account_status_log = {}
                    self.account_status_log[successful_account[0]] = {
                        'status': f'답글 작성 실패: {str(e)[:50]}',
                        'type': 'reply',
                        'thread_id': thread_id,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
            except Exception as update_error:
                self.signals.progress.emit(f"⚠️ 결과 테이블 업데이트 실패: {update_error}")
            
            # 예외 발생 시에도 크롬창 안전 정리
            try:
                driver.switch_to.default_content()
                self.signals.progress.emit(f"🧹 [쓰레드{thread_id}] 답글 작성 실패 - 크롬창 정리 중...")
                self.safe_cleanup_thread_drivers(thread_id)
            except Exception as cleanup_error:
                self.signals.progress.emit(f"⚠️ [쓰레드{thread_id}] 정리 중 오류: {cleanup_error}")
            raise e
    
    def try_solve_captcha_with_gpt(self, driver, login_id, password, thread_id=None):
        """GPT로 캡차 해결 시도 (5회)"""
        # 먼저 캡차가 있는지 확인
        try:
            captcha_image = driver.find_element(By.ID, "captchaimg")
            if not captcha_image.is_displayed():
                return False
        except:
            # 캡차가 없으면 성공으로 처리
            return True
        
        # 캡차가 있을 때만 API 키 확인 및 openai import
        api_key = app_config.get('gpt_api_key')
        if not api_key:
            self.emit_progress("⚠️ GPT API 키가 없어 캡차 해결 불가", thread_id)
            return False
        
        # openai 모듈이 이미 import되어 있음
        
        # GPT로 5회 시도
        for attempt in range(1, 6):
            self.signals.progress.emit(f"🤖 GPT 캡차 해결 시도: {attempt}/5번째")
            
            try:
                image_src = captcha_image.get_attribute("src")
                if not image_src:
                    continue
                
                # 캡차 문제 텍스트
                try:
                    captcha_info = driver.find_element(By.ID, "captcha_info")
                    problem_text = captcha_info.text
                except:
                    problem_text = "이미지에서 요구하는 내용을 찾아 답을 입력해주세요."
                
                # GPT API 호출
                captcha_text = self.solve_captcha_with_chatgpt(image_src, problem_text)
                if not captcha_text:
                    continue
                
                # 캡차 답 입력
                captcha_input = driver.find_element(By.ID, "captcha")
                driver.execute_script("arguments[0].focus();", captcha_input)
                driver.execute_script("arguments[0].value = '';", captcha_input)
                driver.execute_script(f"arguments[0].value = '{captcha_text}';", captcha_input)
                
                # 로그인 버튼 다시 클릭
                login_button = driver.find_element(By.ID, "log.login")
                login_button.click()
                
                self.smart_sleep(3, "캡차 해결 후 로그인 대기")
                
                # 로그인 성공 확인
                current_url = driver.current_url
                if "naver.com" in current_url:
                    self.signals.progress.emit(f"✅ 캡차 해결 후 로그인 성공!")
                    return True
                
            except Exception as e:
                self.signals.progress.emit(f"⚠️ 캡차 해결 시도 실패: {str(e)}")
                continue
        
        self.signals.progress.emit(f"❌ GPT 캡차 해결 5회 모두 실패")
        return False
    
    def write_comments(self, thread_id, reply_url, parser, reply_account):
        """댓글들 작성 (답글 계정 정보 포함)"""
        self.emit_progress(f"💬 댓글 작성 시작 - 총 {len(parser.comments)}개 댓글", thread_id)
        self.emit_progress(f"📌 답글 계정: {reply_account[0]} (작성자 댓글용)", thread_id)
        
        if not parser.comments:
            self.emit_progress("⚠️ 작성할 댓글이 없습니다", thread_id)
            return 0, 0  # 댓글 없음 시 0개 반환
        
        written_comments = []  # 작성된 댓글들을 추적
        
        for i, comment in enumerate(parser.comments):
            if not self.is_running:
                break
            
            # 🔄 댓글별 다중 계정 재시도 시스템
            success = self.process_single_comment(thread_id, reply_url, comment, reply_account, i, len(parser.comments), written_comments)
            
            if success:
                written_comments.append(comment)
                # 🔥 로그 스팸 최적화: 댓글 완료 로그도 5개마다만 (답글방식에서 가져온 최적화)
                if i % 5 == 0 or i == len(parser.comments) - 1:
                    self.emit_progress(f"✅ 댓글 {i+1}/{len(parser.comments)} 작성 완료", thread_id)
            else:
                # 🔥 로그 스팸 최적화: 실패 로그도 5개마다만 (답글방식에서 가져온 최적화)
                if i % 5 == 0 or i == len(parser.comments) - 1:
                    self.emit_progress(f"❌ 댓글 {i+1}/{len(parser.comments)} 모든 계정 시도 실패 - 건너뜀", thread_id)
            
            # 댓글 간 대기 (단축된 대기 시간)
            if i < len(parser.comments) - 1:
                wait_seconds = 15  # 15초로 변경
                
                self.emit_progress(f"⏳ {wait_seconds}초 대기 후 다음 댓글 작성...", thread_id)
                for _ in range(wait_seconds):
                    if not self.is_running:
                        break
                    time.sleep(1)
        
        # 📌 각 댓글마다 브라우저를 종료하므로 별도 정리 불필요
        success_count = len(written_comments)
        total_count = len(parser.comments)
        self.emit_progress(f"🎉 댓글 작성 완료 - {total_count}개 중 {success_count}개 댓글 처리 완료", thread_id)
        
        return success_count, total_count  # 성공/전체 댓글 개수 반환
    
    def process_single_comment(self, thread_id, reply_url, comment, reply_account, comment_index, total_comments, written_comments):
        """단일 댓글 작성 (다중 계정 재시도 포함)"""
        max_account_retry = 10  # 최대 10개 계정까지 시도
        
        for account_attempt in range(max_account_retry):
            if not self.is_running:
                return False
            
            try:
                if account_attempt > 0:
                    self.emit_progress(f"🔄 댓글 {comment_index+1} 다른 계정으로 재시도 ({account_attempt+1}/{max_account_retry})", thread_id)
                else:
                    # 🔥 로그 스팸 최적화: 댓글 로그 빈도 줄이기 - 5개마다 또는 첫/마지막만 (답글방식에서 가져온 최적화)
                    if comment_index % 5 == 0 or comment_index == total_comments - 1:
                        self.emit_progress(f"📝 댓글 {comment_index+1}/{total_comments} 작성 중", thread_id)
                
                # 계정 선택
                if comment['type'] == 'author':
                    # 📌 작성자 댓글 - 답글 작성자와 같은 계정 사용 (재시도 시에도 동일)
                    account = reply_account
                    account_type = 'reply'
                    self.emit_progress(f"👤 작성자 댓글 - 답글 작성자 계정 사용: {account[0]}", thread_id)
                else:
                    # 일반 댓글 - 🔄 재시도 시 새로운 계정 할당
                    if account_attempt == 0:
                        # 첫 번째 시도: 기존 매핑 확인
                        if thread_id not in self.thread_id_account_mapping:
                            self.thread_id_account_mapping[thread_id] = {}
                        
                        comment_id = comment.get('id_num', 'unknown')
                        thread_mapping = self.thread_id_account_mapping[thread_id]
                        
                        if comment_id in thread_mapping:
                            # 🔄 기존에 할당된 계정 재사용
                            account = thread_mapping[comment_id]
                            self.emit_progress(f"👥 아이디{comment_id} 기존 계정 재사용: {account[0]}", thread_id)
                        else:
                            # 🆕 새로운 계정 할당 후 매핑 저장 (답글 작성자 제외)
                            account = self.main_window.get_comment_account_from_pool(exclude_account_id=reply_account[0])
                            if not account:
                                self.emit_progress(f"❌ 사용 가능한 댓글 계정이 없습니다 (답글 작성자 {reply_account[0]} 제외)", thread_id)
                                return False  # 더 이상 시도할 계정 없음
                            thread_mapping[comment_id] = account
                            self.emit_progress(f"👥 아이디{comment_id} 새 계정 할당: {account[0]} (답글 작성자 {reply_account[0]} 제외)", thread_id)
                    else:
                        # 재시도: 새로운 계정 할당 (기존 매핑 무시, 답글 작성자 제외)
                        account = self.main_window.get_comment_account_from_pool(exclude_account_id=reply_account[0])
                        if not account:
                            self.emit_progress(f"❌ 재시도용 댓글 계정이 없습니다 (답글 작성자 {reply_account[0]} 제외)", thread_id)
                            return False  # 더 이상 시도할 계정 없음
                        self.emit_progress(f"🔄 아이디{comment.get('id_num', 'unknown')} 재시도 계정: {account[0]} (답글 작성자 {reply_account[0]} 제외)", thread_id)
                    
                    account_type = 'comment'
                
                # 로그인 및 댓글 작성
                driver = self.get_driver(thread_id, account_type, account[0])
                if driver is None:
                    self.emit_progress(f"🛑 [스레드{thread_id+1}] 드라이버 생성 실패 - 댓글 작성 불가: {account[0]}", thread_id)
                    return False
                
                self.emit_progress(f"🔑 [스레드{thread_id+1}] 로그인 시도: {account[0]}", thread_id)
                login_result = self.login_naver(driver, account[0], account[1], thread_id)
                if not login_result[0]:
                    failure_reason = login_result[1]
                    self.emit_progress(f"❌ [스레드{thread_id+1}] 로그인 실패: {account[0]} - {failure_reason}", thread_id)
                    
                    # 🔄 모든 로그인 실패는 차단 목록에 추가 (재시도 방지)
                    if account_type == 'comment':
                        self.main_window.mark_comment_account_blocked(account[0])
                    elif account_type == 'reply':
                        self.main_window.mark_reply_account_blocked(account[0])
                    self.emit_progress(f"🚫 [스레드{thread_id+1}] 계정 {account[0]} 차단 목록 추가 (로그인 실패)", thread_id)
                    
                    # 드라이버 정리 후 다음 계정으로 재시도
                    try:
                        driver.quit()
                    except:
                        pass
                    continue
                
                self.emit_progress(f"✅ [스레드{thread_id+1}] 로그인 성공: {account[0]}", thread_id)
                
                # 답글 페이지로 이동
                self.emit_progress(f"💬 댓글 작성 페이지로 이동: {reply_url}", thread_id)
                driver.get(reply_url)
                
                # 페이지 로딩 완료 대기
                if not self.wait_for_page_load(driver):
                    self.emit_progress("⚠️ 댓글 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
                
                self.smart_sleep(10, "댓글 페이지 로딩 후 대기")
                
                # 삭제된 게시글 팝업 확인
                if self.handle_deleted_post_popup(driver):
                    self.emit_progress(f"❌ 답글이 삭제되어 댓글 작성 불가: {reply_url}", thread_id)
                    # 결과 테이블 업데이트
                    if hasattr(self, 'current_row'):
                        update_data = {'댓글상황': '답글 삭제됨'}
                        self.main_window.update_result(self.current_row, update_data)
                    # 로그아웃 후 종료
                    self.logout(driver)
                    driver.quit()
                    return False
                
                # 기존 댓글들이 모두 로딩될 때까지 대기
                self.wait_for_existing_comments_to_load(driver)
                
                # iframe 진입
                try:
                    iframe = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, "iframe#cafe_main",
                        max_wait=10, element_name="iframe#cafe_main"
                    )
                    driver.switch_to.frame(iframe)
                    self.signals.progress.emit("🔄 댓글 작성을 위한 iframe 진입")
                except Exception as e:
                    self.signals.progress.emit("ℹ️ iframe 진입 불필요 또는 실패")
                
                # 📌 댓글 입력 전 카페 가입 여부 체크
                try:
                    cafe_join_elements = driver.find_elements(By.XPATH, 
                        "//a[contains(@class, 'btn_join') and contains(text(), '지금 가입하고 댓글에 참여해보세요')]")
                    
                    if cafe_join_elements:
                        # 카페 미가입 계정 감지
                        self.emit_progress(f"🚫 [스레드{thread_id+1}] 카페 미가입 계정: {account[0]} - 차단 목록 추가", thread_id)
                        
                        # 계정별 차단 처리
                        if account_type == 'comment':
                            self.main_window.mark_comment_account_blocked(account[0])
                        elif account_type == 'reply':
                            self.main_window.mark_reply_account_blocked(account[0])
                        
                        # 카페 미가입 상태 기록 (새 필드 추가)
                        if not hasattr(self, 'account_status_log'):
                            self.account_status_log = {}
                        self.account_status_log[account[0]] = {
                            'status': '카페 미가입',
                            'type': account_type,
                            'thread_id': thread_id,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # 드라이버 정리 후 다음 계정으로 재시도
                        try:
                            driver.quit()
                        except:
                            pass
                        continue  # 다음 계정으로 재시도
                        
                except Exception as cafe_check_error:
                    self.signals.progress.emit(f"⚠️ 카페 가입 상태 확인 실패: {cafe_check_error}")
                
                # 댓글 내용 미리보기
                comment_preview = comment['content'][:30] + "..." if len(comment['content']) > 30 else comment['content']
                comment_level = comment.get('level', 0)
                
                # 레벨에 따른 댓글/대댓글 처리
                if comment_level == 0:
                    # 일반 댓글 처리
                    self.signals.progress.emit(f"💭 일반 댓글 입력: {comment_preview}")
                    
                    # 댓글 입력창 찾기
                    comment_input = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'textarea.comment_inbox_text',
                        max_wait=10, element_name="댓글 입력창"
                    )
                    
                    # 댓글 입력창으로 스크롤
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", comment_input)
                    self.smart_sleep(1, "스크롤 완료 대기")
                    
                    # 댓글 입력
                    if not self.safe_click_with_retry(driver, comment_input, element_name="댓글 입력창"):
                        self.signals.progress.emit("⚠️ 댓글 입력창 클릭 실패, 계속 진행")
                    
                    if not self.safe_input_text(driver, comment_input, comment['content'], "댓글"):
                        raise Exception("댓글 입력 실패")
                    
                    # 일반 댓글 등록 버튼
                    submit_btn = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'a.button.btn_register',
                        max_wait=10, element_name="댓글 등록 버튼"
                    )
                    button_name = "댓글 등록 버튼"
                else:
                    # 대댓글 처리
                    self.signals.progress.emit(f"↩️ 대댓글 입력 (level {comment_level}): {comment_preview}")
                    
                    # 부모 댓글 찾기
                    parent_comment = self.find_parent_comment(driver, comment, written_comments)
                    if not parent_comment:
                        raise Exception("부모 댓글을 찾을 수 없습니다")
                    
                    # 답글 버튼 찾기 및 클릭
                    reply_btn = None
                    for selector in ['.comment_info_button', 'a.comment_reply_link', '.btn_reply']:
                        try:
                            reply_btn = parent_comment.find_element(By.CSS_SELECTOR, selector)
                            break
                        except:
                            continue
                    
                    if not reply_btn:
                        raise Exception("답글 버튼을 찾을 수 없습니다")
                    
                    # 답글 버튼 클릭
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", reply_btn)
                    self.smart_sleep(1, "답글 버튼 스크롤 완료 대기")
                    
                    if not self.safe_click_with_retry(driver, reply_btn, element_name="답글 버튼"):
                        raise Exception("답글 버튼 클릭 실패")
                    
                    self.smart_sleep(1, "답글 버튼 클릭 후 대기")
                    
                    # 대댓글 입력창 찾기 및 입력
                    reply_input = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'textarea.comment_inbox_text',
                        max_wait=10, element_name="대댓글 입력창"
                    )
                    
                    if not self.safe_click_with_retry(driver, reply_input, element_name="대댓글 입력창"):
                        self.signals.progress.emit("⚠️ 대댓글 입력창 클릭 실패, 계속 진행")
                    
                    if not self.safe_input_text(driver, reply_input, comment['content'], "대댓글"):
                        raise Exception("대댓글 입력 실패")
                    
                    # 대댓글 등록 버튼
                    submit_btn = self.wait_for_element_with_retry(
                        driver, By.CSS_SELECTOR, 'a.button.btn_register.is_active',
                        max_wait=10, element_name="대댓글 등록 버튼"
                    )
                    button_name = "대댓글 등록 버튼"
                
                # 등록 버튼 클릭
                self.signals.progress.emit(f"📜 {button_name}으로 스크롤...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", submit_btn)
                self.smart_sleep(1, "스크롤 완료 대기")
                
                if not self.safe_click_with_retry(driver, submit_btn, element_name=button_name):
                    raise Exception(f"{button_name} 클릭 실패")
                
                driver.switch_to.default_content()
                self.smart_sleep(10, "댓글 등록 후 대기")
                
                self.smart_sleep(2, "댓글 등록 완료 확인 대기")  
                
                # 📌 성공한 계정 상태 기록
                if not hasattr(self, 'account_status_log'):
                    self.account_status_log = {}
                self.account_status_log[account[0]] = {
                    'status': '카페 가입됨 (댓글 작성 성공)',
                    'type': account_type,
                    'thread_id': thread_id,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # 성공 시 브라우저 정리 후 return True
                self.emit_progress(f"🚪 [스레드{thread_id+1}] 댓글 완료 - 브라우저 종료 중...", thread_id)
                self.logout_naver(driver)
                
                # 개별 드라이버만 정리 (다른 계정 드라이버는 유지)
                driver_key = f"{thread_id}_{account_type}_{account[0]}"
                with self.drivers_lock:
                    if driver_key in self.drivers:
                        try:
                            driver.quit()
                            # 🔧 드라이버 종료 로그 제거 (너무 빈번함)
                        except:
                            pass
                        del self.drivers[driver_key]
                
                # 개별 계정의 크롬 프로세스만 종료 (전체 스레드 종료하지 않음)
                self.emit_progress(f"🧹 [스레드{thread_id+1}] 댓글 {comment_index+1} 작성 완료 - 개별 브라우저 정리", thread_id)
                return True  # 성공
            
            except Exception as e:
                self.emit_progress(f"❌ [스레드{thread_id+1}] 댓글 {comment_index+1} 계정 {account[0]} 시도 실패: {str(e)}", thread_id)
                
                # 실패 시 개별 드라이버만 정리
                try:
                    if 'driver' in locals():
                        self.logout_naver(driver)
                        driver.quit()
                        # 드라이버 딕셔너리에서도 제거
                        driver_key = f"{thread_id}_{account_type}_{account[0]}"
                        with self.drivers_lock:
                            if driver_key in self.drivers:
                                del self.drivers[driver_key]
                                                    # 🔧 실패 로그도 제거
                except:
                    pass
                
                # 개별 계정의 브라우저만 정리 (전체 스레드 종료하지 않음)
                self.emit_progress(f"🧹 [스레드{thread_id+1}] 댓글 {comment_index+1} 실패 - 개별 브라우저 정리", thread_id)
                # 다음 계정으로 재시도
        
        # 모든 계정 시도 실패
        return False
    
    def clear_and_input_content(self, driver, content, image_paths):
        """🆕 수정 모드: 기존 내용 지우고 새 내용 입력"""
        try:
            # 입력 가능한 요소 찾기 (네이버 카페 스마트에디터 구조 반영)
            selectors = [
                'div.se-module.se-module-text',     # 🔥 네이버 카페 메인 입력 영역
                'span.se-placeholder',              # 🔥 네이버 카페 플레이스홀더 영역
                '[contenteditable="true"]',         # 기존 호환성 유지
                'div[role="textbox"]',
                'div[data-placeholder]'
            ]
            
            target = None
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        target = el
                        break
                if target:
                    break
            
            if not target:
                raise Exception("입력 가능한 요소를 찾을 수 없습니다")
            
            # 클릭하여 포커스
            ActionChains(driver).move_to_element(target).click().perform()
            time.sleep(1)
            
            # 🆕 기존 내용 모두 선택 후 삭제
            ActionChains(driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
            ActionChains(driver).send_keys(Keys.DELETE).perform()
            time.sleep(1)
            
            # 내용을 이미지 마커로 분할
            segments = re.split(r"<이미지마커:(\d+)>", content)
            
            for i, part in enumerate(segments):
                if i % 2 == 0:  # 텍스트 부분
                    if part.strip():
                        for line in part.strip().splitlines():
                            ActionChains(driver).send_keys(line).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()
                            time.sleep(0.1)
                else:  # 이미지 마커
                    index = int(part)
                    if 0 <= index < len(image_paths):
                        # 기존 이미지 개수 체크 (업로드 완료 확인용)
                        try:
                            existing_images = driver.find_elements(By.CSS_SELECTOR, 
                                "img, .se-image-resource, [data-type='image'], .se-module-image")
                            initial_image_count = len(existing_images)
                        except:
                            initial_image_count = 0
                        
                        # 네트워크 상태에 따른 대기 시간 조정
                        network_status, _, _ = self.check_network_health()
                        if network_status in ["slow", "very_slow", "disconnected"]:
                            image_wait_time = 8
                        else:
                            image_wait_time = 5
                        
                        # 이미지 클립보드에 설정
                        if set_clipboard_image(image_paths[index]):
                            # Ctrl+V로 붙여넣기
                            ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                            
                            # 이미지 업로드 완료 대기
                            time.sleep(image_wait_time)
                            
                            # 업로드 완료 확인
                            try:
                                current_images = driver.find_elements(By.CSS_SELECTOR, 
                                    "img, .se-image-resource, [data-type='image'], .se-module-image")
                                if len(current_images) > initial_image_count:
                                    self.signals.progress.emit(f"✅ 이미지 {index+1} 업로드 완료")
                                else:
                                    self.signals.progress.emit(f"⚠️ 이미지 {index+1} 업로드 확인 실패")
                            except:
                                self.signals.progress.emit(f"⚠️ 이미지 {index+1} 업로드 상태 확인 불가")
                        else:
                            self.signals.progress.emit(f"❌ 이미지 {index+1} 클립보드 설정 실패")
            
            return True
            
        except Exception as e:
            self.signals.progress.emit(f"❌ 수정 모드 본문 입력 실패: {str(e)}")
            return False

    def input_content_with_images(self, driver, content, image_paths):
        """본문과 이미지 입력"""
        try:
            # 입력 가능한 요소 찾기 (네이버 카페 스마트에디터 구조 반영)
            selectors = [
                'div.se-module.se-module-text',     # 🔥 네이버 카페 메인 입력 영역
                'span.se-placeholder',              # 🔥 네이버 카페 플레이스홀더 영역
                '[contenteditable="true"]',         # 기존 호환성 유지
                'div[role="textbox"]',
                'div[data-placeholder]'
            ]
            
            target = None
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        target = el
                        break
                if target:
                    break
            
            if not target:
                raise Exception("입력 가능한 요소를 찾을 수 없습니다")
            
            # 클릭하여 포커스
            ActionChains(driver).move_to_element(target).click().perform()
            time.sleep(1)
            
            # 내용을 이미지 마커로 분할
            segments = re.split(r"<이미지마커:(\d+)>", content)
            
            for i, part in enumerate(segments):
                if i % 2 == 0:  # 텍스트 부분
                    if part.strip():
                        for line in part.strip().splitlines():
                            ActionChains(driver).send_keys(line).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()
                            time.sleep(0.1)
                else:  # 이미지 마커
                    index = int(part)
                    if 0 <= index < len(image_paths):
                        # 기존 이미지 개수 체크 (업로드 완료 확인용)
                        try:
                            existing_images = driver.find_elements(By.CSS_SELECTOR, 
                                "img, .se-image-resource, [data-type='image'], .se-module-image")
                            initial_image_count = len(existing_images)
                        except:
                            initial_image_count = 0
                        
                        # 네트워크 상태에 따른 대기 시간 조정
                        network_status, _, _ = self.check_network_health()
                        if network_status == "very_slow":
                            upload_timeout = 30
                        elif network_status == "slow":
                            upload_timeout = 20
                        elif network_status == "disconnected":
                            upload_timeout = 40
                        else:
                            upload_timeout = 15
                        
                        # 클립보드 Lock을 이미지 업로드 완료까지 확장
                        with self.clipboard_lock:
                            # 이미지를 클립보드에 설정
                            if not set_clipboard_image(image_paths[index]):
                                self.signals.progress.emit(f"⚠️ 이미지 클립보드 설정 실패: {image_paths[index]}")
                                continue
                            
                            time.sleep(1)  # 클립보드 설정 안정화 대기 (0.5초 → 1초)
                            
                            # 이미지 붙여넣기
                            ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                            
                            # WebDriverWait으로 이미지 업로드 완료까지 대기
                            try:
                                from selenium.webdriver.support.ui import WebDriverWait
                                from selenium.webdriver.support import expected_conditions as EC
                                
                                # 이미지가 추가될 때까지 대기
                                WebDriverWait(driver, upload_timeout).until(
                                    lambda d: len(d.find_elements(By.CSS_SELECTOR, 
                                        "img, .se-image-resource, [data-type='image'], .se-module-image")) > initial_image_count
                                )
                                self.signals.progress.emit(f"✅ 이미지 업로드 완료 (네트워크: {network_status})")
                                
                                # 추가 안정화 대기 (업로드 완료 후)
                                time.sleep(1)
                                
                            except Exception as e:
                                self.signals.progress.emit(f"⚠️ 이미지 업로드 대기 실패: {str(e)} - 기본 대기로 진행")
                                time.sleep(3)  # 실패 시 기본 3초 대기
            
            return True
            
        except Exception as e:
            self.signals.progress.emit(f"❌ 본문 입력 실패: {str(e)}")
            return False
    
    def get_driver(self, thread_id, account_type, account_id=None):
        """스레드별 드라이버 가져오기 (계정별 고정 프록시 지원)"""
        # 계정별로 고유한 드라이버 키 생성
        if account_id:
            driver_key = f"{thread_id}_{account_type}_{account_id}"
        else:
            driver_key = f"{thread_id}_{account_type}"
        
        with self.drivers_lock:
            if driver_key in self.drivers:
                # 기존 드라이버 상태 확인
                existing_driver = self.drivers[driver_key]
                try:
                    # 드라이버가 살아있는지 확인
                    existing_driver.current_url
                    return existing_driver
                except:
                    # 드라이버가 죽어있으면 딕셔너리에서 제거
                    self.emit_progress(f"🔄 [스레드{thread_id}] 기존 드라이버 {driver_key} 죽어있음 - 새로 생성", thread_id)
                    del self.drivers[driver_key]
        
        # 새 드라이버 생성 (계정 정보와 스레드 정보 전달)
        try:
            driver = self.create_chrome_driver(account_type, account_id, thread_id)
        except Exception as e:
            self.emit_progress(f"🛑 [스레드{thread_id}] 드라이버 생성 포기: {str(e)}", thread_id)
            self.emit_progress(f"🛑 [스레드{thread_id}] 더 이상 재시도하지 않음 - 작업 중단", thread_id)
            return None  # None 반환으로 상위에서 처리하도록
        
        with self.drivers_lock:
            self.drivers[driver_key] = driver
        
        return driver
    
    def get_fixed_proxy_for_account(self, account_id, proxies):
        """계정별 고정 프록시 선택 (해시 기반)"""
        if not proxies:
            return None
        
        # 계정 ID의 해시값을 이용해 고정된 인덱스 생성
        hash_value = hash(account_id) % len(proxies)
        return proxies[hash_value]
    
    def fix_chromedriver_cache(self):
        """🔧 ChromeDriverManager 캐시 손상 문제 해결"""
        try:
            import shutil
            from pathlib import Path
            
            # ChromeDriverManager 캐시 폴더 찾기
            cache_folders = [
                Path.home() / ".wdm",  # 기본 캐시 폴더
                Path(tempfile.gettempdir()) / ".wdm",  # 임시 폴더 캐시
                Path(os.getcwd()) / ".wdm"  # 현재 폴더 캐시
            ]
            
            cleaned_count = 0
            for cache_folder in cache_folders:
                try:
                    if cache_folder.exists():
                        shutil.rmtree(cache_folder, ignore_errors=True)
                        cleaned_count += 1
                        self.signals.progress.emit(f"🧹 ChromeDriver 캐시 정리: {cache_folder}")
                except Exception as e:
                    self.signals.progress.emit(f"⚠️ 캐시 정리 실패: {cache_folder} - {e}")
            
            if cleaned_count > 0:
                self.signals.progress.emit(f"✅ ChromeDriver 캐시 {cleaned_count}개 폴더 정리 완료")
                # 캐시 정리 후 잠시 대기
                time.sleep(1)
            else:
                self.signals.progress.emit("ℹ️ 정리할 ChromeDriver 캐시가 없습니다")
                
        except Exception as e:
            self.signals.progress.emit(f"❌ ChromeDriver 캐시 정리 실패: {e}")
    
    def download_chromedriver_manually(self, thread_id):
        """🔄 ChromeDriver 수동 다운로드 및 설치"""
        try:
            import requests
            import zipfile
            from pathlib import Path
            
            self.emit_progress(f"📥 [스레드{thread_id+1}] ChromeDriver 수동 다운로드 시작...", thread_id)
            
            # Chrome 버전 확인
            chrome_version = None
            try:
                chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
                if os.path.exists(chrome_path):
                    version_result = subprocess.run([chrome_path, '--version'], 
                                                  capture_output=True, timeout=5, text=True)
                    if version_result.returncode == 0:
                        version_output = version_result.stdout.strip()
                        # "Google Chrome 120.0.6099.129" 형태에서 주 버전만 추출
                        import re
                        version_match = re.search(r'(\d+)\.\d+\.\d+\.\d+', version_output)
                        if version_match:
                            chrome_version = version_match.group(1)
            except:
                pass
            
            if not chrome_version:
                # 기본값 사용 (최신 안정 버전)
                chrome_version = "120"  # 2024년 기준 안정 버전
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] Chrome 버전 감지 실패, 기본값 사용: {chrome_version}", thread_id)
            else:
                self.emit_progress(f"✅ [스레드{thread_id+1}] Chrome 버전 감지: {chrome_version}", thread_id)
            
            # ChromeDriver 다운로드 URL 생성
            download_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{chrome_version}"
            
            try:
                # 최신 버전 번호 가져오기
                response = requests.get(download_url, timeout=10)
                if response.status_code == 200:
                    latest_version = response.text.strip()
                    
                    # ChromeDriver zip 파일 다운로드
                    driver_url = f"https://chromedriver.storage.googleapis.com/{latest_version}/chromedriver_win32.zip"
                    
                    # 임시 폴더에 다운로드
                    download_dir = Path(tempfile.gettempdir()) / f"chromedriver_manual_{thread_id}"
                    download_dir.mkdir(exist_ok=True)
                    
                    zip_path = download_dir / "chromedriver.zip"
                    
                    # 파일 다운로드
                    with requests.get(driver_url, timeout=30, stream=True) as r:
                        r.raise_for_status()
                        with open(zip_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    
                    # 압축 해제
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(download_dir)
                    
                    # chromedriver.exe 경로
                    chromedriver_exe = download_dir / "chromedriver.exe"
                    
                    if chromedriver_exe.exists():
                        # 실행 테스트
                        test_result = subprocess.run([str(chromedriver_exe), '--version'], 
                                                   capture_output=True, timeout=5, text=True)
                        if test_result.returncode == 0:
                            service = Service(str(chromedriver_exe))
                            self.emit_progress(f"✅ [스레드{thread_id+1}] 수동 다운로드 성공: {latest_version}", thread_id)
                            return service
                        else:
                            raise Exception("다운로드된 ChromeDriver 실행 테스트 실패")
                    else:
                        raise Exception("압축 해제 후 chromedriver.exe를 찾을 수 없음")
                        
                else:
                    raise Exception(f"버전 정보 다운로드 실패: HTTP {response.status_code}")
                    
            except Exception as download_error:
                self.emit_progress(f"❌ [스레드{thread_id+1}] 수동 다운로드 실패: {download_error}", thread_id)
                raise Exception(f"ChromeDriver 수동 다운로드 실패: {download_error}")
                
        except Exception as e:
            self.emit_progress(f"❌ [스레드{thread_id+1}] ChromeDriver 수동 설치 실패: {e}", thread_id)
            raise Exception(f"ChromeDriver 수동 설치 실패: {e}")

    def create_chrome_driver(self, account_type, account_id=None, thread_id=None, max_retries=5):
        """🆕 개선된 Chrome 드라이버 생성 (스레드 안전성 강화)"""
        # 🛑 작업이 중지된 경우 새로운 드라이버 생성 차단
        if not self.is_running:
            raise Exception("작업이 중지되어 새로운 드라이버를 생성할 수 없습니다")
        
        # thread_id가 명시적으로 전달되지 않으면 현재 스레드에서 추출
        if thread_id is None:
            thread_name = threading.current_thread().name
            thread_id = 0
            if 'Thread-' in thread_name:
                try:
                    thread_id = int(thread_name.split('-')[1]) - 1  # 0부터 시작하도록
                except:
                    thread_id = 0
        
        # 🔒 드라이버 생성 전 기존 프로세스 정리
        self.cleanup_dead_chrome_processes(thread_id)
        
        for attempt in range(max_retries):
            driver = None
            service = None
            user_data_dir = None
            
            try:
                # 재시도 시 대기 시간 증가 (더 보수적으로)
                if attempt > 0:
                    wait_time = attempt * 10  # 10초, 20초, 30초, 40초
                    self.emit_progress(f"🔄 [스레드{thread_id+1}] 드라이버 생성 재시도 {attempt+1}/{max_retries} - {wait_time}초 대기", thread_id)
                    time.sleep(wait_time)
                    
                    # 재시도 전 모든 Chrome 프로세스 강제 정리 (더 강력하게)
                    self.force_cleanup_all_chrome_processes()
                    time.sleep(3)  # 정리 후 추가 대기
                
                # 쓰레드별 고유한 임시 폴더 (더 안전한 생성)
                timestamp = int(time.time() * 1000)
                random_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
                user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome_t{thread_id}_{account_type}_{timestamp}_{random_id}")
                
                # 기존 디렉토리가 있으면 삭제
                if os.path.exists(user_data_dir):
                    try:
                        import shutil
                        shutil.rmtree(user_data_dir, ignore_errors=True)
                    except:
                        pass
                
                # 디렉토리 생성
                os.makedirs(user_data_dir, exist_ok=True)
                
                chrome_options = webdriver.ChromeOptions()
                
                # 🌐 Chrome 브라우저 사용 설정
                chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
                if os.path.exists(chrome_path):
                    chrome_options.binary_location = chrome_path
                
                # 🔧 렌더러 연결 실패 방지용 안정화 옵션
                chrome_options.add_argument("--incognito")  # 시크릿 모드 유지
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-web-security")
                chrome_options.add_argument("--disable-features=VizDisplayCompositor")
                chrome_options.add_argument("--disable-ipc-flooding-protection")
                chrome_options.add_argument("--max_old_space_size=4096")  # 메모리 제한
                chrome_options.add_argument("--disable-background-timer-throttling")
                chrome_options.add_argument("--disable-renderer-backgrounding")
                chrome_options.add_argument("--disable-backgrounding-occluded-windows")
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                # 쓰레드별 고유 포트 할당 (포트 충돌 방지 강화)
                # account_type과 account_id를 포함한 고유 포트 생성
                type_offset = 100 if account_type == 'comment' else 0
                account_hash = hash(account_id) % 50 if account_id else 0
                debug_port = 9222 + (thread_id * 200) + type_offset + account_hash + (attempt * 2)
                chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
                
                # 프록시 설정 (스레드별 전용 프록시 사용)
                thread_proxies = self.get_thread_proxies(thread_id, account_type)
                
                selected_proxy = None
                if thread_proxies and account_id:
                    # 스레드 전용 프록시에서 계정별 고정 프록시 선택
                    selected_proxy = self.get_fixed_proxy_for_account(account_id, thread_proxies)
                    chrome_options.add_argument(f'--proxy-server={selected_proxy}')
                    self.emit_progress(f"🌐 [스레드{thread_id+1}] 전용 프록시: {account_id} → {selected_proxy} ({account_type}용)", thread_id)
                elif thread_proxies:
                    # account_id가 없으면 스레드 전용 프록시에서 랜덤 선택
                    selected_proxy = random.choice(thread_proxies)
                    chrome_options.add_argument(f'--proxy-server={selected_proxy}')
                    self.emit_progress(f"🌐 [스레드{thread_id+1}] 랜덤 프록시: {selected_proxy} ({account_type}용)", thread_id)
                else:
                    self.emit_progress(f"🌐 [스레드{thread_id+1}] 프록시 없음: 직접 연결 ({account_type}용)", thread_id)
                
                # 🔧 개선된 Service 생성 (WinError 193 해결)
                service = None
                chromedriver_path = None
                
                # 1단계: ChromeDriverManager로 시도
                try:
                    chromedriver_path = ChromeDriverManager().install()
                    
                    # 다운로드된 파일이 실제로 실행 가능한지 검증
                    if os.path.exists(chromedriver_path) and os.path.getsize(chromedriver_path) > 1000:
                        # 간단한 실행 테스트
                        test_result = subprocess.run([chromedriver_path, '--version'], 
                                                   capture_output=True, timeout=5, text=True)
                        if test_result.returncode == 0:
                            service = Service(chromedriver_path)
                            service.log_level = 'ERROR'
                            self.emit_progress(f"✅ [스레드{thread_id+1}] ChromeDriverManager 성공: {chromedriver_path}", thread_id)
                        else:
                            raise Exception(f"ChromeDriver 실행 테스트 실패: {test_result.stderr}")
                    else:
                        raise Exception("다운로드된 ChromeDriver 파일이 손상됨")
                        
                except Exception as service_error:
                    self.emit_progress(f"⚠️ [스레드{thread_id+1}] ChromeDriverManager 실패: {service_error}", thread_id)
                    service = None
                
                # 2단계: 시스템 PATH에서 찾기
                if service is None:
                    try:
                        # 시스템 PATH에 있는 chromedriver 사용
                        test_result = subprocess.run(['chromedriver', '--version'], 
                                                   capture_output=True, timeout=5, text=True)
                        if test_result.returncode == 0:
                            service = Service()  # 기본 경로 사용
                            self.emit_progress(f"✅ [스레드{thread_id+1}] 시스템 PATH ChromeDriver 사용", thread_id)
                        else:
                            raise Exception("시스템 PATH ChromeDriver 실행 실패")
                    except Exception as path_error:
                        self.emit_progress(f"⚠️ [스레드{thread_id+1}] 시스템 PATH ChromeDriver 실패: {path_error}", thread_id)
                
                # 3단계: 수동 경로들 시도
                if service is None:
                    manual_paths = [
                        "C:/chromedriver.exe",
                        "C:/Program Files/Google/Chrome/Application/chromedriver.exe",
                        "C:/Windows/chromedriver.exe",
                        "./chromedriver.exe"
                    ]
                    
                    for manual_path in manual_paths:
                        try:
                            if os.path.exists(manual_path):
                                test_result = subprocess.run([manual_path, '--version'], 
                                                           capture_output=True, timeout=5, text=True)
                                if test_result.returncode == 0:
                                    service = Service(manual_path)
                                    self.emit_progress(f"✅ [스레드{thread_id+1}] 수동 경로 ChromeDriver 사용: {manual_path}", thread_id)
                                    break
                        except:
                            continue
                
                # 4단계: ChromeDriver 캐시 정리 후 재시도
                if service is None and attempt == 0:
                    self.emit_progress(f"🔧 [스레드{thread_id+1}] ChromeDriver 캐시 정리 후 재시도...", thread_id)
                    self.fix_chromedriver_cache()
                    
                    # 캐시 정리 후 ChromeDriverManager 재시도
                    try:
                        chromedriver_path = ChromeDriverManager().install()
                        if os.path.exists(chromedriver_path) and os.path.getsize(chromedriver_path) > 1000:
                            test_result = subprocess.run([chromedriver_path, '--version'], 
                                                       capture_output=True, timeout=5, text=True)
                            if test_result.returncode == 0:
                                service = Service(chromedriver_path)
                                service.log_level = 'ERROR'
                                self.emit_progress(f"✅ [스레드{thread_id+1}] 캐시 정리 후 성공", thread_id)
                    except:
                        pass
                
                # 5단계: 수동 다운로드 시도
                if service is None and attempt <= 1:
                    try:
                        service = self.download_chromedriver_manually(thread_id)
                    except:
                        pass
                
                # 6단계: 모든 방법 실패 시 예외 발생
                if service is None:
                    raise Exception("모든 ChromeDriver 복구 방법 실패 - 수동으로 chromedriver.exe를 설치해주세요")
                
                # 🔧 드라이버 생성 전 짧은 대기 (프로세스 충돌 방지)
                time.sleep(random.uniform(0.5, 1.5))
                
                # 🔧 드라이버 생성 시 타임아웃 설정
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
                # 드라이버 생성 후 즉시 상태 확인
                try:
                    driver.get("about:blank")  # 빈 페이지로 테스트
                    self.emit_progress(f"✅ [스레드{thread_id+1}] 드라이버 상태 확인 완료", thread_id)
                except Exception as test_error:
                    raise Exception(f"드라이버 상태 테스트 실패: {test_error}")
                
                # 자동화 탐지 우회
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # 🖥️ 창 위치 및 크기 설정 (더 안전한 방식)
                try:
                    self.set_window_position_safe(driver, thread_id)
                except Exception as window_error:
                    self.emit_progress(f"⚠️ [스레드{thread_id+1}] 창 위치 설정 실패: {window_error}", thread_id)
                
                # 쓰레드별 크롬 프로세스 ID 추적
                if hasattr(service, 'process') and service.process:
                    chrome_pid = service.process.pid
                    with self.drivers_lock:
                        if thread_id not in self.thread_chrome_pids:
                            self.thread_chrome_pids[thread_id] = []
                        self.thread_chrome_pids[thread_id].append(chrome_pid)
                    self.emit_progress(f"🆔 [스레드{thread_id+1}] 크롬 PID: {chrome_pid} 추적 시작", thread_id)
                
                self.emit_progress(f"✅ [스레드{thread_id+1}] 드라이버 생성 성공 (시도 {attempt + 1}/{max_retries})", thread_id)
                return driver
                
            except Exception as e:
                error_msg = str(e)
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] 드라이버 생성 실패 (시도 {attempt + 1}/{max_retries}): {error_msg}", thread_id)
                
                # 🔧 실패 시 정리 작업
                try:
                    if driver:
                        driver.quit()
                except:
                    pass
                    
                try:
                    if service and hasattr(service, 'process') and service.process:
                        service.process.terminate()
                except:
                    pass
                    
                try:
                    if user_data_dir and os.path.exists(user_data_dir):
                        shutil.rmtree(user_data_dir, ignore_errors=True)
                except:
                    pass
                
                # 🛠️ 특정 오류에 대한 추가 대응
                if "Failed to establish a new connection" in error_msg:
                    self.emit_progress(f"🔌 [스레드{thread_id+1}] WebDriver 연결 실패 - 포트 정리 중...", thread_id)
                elif "SessionNotCreatedException" in error_msg:
                    self.emit_progress(f"🔄 [스레드{thread_id+1}] 세션 생성 실패 - Chrome 버전 확인 중...", thread_id)
                elif "WebDriverException" in error_msg:
                    self.emit_progress(f"🚫 [스레드{thread_id+1}] WebDriver 예외 - 프로세스 정리 중...", thread_id)
                elif "unable to connect to renderer" in error_msg:
                    self.emit_progress(f"🎨 [스레드{thread_id+1}] 렌더러 연결 실패 - Chrome 프로세스 재시작 필요...", thread_id)
                
                if attempt == max_retries - 1:
                    self.emit_progress(f"❌ [스레드{thread_id+1}] 드라이버 생성 최종 실패: {error_msg}", thread_id)
                    raise Exception(f"드라이버 생성 실패: {error_msg}")
        
        raise Exception(f"[스레드{thread_id+1}] 드라이버 생성 최대 재시도 횟수 초과")
    
    def cleanup_dead_chrome_processes(self, thread_id):
        """🎯 해당 스레드의 죽은 Chrome 프로세스만 선택적 정리"""
        try:
            import psutil
            cleaned_count = 0
            protected_count = 0
            
            # 해당 스레드가 추적 중인 PID들 확인
            thread_pids = []
            with self.drivers_lock:
                if thread_id in self.thread_chrome_pids:
                    thread_pids = self.thread_chrome_pids[thread_id].copy()
            
            # 추적된 PID 중 죽은 프로세스만 정리
            for pid in thread_pids:
                try:
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        if process.status() in ['zombie', 'dead']:
                            # 명령줄 재검증 (안전성 확보)
                            cmdline = ' '.join(process.cmdline()) if process.cmdline() else ''
                            if f"chrome_t{thread_id}_" in cmdline:
                                process.terminate()
                                cleaned_count += 1
                                self.emit_progress(f"💀 [스레드{thread_id+1}] 죽은 Chrome PID {pid} 정리", thread_id)
                            else:
                                protected_count += 1
                    else:
                        # 이미 종료된 PID는 추적 목록에서 제거
                        with self.drivers_lock:
                            if thread_id in self.thread_chrome_pids and pid in self.thread_chrome_pids[thread_id]:
                                self.thread_chrome_pids[thread_id].remove(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # 이미 종료된 프로세스는 추적 목록에서 제거
                    with self.drivers_lock:
                        if thread_id in self.thread_chrome_pids and pid in self.thread_chrome_pids[thread_id]:
                            self.thread_chrome_pids[thread_id].remove(pid)
                except:
                    pass
            
            # 전체 시스템의 좀비 프로세스 중 자동화 관련만 정리
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cmdline']):
                try:
                    if ('chrome' in proc.info['name'].lower() and 
                        proc.info['status'] in ['zombie', 'dead']):
                        
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        # 자동화 프로그램이 생성한 좀비 프로세스만 정리
                        if any(identifier in cmdline for identifier in [
                            f'chrome_t{thread_id}_', 'AutomationControlled', '--incognito'
                        ]):
                            proc.terminate()
                            cleaned_count += 1
                        else:
                            protected_count += 1
                except:
                    pass
            
            if cleaned_count > 0:
                self.emit_progress(f"🧹 [스레드{thread_id+1}] 죽은 Chrome 프로세스 {cleaned_count}개 정리 (사용자 Chrome {protected_count}개 보호)", thread_id)
                
        except Exception as e:
            self.emit_progress(f"⚠️ [스레드{thread_id+1}] 죽은 프로세스 정리 실패: {e}", thread_id)
    
    def set_window_position_safe(self, driver, thread_id):
        """🖥️ 안전한 창 위치 설정"""
        try:
            # 화면 정보 가져오기
            root = tk.Tk()
            root.withdraw()  # 창을 숨김
            
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            
            # 창 크기 고정 설정
            window_width = 800
            window_height = 1400
            
            # 스레드별 위치 계산 (안전한 배치)
            cols = 2
            rows = 3
            position_index = thread_id % 6  # 최대 6개 창만 고려
            
            row = position_index // cols
            col = position_index % cols
            
            # 여백을 고려한 배치 (화면 경계 내에서만)
            margin = 50
            spacing_x = 30
            spacing_y = 80
            
            x = margin + (col * (window_width + spacing_x))
            y = margin + (row * (window_height + spacing_y))
            
            # 스레드3은 오른쪽 모니터로 이동 (듀얼 모니터 환경)
            if thread_id == 2:  # thread_id는 0부터 시작하므로 스레드3은 2
                x = 2030  # 오른쪽 모니터 위치 조정
                y = 10    # 상단 여백 10px
                self.emit_progress(f"🖥️ [스레드{thread_id+1}] 오른쪽 모니터로 이동!", thread_id)
            
            # 화면 경계 최종 체크 (스레드3 제외)
            if thread_id != 2:
                if x + window_width > screen_width:
                    x = screen_width - window_width - margin
                if y + window_height > screen_height:
                    y = screen_height - window_height - margin
            
            # 음수 좌표 방지
            x = max(0, x)
            y = max(0, y)
            
            # 창 위치 및 크기 설정
            driver.set_window_position(x, y)
            driver.set_window_size(window_width, window_height)
            
            self.emit_progress(f"🖥️ [스레드{thread_id+1}] 창 위치 설정: ({x}, {y}) 크기: {window_width}x{window_height}", thread_id)
            
        except Exception as window_error:
            self.emit_progress(f"⚠️ [스레드{thread_id+1}] 창 위치 설정 실패: {window_error}", thread_id)

    
    def find_parent_comment(self, driver, comment, written_comments):
        """부모 댓글 찾기 (eoeotrmf.py 방식 - parent_idx 기반)"""
        try:
            parent_idx = comment.get('parent_idx')
            
            # parent_idx가 없으면 최근 댓글을 부모로 설정
            if parent_idx is None:
                # 가능한 댓글 컨테이너 셀렉터들
                comment_selectors = [
                    '.comment_list .comment_item',
                    '.comment_list li', 
                    '.comment_item',
                    'div[class*="comment"]',
                    'li[class*="comment"]'
                ]
                
                parent_comment = None
                for selector in comment_selectors:
                    try:
                        # 모든 댓글 요소 찾기
                        comment_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if comment_elements:
                            # 가장 마지막 댓글을 부모로 설정
                            parent_comment = comment_elements[-1]
                            self.signals.progress.emit(f"✅ 부모 댓글 찾기 성공 (최근): {selector} ({len(comment_elements)}개 중 마지막)")
                            break
                    except:
                        continue
                
                return parent_comment
            
            # parent_idx가 있으면 실제 작성된 댓글에서 찾기
            if parent_idx < len(written_comments):
                # written_comments에서 parent_idx에 해당하는 댓글의 순서 계산
                target_order = parent_idx + 1  # 1-based index
                
                comment_selectors = [
                    '.comment_list .comment_item',
                    '.comment_list li',
                    '.comment_item'
                ]
                
                for selector in comment_selectors:
                    try:
                        comment_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if len(comment_elements) >= target_order:
                            parent_comment = comment_elements[target_order - 1]  # 0-based index
                            self.signals.progress.emit(f"✅ 부모 댓글 찾기 성공 (정확한 부모): {selector} {target_order}번째")
                            return parent_comment
                    except:
                        continue
            
            # 못 찾으면 최근 댓글을 부모로 설정
            comment_selectors = [
                '.comment_list .comment_item',
                '.comment_list li',
                '.comment_item'
            ]
            
            for selector in comment_selectors:
                try:
                    comment_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if comment_elements:
                        parent_comment = comment_elements[-1]
                        self.signals.progress.emit(f"✅ 부모 댓글 찾기 성공 (대체): {selector} 마지막")
                        return parent_comment
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.signals.progress.emit(f"❌ 부모 댓글 찾기 오류: {str(e)}")
            return None
    
    def extract_new_reply_url(self, driver, thread_id):
        """🔗 방금 작성한 답글의 새로운 URL 추출 (연쇄 시스템용)"""
        try:
            # 페이지 업데이트 대기 (답글 작성 후 DOM 변경 시간)
            time.sleep(3)
            
            # 방법1만 사용: 가장 최신 답글 버튼에서 URL 추출 (최대 3회 시도)
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    self.emit_progress(f"🔗 [연쇄시스템] URL 추출 시도 {attempt + 1}/{max_attempts}", thread_id)
                    
                    # 답글 목록에서 마지막(최신) 답글의 답글 버튼 찾기
                    latest_reply_buttons = driver.find_elements(By.CSS_SELECTOR, 
                        "a[href*='/reply'], button[onclick*='reply'], .reply_btn, .btn_reply")
                    
                    if latest_reply_buttons:
                        # 마지막 답글 버튼에서 URL 얻기
                        latest_btn = latest_reply_buttons[-1]  # 가장 최신
                        href = latest_btn.get_attribute('href')
                        
                        if href and 'reply' in href:
                            self.emit_progress(f"✅ [연쇄시스템] URL 추출 성공 (시도 {attempt + 1}): {href[:50]}...", thread_id)
                            return href  # 즉시 반환 (2번째, 3번째 시도 안 함)
                    
                    # 첫 번째, 두 번째 시도 실패 시 충분한 대기 후 재시도
                    if attempt < max_attempts - 1:
                        wait_time = 5  # 5초 대기
                        self.emit_progress(f"⏳ [연쇄시스템] {wait_time}초 대기 후 재시도...", thread_id)
                        time.sleep(wait_time)
                        
                except Exception as e:
                    self.emit_progress(f"⚠️ [연쇄시스템] 시도 {attempt + 1} 실패: {str(e)}", thread_id)
                    
                    # 첫 번째, 두 번째 시도 실패 시 충분한 대기 후 재시도
                    if attempt < max_attempts - 1:
                        wait_time = 5  # 5초 대기
                        self.emit_progress(f"⏳ [연쇄시스템] {wait_time}초 대기 후 재시도...", thread_id)
                        time.sleep(wait_time)
            
            # 모든 시도 실패
            self.emit_progress(f"❌ [연쇄시스템] 모든 시도 실패 ({max_attempts}회)", thread_id)
            return None
            
        except Exception as e:
            self.emit_progress(f"❌ [연쇄시스템] URL 추출 중 오류: {str(e)}", thread_id)
            return None
    
    def get_spare_account_for_replacement(self, thread_id):
        """🆘 여분아이디 교체용 계정 가져오기 (사용 횟수 제한 적용)"""
        try:
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'spare_accounts'):
                spare_accounts = self.main_window.spare_accounts
                account_limit = getattr(self, 'config', {}).get('account_limit', 3) if hasattr(self, 'config') else 3
                
                # 사용 가능한 여분아이디 찾기 (차단되지 않고, 사용 제한에 도달하지 않은 것)
                for spare_account in spare_accounts:
                    spare_id = spare_account[0]
                    
                    # 이미 차단된 계정이 아닌지 확인
                    if spare_id not in self.main_window.blocked_reply_accounts:
                        # 🔧 사용 횟수 확인 (account_limit까지 사용 가능)
                        current_usage = self.main_window.get_account_usage_count(spare_id)
                        
                        if current_usage < account_limit:
                            self.emit_progress(f"🎯 [스레드{thread_id+1}] 여분아이디 할당: {spare_id} (사용 {current_usage+1}/{account_limit})", thread_id)
                            return spare_account
                        else:
                            # 사용 제한에 도달한 여분 계정은 제거
                            spare_accounts.remove(spare_account)
                            self.main_window.update_spare_table()
                            self.emit_progress(f"🚫 [스레드{thread_id+1}] 여분아이디 {spare_id} 사용 제한 도달 ({current_usage}/{account_limit}) - 제거", thread_id)
                            continue
                
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] 사용 가능한 여분아이디가 없습니다", thread_id)
                return None
            else:
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] 여분아이디 시스템이 초기화되지 않았습니다", thread_id)
                return None
                
        except Exception as e:
            self.emit_progress(f"❌ [스레드{thread_id+1}] 여분아이디 가져오기 실패: {str(e)}", thread_id)
            return None

    def try_login_with_spare_account(self, thread_id, spare_account):
        """🔄 여분아이디로 로그인 시도"""
        try:
            self.emit_progress(f"🔑 [스레드{thread_id+1}] 여분아이디 로그인 시도: {spare_account[0]}", thread_id)
            
            # 여분아이디용 새 드라이버 생성
            driver = self.get_driver(thread_id, 'reply', spare_account[0])
            if driver is None:
                self.emit_progress(f"🛑 [스레드{thread_id+1}] 여분아이디 드라이버 생성 실패: {spare_account[0]}", thread_id)
                return None
            
            # 로그인 시도
            login_result = self.login_naver(driver, spare_account[0], spare_account[1], thread_id)
            
            if login_result[0]:  # 로그인 성공
                self.emit_progress(f"✅ [스레드{thread_id+1}] 여분아이디 로그인 성공: {spare_account[0]}", thread_id)
                return True
            else:
                # 여분아이디도 실패하면 차단 목록에 추가
                failure_reason = login_result[1]
                self.emit_progress(f"❌ [스레드{thread_id+1}] 여분아이디 로그인 실패: {spare_account[0]} - {failure_reason}", thread_id)
                
                # 여분아이디도 차단 대상이면 차단 목록 추가
                if any(keyword in failure_reason for keyword in 
                       ["아이디 보호", "계정 잠금", "존재하지 않는 아이디", "보안 제한"]):
                    self.main_window.mark_reply_account_blocked(spare_account[0])
                    self.emit_progress(f"🚫 [스레드{thread_id+1}] 여분아이디도 차단 목록 추가: {spare_account[0]}", thread_id)
                
                # 실패한 드라이버 정리
                self.safe_cleanup_thread_drivers(thread_id)
                return False
                
        except Exception as e:
            self.emit_progress(f"❌ [스레드{thread_id+1}] 여분아이디 로그인 중 오류: {str(e)}", thread_id)
            self.safe_cleanup_thread_drivers(thread_id)
            return False

    def get_current_ip(self, driver):
        """현재 사용 중인 IP 주소 확인"""
        try:
            current_url = driver.current_url
            driver.get("https://httpbin.org/ip")
            self.smart_sleep(2, "IP 확인 페이지 로딩")
            
            # JSON 응답에서 IP 추출
            page_source = driver.page_source
            if '"origin"' in page_source:
                import json
                try:
                    # JSON 파싱
                    start = page_source.find('{')
                    end = page_source.rfind('}') + 1
                    json_data = json.loads(page_source[start:end])
                    ip = json_data.get('origin', 'Unknown')
                    
                    # 원래 페이지로 돌아가기
                    if current_url and current_url != "https://httpbin.org/ip":
                        driver.get(current_url)
                        self.smart_sleep(1, "원래 페이지로 복귀")
                    
                    return ip
                except:
                    pass
            
            # 원래 페이지로 돌아가기
            if current_url and current_url != "https://httpbin.org/ip":
                driver.get(current_url)
                self.smart_sleep(1, "원래 페이지로 복귀")
            
            return "IP 확인 실패"
        except Exception as e:
            return f"IP 확인 오류: {str(e)}"
    
    def login_naver(self, driver, login_id, password, thread_id=None):
        """네이버 로그인"""
        try:
            self.emit_progress("🔐 네이버 로그인을 시도합니다...", thread_id)
            driver.get('https://nid.naver.com/nidlogin.login')
            
            # 페이지 로딩 대기
            if not self.wait_for_page_load(driver):
                self.emit_progress("⚠️ 로그인 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
            
            self.smart_sleep(2, "로그인 페이지 로딩 후 대기")

            # IP보안 스위치 OFF 처리
            try:
                ip_switch = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, 'span.switch_on[role="checkbox"][aria-checked="true"]',
                    max_wait=5, element_name="IP보안 스위치"
                )
                if self.safe_click_with_retry(driver, ip_switch, element_name="IP보안 스위치"):
                    self.emit_progress("🛡️ IP보안 스위치 OFF 완료", thread_id)
                self.smart_sleep(1, "IP보안 스위치 처리 후 대기")
            except Exception:
                self.emit_progress("ℹ️ IP보안 스위치가 없거나 이미 OFF 상태", thread_id)

            # 아이디 입력 (쓰레드 안전한 클립보드 사용)
            id_input = self.wait_for_element_with_retry(
                driver, By.ID, "id",
                element_name="아이디 입력 필드"
            )
            with self.clipboard_lock:
                pyperclip.copy(login_id)
                id_input.click()
                self.smart_sleep(0.5, "아이디 입력 전 대기")
                id_input.send_keys(Keys.CONTROL + 'a')
                id_input.send_keys(Keys.CONTROL + 'v')
            self.smart_sleep(1, "아이디 입력 후 대기")

            # 비밀번호 입력 (쓰레드 안전한 클립보드 사용)
            pw_input = self.wait_for_element_with_retry(
                driver, By.ID, "pw",
                element_name="비밀번호 입력 필드"
            )
            with self.clipboard_lock:
                pyperclip.copy(password)
                pw_input.click()
                self.smart_sleep(0.5, "비밀번호 입력 전 대기")
                pw_input.send_keys(Keys.CONTROL + 'a')
                pw_input.send_keys(Keys.CONTROL + 'v')
            self.smart_sleep(1, "비밀번호 입력 후 대기")

            # 로그인 버튼 클릭
            login_btn = self.wait_for_element_with_retry(
                driver, By.ID, "log.login",
                element_name="로그인 버튼"
            )
            
            if not self.safe_click_with_retry(driver, login_btn, element_name="로그인 버튼"):
                raise Exception("로그인 버튼 클릭 실패")
            
            self.smart_sleep(10, "로그인 처리 대기")

            # 아이디 보호 메시지 확인
            try:
                warning_element = driver.find_element(By.CSS_SELECTOR, ".warning_title")
                if warning_element and "아이디를 보호하고 있습니다" in warning_element.text:
                    self.emit_progress(f"🚫 계정 {login_id}: 네이버 아이디 보호 기능 발동 - 사용 불가", thread_id)
                    return False, "아이디 보호 기능 발동"
            except:
                pass  # 보호 메시지가 없으면 계속 진행
            
            # 🔧 로그인 성공/실패 확인 (순서 개선: 에러 메시지 먼저 체크)
            
            # 1️⃣ 먼저 에러 메시지 체크 (가장 우선순위)
            failure_reason = self.check_login_failure_reason_early(driver)
            if failure_reason:
                self.emit_progress(f"❌ 계정 {login_id} 로그인 실패: {failure_reason}", thread_id)
                return False, failure_reason
            
            # 2️⃣ 에러가 없으면 URL로 성공 여부 확인
            current_url = driver.current_url
            if "naver.com" in current_url:
                self.emit_progress("✅ 네이버 로그인 성공!", thread_id)
                
                # 사용 중인 IP 확인 및 로그 출력 (비활성화)
                # current_ip = self.get_current_ip(driver)
                # self.emit_progress(f"🌍 계정-IP 매핑: {login_id} → {current_ip}", thread_id)
                
                return True, "로그인 성공"
            else:
                # 3️⃣ URL이 여전히 로그인 페이지면 추가 실패 원인 확인
                detailed_failure = self.check_login_failure_reason(driver)
                self.emit_progress(f"❌ 계정 {login_id} 로그인 실패: {detailed_failure}", thread_id)
                return False, detailed_failure
                
        except Exception as e:
            self.emit_progress(f"로그인 중 오류: {str(e)}", thread_id)
            return False, f"로그인 중 오류: {str(e)}"
    
    def disable_comment_permission_final(self, thread_id, reply_url, reply_account):
        """4단계: 답글 계정으로 댓글 허용 설정 해제"""
        driver = None
        try:
            self.emit_progress("🔄 답글 계정으로 재로그인 중...", thread_id)
            
            # 다른 드라이버와 충돌 방지를 위한 대기
            time.sleep(2)
            
            # 답글 계정으로 새 드라이버 생성 및 로그인
            driver = self.get_driver(thread_id, 'reply', reply_account[0])
            if driver is None:
                self.emit_progress(f"🛑 [스레드{thread_id+1}] 댓글 허용 해제용 드라이버 생성 실패: {reply_account[0]}", thread_id)
                return False
            
            login_success, login_msg = self.login_naver(driver, reply_account[0], reply_account[1], thread_id)
            
            if not login_success:
                raise Exception(f"답글 계정 재로그인 실패: {login_msg}")
            
            self.emit_progress("✅ 답글 계정 재로그인 성공", thread_id)
            
            # 답글 URL에서 게시글 URL 추출
            if '#comment' in reply_url:
                article_url = reply_url.split('#comment')[0]
            elif '/comments/' in reply_url:
                article_url = reply_url.split('/comments/')[0]
            else:
                article_url = reply_url
            
            self.emit_progress(f"📍 게시글로 이동: {article_url}", thread_id)
            driver.get(article_url)
            self.wait_for_page_load(driver)
            self.smart_sleep(2, "게시글 페이지 로딩 대기")
            
            # 📌 답글 버튼과 동일하게 iframe 진입 시도 (네이버 카페 구조)
            try:
                iframe = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, "iframe#cafe_main", 
                    max_wait=5, element_name="iframe#cafe_main"
                )
                driver.switch_to.frame(iframe)
                self.emit_progress("🔄 iframe(cafe_main) 내부로 진입 - 수정 버튼 찾기 준비", thread_id)
                self.smart_sleep(1, "iframe 진입 후 안정화 대기")
            except Exception as e:
                self.emit_progress(f"ℹ️ iframe(cafe_main) 진입 실패 또는 불필요: {str(e)}", thread_id)
                # iframe이 없어도 계속 진행
            
            # 수정 버튼 찾기 및 클릭
            self.emit_progress("🔍 수정 버튼 찾는 중... (iframe 내부)", thread_id)
            
            edit_btn = self.wait_for_element_with_retry(
                driver, By.CSS_SELECTOR, 
                '#app > div > div > div.ArticleBottomBtns > div.left_area > a:nth-child(3)',
                max_wait=25, element_name="수정 버튼"
            )
            
            # 수정 버튼 클릭 전 탭 수 저장
            original_tabs = driver.window_handles
            if not self.safe_click_with_retry(driver, edit_btn, element_name="수정 버튼"):
                raise Exception("수정 버튼 클릭 실패")
            
            # 새 탭 열릴 때까지 대기 (답글과 동일한 로직)
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: len(d.window_handles) > len(original_tabs)
                )
                new_tab = list(set(driver.window_handles) - set(original_tabs))[0]
                driver.switch_to.window(new_tab)
                self.emit_progress("🆕 수정 페이지 새 탭으로 전환 완료", thread_id)
                
                # 새 탭에서 페이지 로딩 완료까지 충분히 대기
                self.smart_sleep(3, "새 탭 초기 로딩 대기")
                
                # document.readyState 체크
                try:
                    WebDriverWait(driver, 20).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    self.emit_progress("✅ 수정 페이지 새 탭 로딩 완료", thread_id)
                except:
                    self.emit_progress("⚠️ 새 탭 페이지 로딩 시간 초과, 계속 진행합니다...", thread_id)
                
                # JavaScript 및 DOM 완전 로딩 대기
                self.smart_sleep(3, "새 탭 JavaScript 로딩 대기")
                
                # 페이지 상호작용 가능 상태 체크
                try:
                    driver.execute_script("return document.body !== null")
                    self.emit_progress("✅ 수정 페이지 새 탭 상호작용 준비 완료", thread_id)
                except:
                    self.emit_progress("⚠️ 새 탭 상호작용 준비 실패", thread_id)
                    
            except Exception as e:
                self.emit_progress(f"ℹ️ 새 탭 감지 실패 또는 새 탭이 열리지 않음: {e}", thread_id)
            
            self.emit_progress("✅ 수정 버튼 클릭 완료", thread_id)
            
            # 페이지 로딩 대기 (수정 페이지가 완전히 로드될 때까지)
            self.smart_sleep(2, "수정 페이지 초기 로딩 대기")
            
            # 📌 에디터 로딩 완료 대기 (답글 작성 시와 동일한 방식)
            try:
                self.emit_progress("⏳ 에디터 로딩 대기 중...", thread_id)
                # contenteditable 요소가 나타날 때까지 대기
                editor_element = self.wait_for_element_with_retry(
                    driver, By.CSS_SELECTOR, '[contenteditable="true"], div[role="textbox"], div[data-placeholder], iframe[id*="editor"], textarea[name="content"]',
                    max_wait=10, retry_count=5, element_name="에디터"
                )
                self.smart_sleep(3, "에디터 완전 로딩 대기")  # 추가 대기
                self.emit_progress("✅ 에디터 로딩 완료", thread_id)
                
                # 에디터가 준비되면 추가로 1초 대기 (안정화)
                self.smart_sleep(1, "에디터 안정화 대기")
            except Exception as e:
                self.emit_progress(f"⚠️ 에디터 로딩 대기 실패: {e}, 계속 진행", thread_id)
            
            # 댓글 비허용 설정 (체크박스가 나타날 때까지 대기)
            try:
                self.emit_progress("🔍 댓글 허용 체크박스 찾는 중...", thread_id)
                # 에디터가 이미 로드되었으므로 체크박스도 바로 있을 것임 - 대기 시간 단축
                comment_checkbox = self.wait_for_element_with_retry(
                    driver, By.ID, "coment",
                    max_wait=3, element_name="댓글 허용 체크박스"  # 10초에서 3초로 단축
                )
                
                if comment_checkbox.is_selected():
                    driver.execute_script("arguments[0].click();", comment_checkbox)
                    self.emit_progress("✅ 댓글 비허용 설정 완료", thread_id)
                    self.smart_sleep(1.5, "체크박스 클릭 후 대기")  # 안정성 개선
                else:
                    self.emit_progress("ℹ️ 댓글이 이미 비허용 상태입니다", thread_id)
            except Exception as e:
                self.emit_progress(f"⚠️ 댓글 설정 변경 실패: {str(e)}", thread_id)
                # 실패해도 계속 진행 (치명적이지 않음)
            
            # 저장 (답글 등록할 때와 같은 녹색 등록 버튼)
            self.emit_progress("💾 설정 저장 중...", thread_id)
            save_btn = self.wait_for_element_with_retry(
                driver, By.CSS_SELECTOR, 'a.BaseButton--skinGreen[role="button"]',
                max_wait=10, element_name="저장 버튼"
            )
            
            # 저장 전 현재 URL 저장
            before_save_url = driver.current_url
            
            # Alert 처리를 위한 저장 시도
            try:
                if not self.safe_click_with_retry(driver, save_btn, element_name="저장 버튼"):
                    raise Exception("저장 버튼 클릭 실패")
            except UnexpectedAlertPresentException as e:
                # Alert 처리
                try:
                    alert = driver.switch_to.alert
                    alert_text = alert.text
                    self.emit_progress(f"⚠️ Alert 감지: {alert_text}", thread_id)
                    
                    if "내용을 입력하세요" in alert_text:
                        # Alert 닫기
                        alert.accept()
                        self.emit_progress("❌ 본문 내용이 비어있음 - 댓글 차단 실패", thread_id)
                        raise Exception("본문 내용이 비어있어 저장할 수 없습니다")
                    else:
                        alert.accept()
                        raise Exception(f"예상치 못한 Alert: {alert_text}")
                except:
                    raise e
            
            # URL 변경 대기 (저장 완료 확인)
            self.emit_progress("⏳ 저장 처리 중... URL 변경 대기", thread_id)
            max_wait_time = 15  # 최대 15초 대기
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = driver.current_url
                if current_url != before_save_url:
                    self.emit_progress(f"✅ URL 변경 감지! 저장 완료 확인", thread_id)
                    break
                time.sleep(0.5)
            else:
                # 시간 초과 시 경고 메시지
                self.emit_progress("⚠️ URL 변경 감지 시간 초과 - 저장은 완료되었을 수 있음", thread_id)
            
            # 추가 안정화 대기
            self.smart_sleep(2, "저장 완료 후 안정화 대기")
            
            self.emit_progress("🎉 댓글 허용 설정 해제 전체 완료!", thread_id)
            
        except Exception as e:
            self.emit_progress(f"❌ 댓글 설정 해제 실패: {str(e)}", thread_id)
            raise e
        finally:
            # 댓글 설정용 드라이버만 개별 정리
            if driver:
                try:
                    driver.quit()
                    # 드라이버 딕셔너리에서도 제거
                    driver_key = f"{thread_id}_reply_{reply_account[0]}"
                    with self.drivers_lock:
                        if driver_key in self.drivers:
                            del self.drivers[driver_key]
                    self.emit_progress("🧹 댓글 설정용 브라우저 개별 종료", thread_id)
                except:
                    pass

    def logout_naver(self, driver):
        """네이버 로그아웃"""
        try:
            driver.get('https://nid.naver.com/nidlogin.logout')
            time.sleep(2)
        except:
            pass
    
    def stop(self):
        """🎯 작업 중지 - 자동화 전용 크롬 프로세스만 선택적 종료 (사용자 Chrome 보호)"""
        self.is_running = False
        
        # 사용자 Chrome 보호 모드 확인
        has_user_chrome = self.detect_user_chrome_processes()
        
        if has_user_chrome:
            self.signals.progress.emit("🛑 작업 중지 - 자동화 전용 Chrome만 선택적 종료 중... (사용자 Chrome 보호)")
        else:
            self.signals.progress.emit("🛑 작업 중지 - 자동화 Chrome 프로세스 정리 중...")
        
        try:
            # 1. 모든 드라이버 즉시 종료
            with self.drivers_lock:
                for driver_key, driver in list(self.drivers.items()):
                    try:
                        driver.quit()
                        self.signals.progress.emit(f"🚫 드라이버 종료: {driver_key}")
                    except:
                        pass
                self.drivers.clear()
            
            # 2. 추적된 자동화 크롬 프로세스만 종료
            killed_count = 0
            protected_count = 0
            
            with self.drivers_lock:
                for thread_id, pids in list(self.thread_chrome_pids.items()):
                    for pid in pids:
                        try:
                            import psutil
                            if psutil.pid_exists(pid):
                                process = psutil.Process(pid)
                                # 명령줄 검증으로 안전성 확보
                                cmdline = ' '.join(process.cmdline()) if process.cmdline() else ''
                                if any(identifier in cmdline for identifier in [
                                    f'chrome_t{thread_id}_', 'AutomationControlled', 'excludeSwitches'
                                ]):
                                    process.terminate()
                                    killed_count += 1
                                    self.signals.progress.emit(f"💀 자동화 Chrome PID {pid} 종료")
                                else:
                                    protected_count += 1
                        except:
                            pass
                self.thread_chrome_pids.clear()
            
            # 3. 사용자 Chrome이 있는 경우 선택적 정리만 수행
            if has_user_chrome:
                # 자동화 식별자가 있는 Chrome만 추가 정리
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if 'chrome' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                            
                            # 자동화 프로그램 식별자가 명확한 경우만 종료
                            is_automation = any(identifier in cmdline for identifier in [
                                'chrome_t', 'remote-debugging-port=922', 'AutomationControlled',
                                'excludeSwitches', 'useAutomationExtension=false'
                            ])
                            
                            if is_automation:
                                proc.terminate()
                                killed_count += 1
                            else:
                                protected_count += 1
                    except:
                        pass
                
                self.signals.progress.emit(f"✅ 선택적 작업 중지 완료 (자동화: {killed_count}개 종료, 사용자: {protected_count}개 보호)")
            else:
                # 사용자 Chrome이 없는 경우에만 전체 정리 (기존 방식)
                import psutil
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if 'chrome' in proc.info['name'].lower():
                            proc.terminate()
                            killed_count += 1
                    except:
                        pass
                
                self.signals.progress.emit(f"✅ 작업 중지 완료 - 자동화 Chrome {killed_count}개 정리됨")
            
        except Exception as e:
            self.signals.progress.emit(f"⚠️ 중지 중 오류: {str(e)}")
            
            # 🚨 오류 발생 시에만 최후 수단으로 taskkill 사용 (사용자에게 경고)
            if not has_user_chrome:
                try:
                    import os
                    os.system("taskkill /f /im chrome.exe >nul 2>&1")
                    os.system("taskkill /f /im chromedriver.exe >nul 2>&1")
                    self.signals.progress.emit("🚫 오류로 인한 taskkill 실행 (사용자 Chrome 없음 확인됨)")
                except:
                    pass
            else:
                self.signals.progress.emit("⚠️ 사용자 Chrome이 감지되어 taskkill 건너뜀 - 수동으로 정리해주세요")
    
    def cleanup(self):
        """정리"""
        for driver in self.drivers.values():
            try:
                driver.quit()
            except:
                pass
        self.drivers.clear()
    
    def solve_captcha_with_chatgpt(self, image_src, problem_text):
        """ChatGPT API를 사용한 캡차 해결"""
        try:
            # openai 모듈이 import되었는지 확인
            if openai is None:
                self.signals.progress.emit("❌ openai 패키지가 설치되지 않았습니다.")
                return None
                
            api_key = app_config.get('gpt_api_key')
            if not api_key:
                return None
            
            # OpenAI 클라이언트 초기화
            client = openai.OpenAI(api_key=api_key)
            
            # 이미지 데이터 가져오기
            if image_src.startswith('data:image'):
                # data URL인 경우
                image_data = image_src.split(',')[1]
            else:
                # 일반 URL인 경우
                response = requests.get(image_src)
                image_data = base64.b64encode(response.content).decode('utf-8')
            
            # ChatGPT API 호출
            response = client.chat.completions.create(
                model=app_config.get('gpt_model'),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""다음은 네이버 로그인 캡차 이미지입니다.
문제: {problem_text}

이미지를 분석하고 요구하는 답을 정확히 찾아주세요. 
- 숫자나 문자를 찾는 문제라면 보이는 그대로 정확히 입력해주세요.
- 계산 문제라면 정확한 답만 숫자로 입력해주세요.
- 한글이나 영어가 섞여 있다면 보이는 그대로 입력해주세요.

답변은 정답만 간단히 입력해주세요. 설명은 필요 없습니다."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            answer = response.choices[0].message.content.strip()
            self.signals.progress.emit(f"🤖 ChatGPT 캡차 해결: '{answer}'")
            return answer
            
        except Exception as e:
            self.signals.progress.emit(f"❌ ChatGPT 캡차 해결 실패: {str(e)}")
            return None
    
    def check_and_set_public_visibility(self, driver, thread_id):
        """공개 설정 확인 및 전체공개로 변경"""
        try:
            self.emit_progress("🔍 공개 설정 확인 중...", thread_id)
            
            # 공개 설정 영역이 열려있는지 확인
            try:
                # 공개 설정 버튼 클릭하여 설정 영역 열기
                open_set_btn = driver.find_element(By.CSS_SELECTOR, "button.btn_open_set")
                if open_set_btn:
                    driver.execute_script("arguments[0].click();", open_set_btn)
                    self.smart_sleep(1, "공개 설정 영역 열기 후 대기")
            except:
                # 버튼이 없거나 이미 열려있는 경우 계속 진행
                pass
            
            # 멤버공개 라디오 버튼이 선택되어 있는지 확인
            try:
                member_radio = driver.find_element(By.ID, "member")
                if member_radio.is_selected():
                    self.emit_progress("📢 멤버공개 감지 → 전체공개로 변경 중...", thread_id)
                    
                    # 전체공개 라디오 버튼 클릭
                    all_radio = driver.find_element(By.ID, "all")
                    driver.execute_script("arguments[0].click();", all_radio)
                    self.smart_sleep(0.5, "전체공개 선택 후 대기")
                    
                    # 검색·네이버 서비스 공개 체크박스도 체크 (가능한 경우)
                    try:
                        permit_checkbox = driver.find_element(By.ID, "permit")
                        if not permit_checkbox.is_selected() and not permit_checkbox.get_attribute("disabled"):
                            driver.execute_script("arguments[0].click();", permit_checkbox)
                            self.emit_progress("✅ 검색·네이버 서비스 공개도 활성화", thread_id)
                    except:
                        # 체크박스가 비활성화되어 있거나 없는 경우 무시
                        pass
                    
                    self.emit_progress("✅ 전체공개로 설정 완료", thread_id)
                    self.smart_sleep(1, "공개 설정 변경 후 대기")
                else:
                    self.emit_progress("ℹ️ 이미 전체공개 상태입니다", thread_id)
                    
            except Exception as radio_error:
                self.emit_progress(f"⚠️ 공개 설정 라디오 버튼 처리 실패: {str(radio_error)}", thread_id)
                # 라디오 버튼을 찾을 수 없어도 계속 진행
                
        except Exception as e:
            self.emit_progress(f"⚠️ 공개 설정 확인/변경 실패: {str(e)}", thread_id)
            # 실패해도 계속 진행 (치명적이지 않음)
    
    def check_login_failure_reason_early(self, driver):
        """🔧 로그인 실패 원인 우선 체크 (에러 메시지 기반)"""
        try:
            # 🚨 네이버 로그인 에러 메시지 우선 체크 (display: none이 아닌 것만)
            error_selectors = {
                "#err_common": "아이디 또는 비밀번호 오류",
                "#err_empty_id": "아이디 입력 누락", 
                "#err_empty_pw": "비밀번호 입력 누락",
                "#err_capslock": "Caps Lock 활성화",
                "#err_passkey_common": "패스키 로그인 실패",
                "#err_passkey_common2": "패스키 로그인 실패",
                "#err_passkey_common3": "패스키 로그인 실패", 
                "#err_passkey_common4": "패스키 로그인 실패"
            }
            
            for selector, error_type in error_selectors.items():
                try:
                    error_element = driver.find_element(By.CSS_SELECTOR, selector)
                    # display: none이 아닌 경우만 에러로 판단
                    if error_element and error_element.is_displayed():
                        # 실제 에러 메시지 텍스트 추출
                        error_text = error_element.text.strip()
                        if error_text:
                            return f"{error_type}: {error_text[:50]}"
                        else:
                            return error_type
                except:
                    continue
            
            # 일반적인 에러 메시지 추가 체크
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".error_message:not([style*='display: none'])")
                for error_element in error_elements:
                    if error_element and error_element.is_displayed():
                        error_text = error_element.text.strip()
                        if error_text and len(error_text) > 5:  # 의미있는 에러 메시지만
                            return f"로그인 오류: {error_text[:50]}"
            except:
                pass
                
            # 에러 메시지가 없으면 None 반환 (URL 체크로 넘어감)
            return None
            
        except Exception as e:
            # 에러 체크 자체에 실패해도 None 반환 (URL 체크로 넘어감)
            return None


    def check_login_failure_reason_early(self, driver):
        """🔥 로그인 실패 원인 우선 체크 (에러 메시지 기반) - 답글방식에서 가져온 최적화"""
        try:
            # 🚨 네이버 로그인 에러 메시지 우선 체크 (display: none이 아닌 것만)
            error_selectors = {
                "#err_common": "아이디 또는 비밀번호 오류",
                "#err_empty_id": "아이디 입력 누락", 
                "#err_empty_pw": "비밀번호 입력 누락",
                "#err_capslock": "Caps Lock 활성화",
                "#err_passkey_common": "패스키 로그인 실패",
                "#err_passkey_common2": "패스키 로그인 실패",
                "#err_passkey_common3": "패스키 로그인 실패", 
                "#err_passkey_common4": "패스키 로그인 실패"
            }
            
            for selector, error_type in error_selectors.items():
                try:
                    error_element = driver.find_element(By.CSS_SELECTOR, selector)
                    # display: none이 아닌 경우만 에러로 판단
                    if error_element and error_element.is_displayed():
                        # 실제 에러 메시지 텍스트 추출
                        error_text = error_element.text.strip()
                        if error_text:
                            return f"{error_type}: {error_text[:50]}"
                        else:
                            return error_type
                except:
                    continue
            
            # 일반적인 에러 메시지 추가 체크
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".error_message:not([style*='display: none'])")
                for error_element in error_elements:
                    if error_element and error_element.is_displayed():
                        error_text = error_element.text.strip()
                        if error_text and len(error_text) > 5:  # 의미있는 에러 메시지만
                            return f"로그인 오류: {error_text[:50]}"
            except:
                pass
                
            # 에러 메시지가 없으면 None 반환 (URL 체크로 넘어감)
            return None
            
        except Exception as e:
            # 에러 체크 자체에 실패해도 None 반환 (URL 체크로 넘어감)
            return None

    def check_login_failure_reason(self, driver):
        """로그인 실패 원인 분석"""
        try:
            # 아이디 보호 메시지 재확인
            try:
                warning_element = driver.find_element(By.CSS_SELECTOR, ".warning_title")
                if warning_element and "아이디를 보호하고 있습니다" in warning_element.text:
                    return "아이디 보호 기능 발동"
            except:
                pass
            
            # 캡차 오류 확인
            try:
                captcha_error = driver.find_element(By.CSS_SELECTOR, ".error_message")
                if captcha_error and ("자동입력 방지" in captcha_error.text or "captcha" in captcha_error.text.lower()):
                    return "캡차 입력 오류"
            except:
                pass
            
            # ID/PW 오류 확인
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".error_message, .message_error, .alert_error")
                for error_element in error_elements:
                    error_text = error_element.text
                    if "아이디" in error_text and "비밀번호" in error_text:
                        return "아이디 또는 비밀번호 오류"
                    elif "존재하지 않는" in error_text:
                        return "존재하지 않는 아이디"
                    elif "비밀번호가 틀렸습니다" in error_text:
                        return "비밀번호 오류"
                    elif "로그인" in error_text and "실패" in error_text:
                        return f"로그인 오류: {error_text[:50]}"
            except:
                pass
            
            # 계정 잠금 확인
            try:
                lock_message = driver.find_element(By.CSS_SELECTOR, ".lock_message, .account_lock")
                if lock_message:
                    return "계정 잠금 상태"
            except:
                pass
            
            # 기타 보안 관련 메시지 확인
            try:
                security_elements = driver.find_elements(By.CSS_SELECTOR, ".security_message, .warning_message")
                for security_element in security_elements:
                    security_text = security_element.text
                    if "보안" in security_text or "제한" in security_text:
                        return f"보안 제한: {security_text[:30]}"
            except:
                pass
            
            # 현재 URL 기반 판단
            current_url = driver.current_url
            if "loginform" in current_url:
                return "로그인 페이지에 머물러 있음 (원인 불명)"
            elif "error" in current_url:
                return "로그인 오류 페이지로 이동됨"
            else:
                return "알 수 없는 로그인 실패"
                
        except Exception as e:
            return f"실패 원인 분석 중 오류: {str(e)}"
    
    def has_captcha(self, driver):
        """현재 페이지에 캡차가 있는지 확인"""
        try:
            # 캡차 이미지 확인
            captcha_image = driver.find_element(By.ID, "captchaimg")
            if captcha_image and captcha_image.is_displayed():
                return True
        except:
            pass
        
        try:
            # 캡차 입력 필드 확인
            captcha_input = driver.find_element(By.ID, "captcha")
            if captcha_input and captcha_input.is_displayed():
                return True
        except:
            pass
        
        try:
            # 기타 캡차 관련 요소 확인
            captcha_elements = driver.find_elements(By.CSS_SELECTOR, "[id*='captcha'], [class*='captcha'], [id*='Captcha'], [class*='Captcha']")
            for element in captcha_elements:
                if element.is_displayed():
                    return True
        except:
            pass
        
        return False
    
    def handle_deleted_post_popup(self, driver):
        """삭제된 게시글 팝업 처리"""
        try:
            self.signals.progress.emit("🔍 삭제된 게시글 팝업 확인 중...")
            
            # JavaScript alert 팝업 확인
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                self.signals.progress.emit(f"🔔 Alert 감지: {alert_text}")
                
                # 삭제된 게시글 관련 키워드 확인
                delete_keywords = ["삭제되었거나 없는 게시글", "삭제된 게시글", "존재하지 않는 게시글", 
                                 "없는 게시글", "삭제되었습니다", "찾을 수 없습니다"]
                
                if any(keyword in alert_text for keyword in delete_keywords):
                    alert.accept()  # 확인 버튼 클릭
                    self.signals.progress.emit("✅ 삭제된 게시글 Alert 처리 완료")
                    time.sleep(1)
                    return True
                else:
                    # 다른 종류의 alert는 그대로 둠
                    return False
                    
            except:
                # alert가 없는 경우
                pass
                
            # 페이지 내 에러 메시지 확인
            try:
                error_selectors = [
                    "div.error_content",
                    "div.no_article",
                    "div.content_error",
                    "p.error_msg"
                ]
                
                for selector in error_selectors:
                    error_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in error_elements:
                        if element.is_displayed():
                            error_text = element.text
                            if any(keyword in error_text for keyword in ["삭제", "없는", "존재하지"]):
                                self.signals.progress.emit(f"✅ 삭제된 게시글 메시지 감지: {error_text}")
                                return True
            except:
                pass
                
            return False
            
        except Exception as e:
            self.signals.progress.emit(f"⚠️ 삭제된 게시글 팝업 처리 중 오류: {str(e)}")
            return False

    def handle_title_popup(self, driver):
        """제목 입력 관련 팝업 처리 전용"""
        try:
            self.signals.progress.emit("🔍 제목 관련 팝업 확인 중...")
            
            # JavaScript alert 처리
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                self.signals.progress.emit(f"📋 제목 관련 Alert 감지: {alert_text}")
                
                # 제목 관련 팝업 확인
                if any(keyword in alert_text for keyword in ["제목을 입력", "제목 입력", "제목을 작성"]):
                    alert.accept()  # 확인 버튼 클릭
                    self.signals.progress.emit("✅ 제목 입력 Alert 처리 완료")
                    time.sleep(1)
                    return True
                else:
                    # 제목과 관련 없는 팝업은 처리하지 않음
                    return False
                    
            except Exception:
                # alert가 없는 경우
                return False
            
        except Exception as e:
            self.signals.progress.emit(f"⚠️ 제목 팝업 처리 중 오류: {str(e)}")
            return False
    
    def reset_blocked_accounts(self):
        """차단된 계정 목록 초기화"""
        blocked_count = len(self.blocked_accounts)
        self.blocked_accounts.clear()
        self.signals.progress.emit(f"🔄 차단된 계정 목록 초기화: {blocked_count}개 계정 해제")
    
    def get_blocked_accounts_info(self):
        """차단된 계정 정보 반환"""
        if self.blocked_accounts:
            return f"차단된 계정: {', '.join(self.blocked_accounts)}"
        else:
            return "차단된 계정 없음"
    
    def kill_thread_chrome_processes(self, thread_id):
        """특정 쓰레드의 크롬 프로세스만 개별 종료"""
        try:
            with self.drivers_lock:
                pids = self.thread_chrome_pids.get(thread_id, [])
                
            if not pids:
                self.signals.progress.emit(f"🔍 [쓰레드{thread_id}] 종료할 크롬 프로세스가 없습니다")
                return
            
            killed_count = 0
            for pid in pids:
                try:
                    # 특정 PID의 프로세스 종료
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        process.terminate()
                        process.wait(timeout=3)  # 3초 대기
                        killed_count += 1
                        self.signals.progress.emit(f"💀 [쓰레드{thread_id}] 크롬 PID {pid} 종료됨")
                    else:
                        self.signals.progress.emit(f"ℹ️ [쓰레드{thread_id}] 크롬 PID {pid} 이미 종료됨")
                except Exception as e:
                    self.signals.progress.emit(f"⚠️ [쓰레드{thread_id}] PID {pid} 종료 실패: {str(e)}")
            
            # 추적 목록에서 제거
            with self.drivers_lock:
                if thread_id in self.thread_chrome_pids:
                    del self.thread_chrome_pids[thread_id]
            
            self.signals.progress.emit(f"🧹 [쓰레드{thread_id}] 크롬 프로세스 정리 완료: {killed_count}개 종료")
            
        except Exception as e:
            self.signals.progress.emit(f"❌ [쓰레드{thread_id}] 크롬 프로세스 종료 중 오류: {str(e)}")
    
    def safe_cleanup_thread_drivers(self, thread_id):
        """🧹 스레드별 드라이버 완전 정리 (크롬창 누적 방지 강화)"""
        try:
            self.emit_progress(f"🧹 [스레드{thread_id+1}] 전체 드라이버 정리 시작...", thread_id)
            
            # 1단계: 드라이버 딕셔너리에서 해당 스레드 드라이버들 찾기 및 종료
            with self.drivers_lock:
                drivers_to_remove = []
                
                # 해당 스레드의 모든 드라이버 키 찾기 (더 포괄적으로)
                for key in list(self.drivers.keys()):
                    if (key.startswith(f"{thread_id}_") or 
                        f"_t{thread_id}_" in key or 
                        f"edit_block" in key):  # 수정용 드라이버도 포함
                        drivers_to_remove.append(key)
                
                self.emit_progress(f"🔍 [스레드{thread_id+1}] 정리 대상 드라이버: {len(drivers_to_remove)}개", thread_id)
                
                # 각 드라이버 안전하게 종료
                for key in drivers_to_remove:
                    try:
                        if key in self.drivers:
                            driver = self.drivers[key]
                            
                            # 로그아웃 시도
                            try:
                                self.logout_naver(driver)
                            except:
                                pass
                            
                            # 모든 탭 닫기 시도
                            try:
                                for handle in driver.window_handles:
                                    driver.switch_to.window(handle)
                                    driver.close()
                            except:
                                pass
                            
                            # 드라이버 완전 종료
                            driver.quit()
                            self.emit_progress(f"✅ [스레드{thread_id+1}] 드라이버 {key} 완전 종료", thread_id)
                            
                    except Exception as e:
                        self.emit_progress(f"⚠️ [스레드{thread_id+1}] 드라이버 {key} 종료 오류: {e}", thread_id)
                    
                    # 딕셔너리에서 제거
                    if key in self.drivers:
                        del self.drivers[key]
            
            # 2단계: 해당 스레드의 모든 Chrome 프로세스 강제 종료
            self.kill_thread_chrome_processes(thread_id)
            
            # 3단계: 임시 폴더 완전 정리 (모든 타입)
            try:
                import glob
                import shutil
                
                # 해당 스레드의 모든 임시 폴더 찾기
                temp_patterns = [
                    f"{tempfile.gettempdir()}/chrome_t{thread_id}_*",
                    f"{tempfile.gettempdir()}/chrome_*_t{thread_id}_*"
                ]
                
                cleaned_dirs = 0
                for pattern in temp_patterns:
                    temp_dirs = glob.glob(pattern)
                    for temp_dir in temp_dirs:
                        try:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            cleaned_dirs += 1
                            self.emit_progress(f"🗑️ [스레드{thread_id+1}] 임시 폴더 삭제: {os.path.basename(temp_dir)}", thread_id)
                        except Exception as e:
                            self.emit_progress(f"⚠️ [스레드{thread_id+1}] 임시 폴더 삭제 실패: {e}", thread_id)
                
                if cleaned_dirs > 0:
                    self.emit_progress(f"🧹 [스레드{thread_id+1}] 임시 폴더 {cleaned_dirs}개 정리 완료", thread_id)
                    
            except Exception as cleanup_error:
                self.emit_progress(f"⚠️ [스레드{thread_id+1}] 임시 폴더 정리 실패: {cleanup_error}", thread_id)
            
            # 4단계: 메모리 정리
            import gc
            gc.collect()
            
            # 5단계: 1초 대기 후 남은 Chrome 프로세스 한 번 더 정리 (완전 정리)
            time.sleep(1)
            self.force_kill_remaining_chrome_processes(thread_id)
            
            self.emit_progress(f"✅ [스레드{thread_id+1}] 전체 정리 완료 - 크롬창 누적 방지", thread_id)
            
        except Exception as e:
            self.emit_progress(f"❌ [스레드{thread_id+1}] 드라이버 정리 중 오류: {str(e)}", thread_id)
    
    def force_kill_remaining_chrome_processes(self, thread_id):
        """🔥 남은 Chrome 프로세스 강제 종료 (크롬창 누적 방지)"""
        try:
            import psutil
            killed_count = 0
            
            # 해당 스레드와 관련된 모든 Chrome 프로세스 찾기
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        
                        # 스레드별 포트나 폴더명이 포함된 프로세스 찾기
                        if (f"chrome_t{thread_id}_" in cmdline or 
                            f"remote-debugging-port={9222 + thread_id * 20}" in cmdline or
                            f"remote-debugging-port={9222 + (thread_id * 20)}" in cmdline):
                            
                            proc.terminate()
                            killed_count += 1
                            self.emit_progress(f"💀 [스레드{thread_id+1}] Chrome PID {proc.info['pid']} 강제 종료", thread_id)
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    continue
            
            if killed_count > 0:
                self.emit_progress(f"🔥 [스레드{thread_id+1}] 남은 Chrome 프로세스 {killed_count}개 강제 종료", thread_id)
                
                # 프로세스 종료 후 잠시 대기
                time.sleep(2)
            else:
                self.emit_progress(f"✅ [스레드{thread_id+1}] 정리할 Chrome 프로세스 없음", thread_id)
                
        except Exception as e:
            self.emit_progress(f"⚠️ [스레드{thread_id+1}] Chrome 프로세스 강제 정리 실패: {e}", thread_id)
    
    def force_cleanup_all_chrome_processes(self):
        """🎯 자동화 프로그램이 생성한 Chrome 프로세스만 선택적 정리 (사용자 Chrome 보호)"""
        try:
            import psutil
            import subprocess
            
            self.signals.progress.emit("🎯 자동화 전용 Chrome 프로세스 선택적 정리 시작...")
            
            killed_count = 0
            protected_count = 0
            automation_identifiers = []
            
            # 자동화 프로그램이 생성한 Chrome 프로세스 식별자 수집
            with self.drivers_lock:
                for thread_id, pids in self.thread_chrome_pids.items():
                    for pid in pids:
                        automation_identifiers.append(pid)
            
            # 1단계: 추적된 PID 기반으로 정리 (가장 안전)
            for pid in automation_identifiers:
                try:
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        # 추가 검증: 명령줄에 자동화 식별자 확인
                        cmdline = ' '.join(process.cmdline()) if process.cmdline() else ''
                        if any(identifier in cmdline for identifier in [
                            'chrome_t', 'remote-debugging-port=922', 'user-data-dir'
                        ]):
                            process.terminate()
                            killed_count += 1
                            self.signals.progress.emit(f"💀 자동화 Chrome PID {pid} 종료")
                        else:
                            protected_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    continue
            
            # 2단계: 명령줄 기반 선택적 정리 (추적되지 않은 프로세스)
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        
                        # 자동화 프로그램 식별자가 있는 프로세스만 종료
                        is_automation_chrome = any(identifier in cmdline for identifier in [
                            'chrome_t0_', 'chrome_t1_', 'chrome_t2_', 'chrome_t3_', 'chrome_t4_',  # 스레드별 폴더
                            'remote-debugging-port=9222', 'remote-debugging-port=9242',  # 자동화 포트
                            'remote-debugging-port=9262', 'remote-debugging-port=9282', 
                            'remote-debugging-port=9302',  # 스레드별 포트
                            '--disable-blink-features=AutomationControlled',  # 자동화 식별자
                            '--incognito'  # 시크릿 모드 (일반 사용자는 잘 사용하지 않음)
                        ])
                        
                        if is_automation_chrome:
                            # PID가 이미 처리되지 않은 경우만
                            if proc.info['pid'] not in automation_identifiers:
                                proc.terminate()
                                killed_count += 1
                                self.signals.progress.emit(f"💀 미추적 자동화 Chrome PID {proc.info['pid']} 종료")
                        else:
                            protected_count += 1
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    continue
            
            # 3단계: 자동화 전용 임시 폴더만 정리
            try:
                import glob
                import shutil
                
                # 자동화 프로그램이 생성한 폴더만 정리
                automation_temp_patterns = [
                    f"{tempfile.gettempdir()}/chrome_t*_*",  # 스레드별 폴더
                    f"{tempfile.gettempdir()}/chrome_reply_*",  # 답글용 폴더
                    f"{tempfile.gettempdir()}/chrome_comment_*"  # 댓글용 폴더
                ]
                
                cleaned_dirs = 0
                for pattern in automation_temp_patterns:
                    temp_dirs = glob.glob(pattern)
                    for temp_dir in temp_dirs:
                        try:
                            # 폴더명에 타임스탬프가 포함된 것만 정리 (더 안전)
                            folder_name = os.path.basename(temp_dir)
                            if any(identifier in folder_name for identifier in ['chrome_t', '_reply_', '_comment_']):
                                shutil.rmtree(temp_dir, ignore_errors=True)
                                cleaned_dirs += 1
                        except:
                            pass
                
                if cleaned_dirs > 0:
                    self.signals.progress.emit(f"🗂️ 자동화 전용 임시 폴더 {cleaned_dirs}개 정리")
                    
            except:
                pass
            
            # 4단계: 메모리 정리
            import gc
            gc.collect()
            
            self.signals.progress.emit(f"✅ 선택적 Chrome 정리 완료 (자동화: {killed_count}개 종료, 사용자: {protected_count}개 보호)")
            
            # 대기 시간 단축 (5초 → 2초)
            time.sleep(2)
            
        except Exception as e:
            self.signals.progress.emit(f"⚠️ 선택적 Chrome 프로세스 정리 실패: {e}")
    
    def detect_user_chrome_processes(self):
        """🛡️ 사용자가 실제 사용 중인 Chrome 프로세스 감지 및 보호"""
        try:
            import psutil
            user_chrome_count = 0
            automation_chrome_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        
                        # 자동화 프로그램 식별자 체크
                        is_automation = any(identifier in cmdline for identifier in [
                            'chrome_t', 'remote-debugging-port=922', 'AutomationControlled',
                            'excludeSwitches', 'useAutomationExtension=false', 'incognito'
                        ])
                        
                        if is_automation:
                            automation_chrome_count += 1
                        else:
                            user_chrome_count += 1
                            
                except:
                    continue
            
            if user_chrome_count > 0:
                self.signals.progress.emit(f"🛡️ 사용자 Chrome {user_chrome_count}개 감지됨 - 보호 모드 활성화")
                self.signals.progress.emit(f"🤖 자동화 Chrome {automation_chrome_count}개 감지됨 - 정리 대상")
                return True
            else:
                self.signals.progress.emit(f"ℹ️ 사용자 Chrome 없음 - 일반 정리 모드")
                return False
                
        except Exception as e:
            self.signals.progress.emit(f"⚠️ Chrome 프로세스 감지 실패: {e}")
            return True  # 안전을 위해 보호 모드로 설정

# 메인 GUI 클래스
class CafePostingMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 카페 포스팅 자동화 프로그램 v1.0")
        
        # 적절한 고정 크기로 설정
        self.setGeometry(100, 100, 1400, 900)
        
        # 최소 크기 설정
        self.setMinimumSize(1200, 800)
        
        # 🔥 로그 파일 설정 (프로그램 시작 시 초기화)
        self.setup_logging()
        
        # 데이터 저장
        self.reply_accounts = []
        self.comment_accounts = []
        self.reply_proxies = []
        self.comment_proxies = []
        self.urls = []
        self.script_folders = []
        self.url_script_mapping = {}  # 기존 호환성 유지
        self.url_comment_block_settings = {}  # URL별 댓글 차단 설정
        self.account_urls = {}  # 🆕 계정별 수정할 URL 매핑
        self.account_rows = []  # 🆕 각 행의 정보를 개별적으로 저장
        
        # 🆕 ID 기준 새로운 데이터 구조
        self.id_script_mapping = {}  # 아이디별 원고 매칭
        self.spare_accounts = []     # 여분 아이디 목록
        self.id_comment_block_settings = {}  # 아이디별 댓글 차단 설정
        self.id_url_assignments = {}  # 아이디별 URL 배정
        
        # 🏢 카페별 개별 탭 시스템
        self.cafe_folders = []       # 로드된 카페 폴더 목록
        self.current_cafe_index = 0  # 현재 작업 중인 카페 인덱스
        self.cafe_tabs = {}          # 카페별 탭 위젯 저장 {cafe_name: tab_widget}
        self.cafe_data = {}          # 카페별 데이터 저장 {cafe_name: {매칭데이터, 상태 등}}
        self.cafe_tab_indices = {}   # 카페별 탭 인덱스 저장 {cafe_name: tab_index}
        
        self.worker = None
        self.results = []
        
        # 🆕 개선된 저장 시스템
        self.auto_save_enabled = False      # 자동 저장 활성화 여부
        self.save_directory = ""            # 미리 설정된 저장 폴더
        self.pending_results = {}           # 탭별 결과 임시 저장 {cafe_name: results}
        
        # 🔄 공용 풀 시스템 추가
        self.available_reply_accounts = []      # 답글 계정 공용 풀
        self.available_comment_accounts = []    # 댓글 계정 공용 풀
        self.blocked_reply_accounts = set()     # 차단된 답글 계정
        self.blocked_comment_accounts = set()   # 차단된 댓글 계정
        self.reply_pool_lock = threading.Lock()      # 답글 계정 풀 락
        self.comment_pool_lock = threading.Lock()    # 댓글 계정 풀 락
        self.drivers_lock = threading.Lock()         # 드라이버 관리 락
        self.clipboard_lock = threading.Lock()       # 클립보드 락
        
        self.setup_ui()
        self.setup_style()
        
        # 초기 상태 설정
        self.update_mapping_status(0)
    
    def setup_logging(self):
        """🔥 로그 파일 설정 - 프로그램 시작 시 로그 파일 초기화"""
        try:
            # 로그 파일 경로 설정 (영문 파일명으로 변경)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file_path = os.path.join(os.path.dirname(__file__), f"cafe_posting_log_{timestamp}.txt")
            
            # 기존 로그 파일이 있으면 삭제 (초기화)
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
            
            # 로거 설정
            self.logger = logging.getLogger('CafePosting')
            self.logger.setLevel(logging.INFO)
            
            # 기존 핸들러 제거
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # 파일 핸들러 설정
            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 로그 포맷 설정
            formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            
            # 시작 로그 기록 및 로그 파일 생성 확인
            self.logger.info("=" * 60)
            self.logger.info("🚀 네이버 카페 포스팅 프로그램 시작")
            self.logger.info("=" * 60)
            
            # 로그 파일이 실제로 생성되었는지 확인
            if os.path.exists(self.log_file_path):
                file_size = os.path.getsize(self.log_file_path)
                self.logger.info(f"✅ 로그 파일 생성 확인: {self.log_file_path} (크기: {file_size} bytes)")
                print(f"✅ 로그 파일 생성됨: {self.log_file_path}")
            else:
                print(f"❌ 로그 파일 생성 실패: {self.log_file_path}")
                # 콘솔 로그로 대체
                print("⚠️ 파일 로그 실패 - 콘솔 로그로 진행합니다")
            
            print(f"📝 로그 파일 생성: {self.log_file_path}")
            
        except Exception as e:
            print(f"❌ 로그 설정 실패: {e}")
            self.logger = None
    
    def verify_log_file_health(self):
        """🔍 로그 파일 상태 주기적 확인"""
        try:
            if hasattr(self, 'log_file_path') and self.log_file_path and os.path.exists(self.log_file_path):
                file_size = os.path.getsize(self.log_file_path)
                # 로그 파일이 너무 작으면 경고
                if file_size < 100:  # 100바이트 미만이면 문제 가능성
                    print(f"⚠️ 로그 파일이 너무 작습니다: {file_size} bytes")
                    return False
                return True
            else:
                print("❌ 로그 파일이 존재하지 않습니다")
                return False
        except Exception as e:
            print(f"⚠️ 로그 파일 상태 확인 실패: {e}")
            return False
    
    def periodic_log_check(self):
        """🔍 주기적 로그 파일 상태 체크"""
        try:
            if hasattr(self, 'worker') and self.worker and self.worker.is_running:
                log_health = self.verify_log_file_health()
                if not log_health:
                    self.log_message("🚨 로그 파일 문제 감지! 백업 로그로 전환")
                    # 백업 로그 파일 생성
                    backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_log_path = os.path.join(os.path.dirname(__file__), f"backup_log_{backup_timestamp}.txt")
                    with open(backup_log_path, 'w', encoding='utf-8') as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] 백업 로그 파일 생성 - 메인 로그 실패\n")
                    print(f"📝 백업 로그 생성: {backup_log_path}")
                else:
                    # 로그 파일 크기 확인
                    file_size = os.path.getsize(self.log_file_path)
                    self.log_message(f"📊 로그 상태 정상 (크기: {file_size} bytes)")
        except Exception as e:
            print(f"⚠️ 주기적 로그 체크 실패: {e}")
        
        # 시작 메시지는 UI 초기화 후에 표시됨
    
    def setup_ui(self):
        """UI 구성"""
        # 🆕 메뉴바 생성
        self.create_menu_bar()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 각 탭 생성
        self.create_account_tab()
        self.create_execution_tab()
        self.create_result_tab()
    
    def create_menu_bar(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        # 업데이트 확인
        update_action = file_menu.addAction('🔄 업데이트 확인')
        update_action.triggered.connect(self.manual_update_check)
        
        file_menu.addSeparator()
        
        # 종료
        exit_action = file_menu.addAction('❌ 종료')
        exit_action.triggered.connect(self.close)
        
        # 도구 메뉴
        tools_menu = menubar.addMenu('도구')
        
        # 라이선스 관리자
        license_manager_action = tools_menu.addAction('🔐 라이선스 관리자')
        license_manager_action.triggered.connect(self.open_license_manager)
        
        # 정보 메뉴
        info_menu = menubar.addMenu('정보')
        
        # 버전 정보
        version_action = info_menu.addAction('ℹ️ 버전 정보')
        version_action.triggered.connect(self.show_version_info)
        
        # 정보
        about_action = info_menu.addAction('📋 프로그램 정보')
        about_action.triggered.connect(self.show_about_info)
    
    def show_version_info(self):
        """버전 정보 표시"""
        version_info = get_version_info()
        
        message = f"""🔢 버전 정보

📱 프로그램: 네이버 카페 포스팅 자동화
🏷️ 버전: v{version_info['version']}
📅 빌드 날짜: {version_info['build_date']}
👨‍💻 개발자: {version_info['author']}

🔐 라이선스: 인증됨
🖥️ 머신 ID: {get_machine_id()}

🔄 업데이트: GitHub 자동 업데이트 지원
📦 빌드 타입: PyInstaller onedir"""
        
        QMessageBox.information(self, "버전 정보", message)
    
    def show_about_info(self):
        """프로그램 정보 표시"""
        message = f"""🤖 네이버 카페 포스팅 자동화 프로그램

📋 주요 기능:
• 답글 자동 작성
• 댓글 자동 작성  
• 멤버공개 → 전체공개 자동 변경
• 작업 완료 후 댓글 차단
• 프록시 서버 지원
• 스레드 1-5개 동시 실행
• 라이선스 인증 시스템
• 자동 업데이트 기능

⚠️ 주의사항:
• 교육 목적으로만 사용하세요
• 네이버 이용약관을 준수해주세요
• 사용으로 인한 책임은 사용자에게 있습니다

📞 문의사항이 있으시면 관리자에게 연락하세요."""
        
        QMessageBox.information(self, "프로그램 정보", message)
    
    def manual_update_check(self):
        """수동 업데이트 확인"""
        self.log_message("🔄 수동 업데이트 확인 시작...")
        
        # 별도 스레드에서 업데이트 확인
        def check_update():
            try:
                update_info = check_for_updates()
                
                if update_info.get('available'):
                    self.log_message(f"🆕 새 버전 발견: v{update_info['version']}")
                    
                    # 메인 스레드에서 다이얼로그 표시
                    QTimer.singleShot(100, lambda: self.handle_update_dialog(update_info))
                else:
                    self.log_message("✅ 이미 최신 버전입니다.")
                    QTimer.singleShot(100, lambda: QMessageBox.information(
                        self, "업데이트 확인", f"현재 v{CURRENT_VERSION}이 최신 버전입니다."))
                    
            except Exception as e:
                self.log_message(f"❌ 업데이트 확인 실패: {e}")
                QTimer.singleShot(100, lambda: QMessageBox.warning(
                    self, "업데이트 오류", f"업데이트 확인에 실패했습니다:\n{str(e)}"))
        
        threading.Thread(target=check_update, daemon=True).start()
    
    def handle_update_dialog(self, update_info):
        """업데이트 다이얼로그 처리"""
        if show_update_dialog(update_info):
            if update_info.get('download_url'):
                download_and_install_update(update_info['download_url'], update_info['version'])
            else:
                QMessageBox.warning(self, "업데이트 오류", "다운로드 링크를 찾을 수 없습니다.\nGitHub에서 수동으로 다운로드해주세요.")
    
    def open_license_manager(self):
        """라이선스 관리자 실행"""
        try:
            license_manager_path = "license_manager_modern.py"
            if os.path.exists(license_manager_path):
                subprocess.Popen([sys.executable, license_manager_path])
                self.log_message("🔐 라이선스 관리자 실행됨")
            else:
                QMessageBox.warning(self, "오류", "라이선스 관리자 파일을 찾을 수 없습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"라이선스 관리자 실행 실패:\n{str(e)}")
            self.log_message(f"❌ 라이선스 관리자 실행 실패: {e}")
    
    def create_account_tab(self):
        """카페 폴더 선택 및 계정 설정 탭"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 카페 폴더 선택 그룹
        cafe_group = QGroupBox("카페 폴더 선택")
        cafe_layout = QVBoxLayout(cafe_group)
        
        # 설명
        info_label = QLabel("각 카페별 폴더를 선택하면 accounts.xlsx(C열에 수정할 URL), 원고 폴더가 자동으로 로드됩니다.")
        info_label.setStyleSheet("color: #666; font-size: 11px; margin: 5px;")
        cafe_layout.addWidget(info_label)
        
        cafe_folder_layout = QHBoxLayout()
        self.cafe_folder_label = QLabel("선택된 카페 폴더: 없음")
        self.cafe_folder_btn = QPushButton("📁 카페 폴더들 선택 (다중 선택)")
        self.cafe_folder_btn.clicked.connect(self.load_cafe_folders)
        
        cafe_folder_layout.addWidget(self.cafe_folder_label)
        cafe_folder_layout.addStretch()
        cafe_folder_layout.addWidget(self.cafe_folder_btn)
        cafe_layout.addLayout(cafe_folder_layout)
        
        # 선택된 카페 목록 표시
        self.cafe_list_widget = QListWidget()
        self.cafe_list_widget.setMaximumHeight(100)
        self.cafe_list_widget.setStyleSheet("QListWidget { background-color: #f9f9f9; border: 1px solid #ddd; }")
        cafe_layout.addWidget(QLabel("📋 선택된 카페 목록:"))
        cafe_layout.addWidget(self.cafe_list_widget)
        
        # 로드된 데이터 상태 표시
        status_layout = QVBoxLayout()
        self.url_status_label = QLabel("📄 URLs: 로드되지 않음")
        self.reply_acc_status_label = QLabel("👤 답글 계정: 로드되지 않음")
        self.comment_acc_status_label = QLabel("💬 댓글 계정: 로드되지 않음")
        self.script_status_label = QLabel("📝 원고 폴더: 로드되지 않음")
        
        status_layout.addWidget(self.url_status_label)
        status_layout.addWidget(self.reply_acc_status_label)
        status_layout.addWidget(self.comment_acc_status_label)
        status_layout.addWidget(self.script_status_label)
        cafe_layout.addLayout(status_layout)
        
        layout.addWidget(cafe_group)
        
        # 프록시 설정 그룹 (전체 공용)
        proxy_group = QGroupBox("프록시 설정 (전체 공용)")
        proxy_layout = QVBoxLayout(proxy_group)
        
        proxy_file_layout = QHBoxLayout()
        self.proxy_file_label = QLabel("선택된 파일: 없음")
        self.proxy_load_btn = QPushButton("📂 프록시 파일 선택")
        self.proxy_load_btn.clicked.connect(self.load_proxy_file)
        
        proxy_file_layout.addWidget(self.proxy_file_label)
        proxy_file_layout.addStretch()
        proxy_file_layout.addWidget(self.proxy_load_btn)
        proxy_layout.addLayout(proxy_file_layout)
        
        layout.addWidget(proxy_group)
        
        # GPT API 설정 그룹
        gpt_group = QGroupBox("GPT API 설정 (캡차 해결용)")
        gpt_layout = QVBoxLayout(gpt_group)
        
        # API 키 입력
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API 키:"))
        self.gpt_api_key_input = QLineEdit()
        self.gpt_api_key_input.setEchoMode(QLineEdit.Password)
        self.gpt_api_key_input.setPlaceholderText("OpenAI API 키를 입력하세요")
        self.gpt_api_key_input.setText(app_config.get('gpt_api_key', ''))
        api_layout.addWidget(self.gpt_api_key_input)
        
        save_api_btn = QPushButton("저장")
        save_api_btn.clicked.connect(self.save_gpt_config)
        api_layout.addWidget(save_api_btn)
        
        gpt_layout.addLayout(api_layout)
        
        # 모델 선택
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("모델:"))
        self.gpt_model_combo = QComboBox()
        self.gpt_model_combo.addItems(['gpt-4o', 'gpt-4', 'gpt-3.5-turbo'])
        self.gpt_model_combo.setCurrentText(app_config.get('gpt_model', 'gpt-4o'))
        model_layout.addWidget(self.gpt_model_combo)
        model_layout.addStretch()
        
        gpt_layout.addLayout(model_layout)
        
        # 설명
        info_label = QLabel("※ 네이버 로그인 시 캡차가 나타나면 GPT API를 사용해 자동으로 해결합니다.")
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        gpt_layout.addWidget(info_label)
        
        layout.addWidget(gpt_group)
        
        self.tab_widget.addTab(tab, "카페 설정")
    
    
    def create_execution_tab(self):
        """작업 실행 탭"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 실행 설정 그룹
        settings_group = QGroupBox("실행 설정")
        settings_layout = QGridLayout(settings_group)
        
        # 스레드 개수
        settings_layout.addWidget(QLabel("스레드 개수:"), 0, 0)
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setMinimum(1)
        self.thread_count_spin.setMaximum(5)
        self.thread_count_spin.setValue(1)
        self.thread_count_spin.setToolTip(
            "동시에 실행할 스레드 수를 설정합니다.\n"
            "• 1개: 순차 처리 (안정적)\n"
            "• 2-3개: 중간 속도 (권장)\n"
            "• 4-5개: 고속 처리 (불안정 가능)"
        )
        settings_layout.addWidget(self.thread_count_spin, 0, 1)
        
        # 🔧 레거시 답글계정당 원고 개수 설정 - 카페별 탭에서 개별 설정으로 이동됨
        # settings_layout.addWidget(QLabel("답글계정당 원고 개수:"), 1, 0)
        self.account_limit_spin = QSpinBox()
        self.account_limit_spin.setMinimum(1)
        self.account_limit_spin.setMaximum(20)
        self.account_limit_spin.setValue(3)  # 🔧 기본값을 3으로 변경 (카페별 설정과 일치)
        self.account_limit_spin.setSuffix("개")
        self.account_limit_spin.setToolTip(
            "⚠️ 레거시 설정입니다. 실제로는 각 카페별 탭에서 개별 설정됩니다.\n"
            "• 현재는 각 카페별 탭의 '아이디당 원고 개수' 설정이 우선 적용됩니다."
        )
        self.account_limit_spin.valueChanged.connect(self.on_account_limit_changed)
        # settings_layout.addWidget(self.account_limit_spin, 1, 1)  # UI에서 숨김
        
        # 매칭 현황 표시
        settings_layout.addWidget(QLabel("매칭된 작업:"), 2, 0)
        self.work_count_label = QLabel("매칭 후 확인 가능")
        self.work_count_label.setStyleSheet("color: #666; font-style: italic;")
        settings_layout.addWidget(self.work_count_label, 2, 1)
        
        layout.addWidget(settings_group)
        
        # 컨트롤 버튼
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 작업 시작")
        self.start_btn.clicked.connect(self.start_work)
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }")
        
        self.stop_btn = QPushButton("⏹️ 작업 중지")
        self.stop_btn.clicked.connect(self.stop_work)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 10px; }")
        
        self.reset_btn = QPushButton("🔄 전체 초기화")
        self.reset_btn.clicked.connect(self.reset_all)
        self.reset_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 10px; }")
        self.reset_btn.setToolTip(
            "프로그램 상태를 완전히 초기화합니다:\n"
            "• 작업 진행 상태 초기화\n"
            "• 결과 목록 초기화\n"
            "• 차단된 계정 목록 초기화\n"
            "• 계정 사용 횟수 초기화\n"
            "• Chrome 프로세스 강제 종료\n"
            "• 로그 텍스트 초기화"
        )
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.reset_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 진행률
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 상태 라벨
        self.status_label = QLabel("대기 중...")
        layout.addWidget(self.status_label)
        
        # 로그 영역 - 동적 생성을 위한 컨테이너
        self.log_group = QGroupBox("실행 로그")
        self.log_layout = QVBoxLayout(self.log_group)
        
        # 로그 위젯들을 담을 딕셔너리
        self.log_widgets = {}
        
        # 기본 로그창 (스레드 수 결정 전까지 사용)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_layout.addWidget(self.log_text)
        
        layout.addWidget(self.log_group)
        
        self.tab_widget.addTab(tab, "작업 실행")
    
    def create_result_tab(self):
        """결과 확인 탭"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 결과 저장 버튼
        save_layout = QHBoxLayout()
        self.save_result_btn = QPushButton("📊 결과 저장 (CSV)")
        self.save_result_btn.clicked.connect(self.save_results)
        self.save_result_btn.setEnabled(False)
        
        save_layout.addWidget(self.save_result_btn)
        save_layout.addStretch()
        layout.addLayout(save_layout)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)  # 열 추가
        self.result_table.setHorizontalHeaderLabels([
            "폴더명", "답글아이디", "답글아이디로그인아이피", "답글등록상태", 
            "답글URL", "원본URL", "댓글상황", "댓글차단"
        ])
        
        # 열 너비 설정
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # 폴더명
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)       # 답글아이디
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)       # 아이피
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)       # 등록상태
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)     # 답글URL
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)     # 원본URL
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)       # 댓글상황
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)       # 댓글차단
        
        # 고정 너비 설정
        self.result_table.setColumnWidth(1, 100)  # 답글아이디
        self.result_table.setColumnWidth(2, 120)  # 아이피
        self.result_table.setColumnWidth(3, 80)   # 등록상태
        self.result_table.setColumnWidth(6, 100)  # 댓글상황
        self.result_table.setColumnWidth(7, 80)   # 댓글차단
        
        # 📋 복사 기능 추가
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectItems)  # 개별 셀 선택
        self.result_table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 다중 선택 가능
        self.result_table.setSortingEnabled(True)  # 정렬 기능
        
        # 우클릭 메뉴
        self.result_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self.show_table_context_menu)
        
        # 키보드 단축키
        self.result_table.keyPressEvent = self.table_key_press_event
        
        layout.addWidget(self.result_table)
        
        self.tab_widget.addTab(tab, "작업 결과")
        
        # 🆕 아이디 관리 탭 추가
        self.setup_account_management_tab()
    
    def setup_account_management_tab(self):
        """아이디 관리 탭 설정"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 상단 요약 정보
        summary_layout = QHBoxLayout()
        
        self.total_accounts_label = QLabel("총 아이디: 0개")
        self.active_accounts_label = QLabel("활성: 0개")
        self.blocked_accounts_label = QLabel("차단: 0개")
        self.today_used_label = QLabel("오늘 사용: 0개")
        
        summary_layout.addWidget(self.total_accounts_label)
        summary_layout.addWidget(QLabel(" | "))
        summary_layout.addWidget(self.active_accounts_label)
        summary_layout.addWidget(QLabel(" | "))
        summary_layout.addWidget(self.blocked_accounts_label)
        summary_layout.addWidget(QLabel(" | "))
        summary_layout.addWidget(self.today_used_label)
        summary_layout.addStretch()
        
        layout.addLayout(summary_layout)
        
        # 아이디 관리 테이블
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(8)
        self.account_table.setHorizontalHeaderLabels([
            "답글 아이디", "카페", "할당작업", "완료", "실패", "진행률", "상태", "마지막 사용"
        ])
        
        # 테이블 설정
        header = self.account_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 아이디
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 카페
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 할당작업
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 완료
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 실패
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 진행률
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 상태
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 마지막 사용
        
        self.account_table.setAlternatingRowColors(True)
        self.account_table.setSortingEnabled(True)
        
        layout.addWidget(self.account_table)
        
        # 하단 버튼
        button_layout = QHBoxLayout()
        
        self.save_account_btn = QPushButton("💾 저장하기")
        self.save_account_btn.clicked.connect(self.save_account_results)
        
        self.export_account_btn = QPushButton("📊 통계 내보내기")
        self.export_account_btn.clicked.connect(self.export_account_stats)
        
        self.refresh_account_btn = QPushButton("🔄 새로고침")
        self.refresh_account_btn.clicked.connect(self.refresh_account_stats)
        
        button_layout.addWidget(self.save_account_btn)
        button_layout.addWidget(self.export_account_btn)
        button_layout.addWidget(self.refresh_account_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.tab_widget.addTab(tab, "아이디 관리")
        
        # 아이디별 통계 저장용
        self.account_stats = {}
    
    def table_key_press_event(self, event):
        """테이블 키보드 이벤트 처리"""
        if event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            # Ctrl+A: 전체 선택
            self.result_table.selectAll()
        elif event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            # Ctrl+C: 복사
            self.copy_table_selection()
        else:
            # 기본 이벤트 처리
            QTableWidget.keyPressEvent(self.result_table, event)
    
    def show_table_context_menu(self, position):
        """테이블 우클릭 메뉴"""
        menu = QMenu()
        
        copy_action = menu.addAction("📋 복사 (Ctrl+C)")
        copy_action.triggered.connect(self.copy_table_selection)
        
        select_all_action = menu.addAction("🔲 전체 선택 (Ctrl+A)")
        select_all_action.triggered.connect(self.result_table.selectAll)
        
        menu.addSeparator()
        
        export_action = menu.addAction("📊 선택된 행 CSV 저장")
        export_action.triggered.connect(self.export_selected_rows)
        
        menu.addSeparator()
        
        # 현재 상태 정보
        result_count = len(self.results)
        table_rows = self.result_table.rowCount()
        status_text = f"💾 저장 가능한 결과: {result_count}개 | 테이블 행: {table_rows}개"
        status_action = menu.addAction(status_text)
        status_action.setEnabled(False)  # 클릭 불가 (정보 표시용)
        
        if result_count > 0:
            force_save_action = menu.addAction("💾 강제 저장하기")
            force_save_action.triggered.connect(self.force_save_results)
        
        menu.exec_(self.result_table.mapToGlobal(position))
    
    def copy_table_selection(self):
        """선택된 테이블 내용을 클립보드에 복사"""
        selection = self.result_table.selectionModel().selectedIndexes()
        if not selection:
            QMessageBox.warning(self, "경고", "복사할 셀을 선택해주세요.")
            return
        
        # 선택된 셀들을 행/열로 정리
        selected_data = {}
        for index in selection:
            row = index.row()
            col = index.column()
            if row not in selected_data:
                selected_data[row] = {}
            item = self.result_table.item(row, col)
            selected_data[row][col] = item.text() if item else ""
        
        # 최소/최대 행과 열 찾기
        if not selected_data:
            return
            
        min_row = min(selected_data.keys())
        max_row = max(selected_data.keys())
        min_col = min(min(row_data.keys()) for row_data in selected_data.values())
        max_col = max(max(row_data.keys()) for row_data in selected_data.values())
        
        # 데이터 구성
        copied_data = []
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                if row in selected_data and col in selected_data[row]:
                    row_data.append(selected_data[row][col])
                else:
                    row_data.append("")  # 빈 셀
            copied_data.append("\t".join(row_data))
        
        # 클립보드에 복사
        clipboard_text = "\n".join(copied_data)
        QApplication.clipboard().setText(clipboard_text)
        
        # 성공 메시지
        cell_count = len(selection)
        self.log_message(f"📋 {cell_count}개 셀이 클립보드에 복사되었습니다")
        
        # 상태바에 잠시 표시
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"📋 {cell_count}개 셀 복사 완료", 2000)
    
    def export_selected_rows(self):
        """선택된 셀들을 CSV로 내보내기 (완전한 행만)"""
        selection = self.result_table.selectionModel().selectedIndexes()
        if not selection:
            QMessageBox.warning(self, "경고", "내보낼 셀을 선택해주세요.")
            return
        
        # 완전한 행들만 찾기 (모든 컬럼이 선택된 행)
        selected_rows = set()
        col_count = self.result_table.columnCount()
        
        # 각 행별로 선택된 컬럼 수 계산
        row_col_count = {}
        for index in selection:
            row = index.row()
            if row not in row_col_count:
                row_col_count[row] = 0
            row_col_count[row] += 1
        
        # 모든 컬럼이 선택된 행들만 추출
        for row, count in row_col_count.items():
            if count == col_count:
                selected_rows.add(row)
        
        if not selected_rows:
            QMessageBox.warning(self, "경고", "완전한 행이 선택되지 않았습니다.\n전체 행을 선택하려면 행 번호를 클릭하세요.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "선택 항목 저장", f"선택된_결과_{timestamp}.csv", 
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                # 선택된 행들의 데이터 수집
                selected_data = []
                for row in sorted(selected_rows):
                    row_data = {}
                    for col in range(col_count):
                        header = self.result_table.horizontalHeaderItem(col).text()
                        item = self.result_table.item(row, col)
                        row_data[header] = item.text() if item else ""
                    selected_data.append(row_data)
                
                # CSV로 저장
                df = pd.DataFrame(selected_data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                QMessageBox.information(self, "완료", f"선택된 {len(selected_rows)}개 행이 저장되었습니다:\n{file_path}")
                self.log_message(f"💾 선택된 {len(selected_rows)}개 행 저장 완료: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 실패:\n{str(e)}")
    
    def setup_style(self):
        """스타일 설정"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e1e1e1;
                border: 1px solid #c0c0c0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4a90e2;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #e1e1e1;
                border: 1px solid #adadad;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d1d1d1;
            }
            QPushButton:pressed {
                background-color: #c1c1c1;
            }
        """)
    
    def load_cafe_folders(self):
        """여러 카페 폴더들 선택"""
        # 상위 폴더 선택 (카페 폴더들이 들어있는 폴더)
        parent_folder = QFileDialog.getExistingDirectory(
            self, "카페 폴더들이 들어있는 상위 폴더 선택", ""
        )
        
        if parent_folder:
            try:
                # 하위 폴더들 중 유효한 카페 폴더들 찾기
                cafe_folders = []
                invalid_folders = []
                
                for item in os.listdir(parent_folder):
                    item_path = os.path.join(parent_folder, item)
                    if os.path.isdir(item_path):
                        # 🆕 카페 폴더 유효성 검사 (urls.txt 제거)
                        accounts_file = os.path.join(item_path, "accounts.xlsx")
                        scripts_folder = os.path.join(item_path, "원고")
                        
                        if (os.path.exists(accounts_file) and 
                            os.path.exists(scripts_folder)):
                            cafe_folders.append(item_path)
                        else:
                            invalid_folders.append(item)
                
                if not cafe_folders:
                    QMessageBox.warning(self, "경고", 
                        "유효한 카페 폴더를 찾을 수 없습니다.\n\n"
                        "각 카페 폴더에는 다음이 있어야 합니다:\n"
                        "- accounts.xlsx (C열에 수정할 URL 포함)\n- 원고 폴더")
                    return
                
                # 유효한 카페 폴더들 저장
                self.cafe_folders = cafe_folders
                self.current_cafe_index = 0
                
                # UI 업데이트
                self.cafe_folder_label.setText(f"선택된 카페: {len(cafe_folders)}개")
                
                # 카페 목록 표시
                self.cafe_list_widget.clear()
                for folder in cafe_folders:
                    cafe_name = os.path.basename(folder)
                    self.cafe_list_widget.addItem(f"📁 {cafe_name}")
                
                # 🆕 카페별 개별 탭 생성
                self.create_cafe_tabs(cafe_folders)
                
                # 첫 번째 카페 폴더 로드 (미리보기용)
                self.load_single_cafe_folder(cafe_folders[0])
                
                self.log_message(f"✅ {len(cafe_folders)}개 카페 폴더 선택 완료")
                self.log_message(f"🏢 카페별 개별 탭 {len(cafe_folders)}개 생성됨")
                
                if invalid_folders:
                    self.log_message(f"⚠️ 유효하지 않은 폴더들: {', '.join(invalid_folders)}")
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"카페 폴더들 로드 실패:\n{str(e)}")
                self.log_message(f"❌ 카페 폴더들 로드 실패: {str(e)}")
    
    def create_cafe_tabs(self, cafe_folders):
        """🏢 카페별 개별 탭 생성"""
        try:
            # 기존 카페 탭들 제거 (매칭 상태 탭 이후의 탭들)
            self.remove_existing_cafe_tabs()
            
            # 각 카페별로 탭 생성
            for i, folder_path in enumerate(cafe_folders):
                cafe_name = os.path.basename(folder_path)
                
                # 카페별 데이터 초기화
                self.cafe_data[cafe_name] = {
                    'folder_path': folder_path,
                    'id_script_mapping': {},
                    'spare_accounts': [],
                    'id_comment_block_settings': {},
                    'id_url_assignments': {},
                    'url_comment_block_settings': {},
                    'urls': [],
                    'script_folders': [],
                    'reply_accounts': [],
                    'comment_accounts': [],
                    'status': 'pending'  # pending, working, completed
                }
                
                # 카페별 탭 생성
                cafe_tab = self.create_individual_cafe_tab(cafe_name, folder_path)
                
                # 탭 추가 (카페 설정 탭 바로 다음에 삽입)
                # 탭 순서: 카페 설정(0) -> 카페들(1~) -> 실행 -> 결과
                tab_index = self.tab_widget.insertTab(1 + i, cafe_tab, f"📁 {cafe_name}")
                
                # 탭 정보 저장
                self.cafe_tabs[cafe_name] = cafe_tab
                self.cafe_tab_indices[cafe_name] = tab_index
                
            self.log_message(f"🎯 카페별 개별 탭 생성 완료: {len(cafe_folders)}개")
            
        except Exception as e:
            self.log_message(f"❌ 카페 탭 생성 실패: {str(e)}")
            
    def remove_existing_cafe_tabs(self):
        """기존 카페 탭들 제거"""
        try:
            # 뒤에서부터 제거 (인덱스 변경 방지)
            for i in range(self.tab_widget.count() - 1, -1, -1):
                tab_text = self.tab_widget.tabText(i)
                if tab_text.startswith("📁") or tab_text.startswith("⚡") or tab_text.startswith("✅"):
                    self.tab_widget.removeTab(i)
            
            # 데이터 초기화
            self.cafe_tabs.clear()
            self.cafe_data.clear()
            self.cafe_tab_indices.clear()
            
        except Exception as e:
            self.log_message(f"⚠️ 기존 카페 탭 제거 중 오류: {str(e)}")
            
    def create_individual_cafe_tab(self, cafe_name, folder_path):
        """개별 카페 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 카페 정보 표시
        info_group = QGroupBox(f"{cafe_name} 매칭 상태")
        info_layout = QVBoxLayout(info_group)
        
        # 카페 경로 표시
        path_label = QLabel(f"📂 경로: {folder_path}")
        path_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        info_layout.addWidget(path_label)
        
        # 매칭 상태 표시
        status_label = QLabel("매칭 현황: 아직 매칭되지 않음")
        status_label.setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        info_layout.addWidget(status_label)
        
        # 계정 배분 현황 표시
        distribution_label = QLabel("계정 배분 현황: 매칭 후 확인 가능")
        distribution_label.setStyleSheet("color: #666; padding: 10px; background-color: #f9f9f9; border-radius: 5px; border: 1px solid #ddd;")
        info_layout.addWidget(distribution_label)
        
        layout.addWidget(info_group)
        
        # 🆕 매칭 설정 그룹 (자동 1:1 매핑 안내)
        setting_group = QGroupBox("매칭 설정")
        setting_layout = QVBoxLayout(setting_group)
        
        # 자동 매칭 안내
        auto_info_label = QLabel("🔄 자동 매핑: 계정별 URL 개수만큼 원고 자동 할당")
        auto_info_label.setStyleSheet("""
            color: #2e7d32; 
            font-weight: bold; 
            padding: 8px; 
            background-color: #e8f5e9; 
            border-radius: 5px; 
            border: 1px solid #4caf50;
        """)
        setting_layout.addWidget(auto_info_label)
        
        layout.addWidget(setting_group)
        
        # 매칭 컨트롤 버튼들
        control_group = QGroupBox("매칭 제어")
        control_layout = QHBoxLayout(control_group)
        
        # 카페 로드 버튼
        load_btn = QPushButton(f"📥 {cafe_name} 로드")
        load_btn.clicked.connect(lambda checked, name=cafe_name: self.load_individual_cafe(name))
        
        # 매칭 버튼
        mapping_btn = QPushButton("🔄 매칭 실행")
        mapping_btn.clicked.connect(lambda checked, name=cafe_name: self.execute_individual_mapping(name))
        
        # 초기화 버튼
        clear_btn = QPushButton("🗑️ 매칭 초기화")
        clear_btn.clicked.connect(lambda checked, name=cafe_name: self.clear_individual_mapping(name))
        
        control_layout.addWidget(load_btn)
        control_layout.addWidget(mapping_btn)
        control_layout.addWidget(clear_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        # ID 기준 매칭 테이블
        mapping_group = QGroupBox("ID-원고 매칭")
        mapping_layout = QVBoxLayout(mapping_group)
        
        mapping_table = QTableWidget()
        mapping_table.setColumnCount(5)
        mapping_table.setHorizontalHeaderLabels(["아이디", "매칭원고", "매칭폴더리스트", "댓글차단", "URL"])
        
        # 열 너비 설정
        header = mapping_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        mapping_table.setColumnWidth(0, 120)
        mapping_table.setColumnWidth(1, 80)
        mapping_table.setColumnWidth(2, 250)
        mapping_table.setColumnWidth(3, 80)
        
        mapping_layout.addWidget(mapping_table)
        layout.addWidget(mapping_group)
        
        # 여분아이디 관리
        spare_group = QGroupBox("여분 아이디 관리")
        spare_layout = QVBoxLayout(spare_group)
        
        spare_table = QTableWidget()
        spare_table.setColumnCount(3)
        spare_table.setHorizontalHeaderLabels(["여분 아이디", "비밀번호", "삭제"])
        spare_table.setMaximumHeight(150)
        
        spare_header = spare_table.horizontalHeader()
        spare_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        spare_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        spare_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        spare_table.setColumnWidth(1, 150)
        spare_table.setColumnWidth(2, 60)
        
        spare_layout.addWidget(spare_table)
        
        # 여분아이디 추가 버튼
        add_spare_btn = QPushButton("➕ 여분 아이디 추가")
        add_spare_btn.clicked.connect(lambda checked, name=cafe_name: self.test_button_click(f"여분아이디 추가 버튼 클릭: {name}"))
        spare_layout.addWidget(add_spare_btn)
        
        layout.addWidget(spare_group)
        
        # 위젯들을 카페 데이터에 저장 (나중에 업데이트용)
        self.cafe_data[cafe_name]['widgets'] = {
            'status_label': status_label,
            'distribution_label': distribution_label,
            'mapping_table': mapping_table,
            'spare_table': spare_table,
            'load_btn': load_btn,
            'mapping_btn': mapping_btn,
            'clear_btn': clear_btn
        }
        
        return tab
    
    def test_button_click(self, message):
        """🧪 버튼 클릭 테스트"""
        self.log_message(f"🎯 테스트: {message}")
        print(f"🎯 테스트: {message}")  # 콘솔에도 출력

    def load_individual_cafe(self, cafe_name):
        """개별 카페 로드"""
        self.log_message(f"🔄 {cafe_name} 로드 버튼 클릭됨!")
        try:
            if cafe_name not in self.cafe_data:
                self.log_message(f"❌ 카페 {cafe_name} 데이터를 찾을 수 없습니다.")
                return
                
            folder_path = self.cafe_data[cafe_name]['folder_path']
            
            # 🆕 카페 데이터 로드 (urls.txt 제거)
            accounts_file = os.path.join(folder_path, "accounts.xlsx") 
            scripts_folder = os.path.join(folder_path, "원고")
            
            # 계정 로드 (C열에서 URL도 함께 로드)
            reply_accounts, comment_accounts = self.load_accounts_from_cafe(accounts_file)
            self.cafe_data[cafe_name]['reply_accounts'] = reply_accounts
            self.cafe_data[cafe_name]['comment_accounts'] = comment_accounts
            
            # 🆕 카페별로 account_rows와 account_urls 저장 (여러 카페 로드 시 혼선 방지)
            self.cafe_data[cafe_name]['account_rows'] = list(self.account_rows)  # 깊은 복사
            self.cafe_data[cafe_name]['account_urls'] = dict(self.account_urls)  # dict 복사
            
            # 🆕 계정별 URL 매핑에서 URL 목록 생성 (리스트 기반)
            account_urls = []
            for urls in self.account_urls.values():
                if urls:  # URL 리스트가 있는 경우
                    account_urls.extend(urls)
            self.cafe_data[cafe_name]['urls'] = account_urls  # 호환성을 위해 유지
            
            # 원고 로드
            script_folders = self.load_scripts_from_cafe(scripts_folder)
            self.cafe_data[cafe_name]['script_folders'] = script_folders
            
            self.log_message(f"✅ {cafe_name} 로드 완료:")
            self.log_message(f"   🔗 계정별 URL: {len(account_urls)}개")
            self.log_message(f"   👥 답글계정: {len(reply_accounts)}개")
            self.log_message(f"   💬 댓글계정: {len(comment_accounts)}개")
            self.log_message(f"   📝 원고폴더: {len(script_folders)}개")
            
            # 상태 업데이트
            widgets = self.cafe_data[cafe_name]['widgets']
            widgets['status_label'].setText("매칭 현황: 데이터 로드 완료 - 매칭 실행 대기")
            widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #e8f5e8; border-radius: 3px;")
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 로드 실패: {str(e)}")

    def populate_all_tasks_preview(self, cafe_name):
        """전체 작업 목록을 미리 생성하여 결과 테이블에 표시 (누적 추가 방식)"""
        try:
            if cafe_name not in self.cafe_data:
                return
                
            cafe_data = self.cafe_data[cafe_name]
            
            # 🔥 매칭된 ID-스크립트 조합으로만 작업 생성 (실제 할당된 것만)
            id_script_mapping = cafe_data.get('id_script_mapping', {})
            
            if not id_script_mapping:
                self.log_message(f"⚠️ {cafe_name}: 매칭 실행을 먼저 해주세요.")
                return
            
            # 🔥 기존 이 카페의 미리보기 행들 제거 (다른 카페는 유지)
            self.remove_cafe_preview_rows(cafe_name)
            
            task_count = 0
            # 🔥 기존 작업 개수를 세어서 연속된 번호 유지
            task_number = len([r for r in self.results if r.get('is_preview', False)]) + 1
            self.log_message(f"📋 {cafe_name} 전체 작업 목록 생성 중... (시작 번호: {task_number})")
            
            # 폴더명 카운트를 위한 딕셔너리
            folder_count = {}
            
            # 실제 매칭된 작업들만 미리 표시
            for account_id, mapping_data in id_script_mapping.items():
                assigned_url = mapping_data.get('assigned_url', '')
                scripts = mapping_data.get('scripts', [])
                
                for script_index, script_folder in enumerate(scripts):
                    script_name = os.path.basename(script_folder)
                    
                    # 폴더명 중복 처리
                    base_folder_name = extract_keyword_from_folder_name(script_name)
                    count = folder_count.get(base_folder_name, 0) + 1
                    folder_count[base_folder_name] = count
                    
                    # 2번째부터 번호 추가
                    if count > 1:
                        folder_name = f"{base_folder_name}({count})"
                    else:
                        folder_name = base_folder_name
                    
                    # 대기중 상태의 결과 데이터 생성
                    preview_result = {
                        '폴더명': folder_name,  # 🔥 중복 방지를 위해 번호 추가
                        '답글아이디': '⏳ 대기중',
                        '답글아이디로그인아이피': '-',
                        '답글등록상태': '⏳',
                        '답글URL': '대기중',
                        '원본URL': assigned_url,
                        '댓글상황': '미작성',
                        '댓글차단': '⏳ 대기중',
                        '스크립트': script_name,
                        'account_id': account_id,
                        'script_index': script_index,
                        'script_folder': script_folder,  # 실제 스크립트 폴더 경로
                        'cafe_name': cafe_name,  # 카페명은 별도 저장
                        'task_number': task_number,  # 작업 순서 번호 (내부 사용)
                        'is_preview': True  # 미리 생성된 행임을 표시
                    }
                    
                    # 결과 배열에 추가
                    self.results.append(preview_result)
                    
                    # 테이블에 행 추가
                    row = self.result_table.rowCount()
                    self.result_table.insertRow(row)
                    
                    self.result_table.setItem(row, 0, QTableWidgetItem(preview_result['폴더명']))
                    self.result_table.setItem(row, 1, QTableWidgetItem(preview_result['답글아이디']))
                    self.result_table.setItem(row, 2, QTableWidgetItem(preview_result['답글아이디로그인아이피']))
                    self.result_table.setItem(row, 3, QTableWidgetItem(preview_result['답글등록상태']))
                    self.result_table.setItem(row, 4, QTableWidgetItem(preview_result['답글URL']))
                    self.result_table.setItem(row, 5, QTableWidgetItem(preview_result['원본URL']))
                    self.result_table.setItem(row, 6, QTableWidgetItem(preview_result['댓글상황']))
                    self.result_table.setItem(row, 7, QTableWidgetItem(preview_result['댓글차단']))
                    self.result_table.setItem(row, 8, QTableWidgetItem(preview_result['스크립트']))
                    
                    task_count += 1
                    task_number += 1  # 🔥 다음 작업 번호
            
            self.log_message(f"✅ {cafe_name} 전체 작업 목록 생성 완료: {task_count}개 작업")
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 작업 목록 생성 실패: {str(e)}")

    def remove_cafe_preview_rows(self, cafe_name):
        """특정 카페의 미리보기 행들만 제거 (다른 카페는 유지)"""
        try:
            # 뒤에서부터 제거 (인덱스가 변하지 않도록)
            rows_to_remove = []
            
            for i, result in enumerate(self.results):
                if (result.get('is_preview', False) and 
                    result.get('cafe_name', '') == cafe_name):
                    rows_to_remove.append(i)
            
            # 뒤에서부터 제거
            for row_index in reversed(rows_to_remove):
                # results 리스트에서 제거
                self.results.pop(row_index)
                # 테이블에서 제거
                self.result_table.removeRow(row_index)
            
            if rows_to_remove:
                self.log_message(f"🗑️ {cafe_name} 기존 미리보기 {len(rows_to_remove)}개 행 제거됨")
                
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 미리보기 행 제거 실패: {str(e)}")

    def execute_individual_mapping(self, cafe_name):
        """개별 카페 매칭 실행"""
        self.log_message(f"🔄 {cafe_name} 매칭 실행 버튼 클릭됨!")
        try:
            if cafe_name not in self.cafe_data:
                self.log_message(f"❌ 카페 {cafe_name} 데이터를 찾을 수 없습니다.")
                return
                
            cafe_data = self.cafe_data[cafe_name]
            
            # 데이터 확인
            if not cafe_data['urls'] or not cafe_data['reply_accounts'] or not cafe_data['script_folders']:
                self.log_message(f"⚠️ {cafe_name}: 먼저 카페 데이터를 로드해주세요.")
                return
            
            # 매칭 초기화
            cafe_data['id_script_mapping'].clear()
            cafe_data['id_url_assignments'].clear() 
            cafe_data['id_comment_block_settings'].clear()
            cafe_data['spare_accounts'].clear()
            
            self.log_message(f"🔄 {cafe_name} 매칭 시작...")
            
            # 🆕 1:1 자동 매핑 (아이디당 원고 개수 설정 제거)
            
            urls = cafe_data['urls']
            reply_accounts = cafe_data['reply_accounts']
            script_folders = cafe_data['script_folders']
            
            # 아이디별 원고 배분
            total_scripts = len(script_folders)
            total_accounts = len(reply_accounts)
            
            if total_accounts == 0:
                self.log_message(f"❌ {cafe_name}: 사용 가능한 계정이 없습니다.")
                return
            
            self.log_message(f"📊 {cafe_name} 행 기반 매핑: 엑셀 각 행을 개별 작업으로 처리")
            
            # 🆕 행 기반 매핑 로직 (각 엑셀 행을 개별 작업으로 처리)
            used_accounts = []
            spare_accounts = []
            script_index = 0
            
            # 🔥 엑셀 행 정보 확인
            account_rows = self.account_rows
            self.log_message(f"📋 {cafe_name} 엑셀 행 정보: 총 {len(account_rows)}행")
            self.log_message(f"📝 사용 가능한 원고: 총 {total_scripts}개")
            
            # 원고 목록 출력
            for idx, script_folder in enumerate(script_folders):
                script_name = os.path.basename(script_folder)
                self.log_message(f"   원고 {idx+1}: {script_name}")
            total_rows = len(account_rows)
            
            self.log_message(f"📊 엑셀 행 기반 매핑: 총 {total_rows}개 행")
            
            # 각 엑셀 행을 개별 작업으로 처리
            for row_idx, row_data in enumerate(account_rows):
                account_id = row_data['account_id']
                account_pw = row_data['password']
                account_url = row_data['url']
                
                self.log_message(f"🔍 행{row_idx+1} 처리: {account_id}, URL={account_url[:30] if account_url else '없음'}...")
                
                if account_url:  # URL이 있는 행만 처리
                    if script_index < total_scripts:
                        # 원고 할당
                        scripts_for_this_row = [script_folders[script_index]]
                        script_name = os.path.basename(scripts_for_this_row[0])
                        self.log_message(f"✅ 행{row_idx+1} {account_id}: 원고 {script_index+1}번({script_name}) 할당")
                        
                        # 매칭 데이터 저장 (행별로 고유 키 생성)
                        unique_key = f"{account_id}_row{row_idx+1}"
                        cafe_data['id_script_mapping'][unique_key] = {
                            'scripts': scripts_for_this_row,
                            'keywords': [extract_keyword_from_folder_name(script_name)],
                            'block_comments': True,
                            'assigned_url': account_url,
                            'account_id': account_id,  # 원본 계정 ID 저장
                            'row_index': row_idx
                        }
                        
                        used_accounts.append((account_id, account_pw))
                        script_index += 1
                    else:
                        # 원고 부족
                        self.log_message(f"⚠️ 행{row_idx+1} {account_id}: 원고 부족 - 여분 풀로 이동")
                        spare_accounts.append((account_id, account_pw))
                else:
                    # URL 없음
                    self.log_message(f"⚠️ 행{row_idx+1} {account_id}: URL 없음 - 여분 풀로 이동")
                    spare_accounts.append((account_id, account_pw))

                    
            # 여분 계정들 저장
            cafe_data['spare_accounts'] = spare_accounts
            
            # 🆕 행 기반 매핑에서 남은 원고 체크
            used_scripts = script_index
            if used_scripts < total_scripts:
                remaining_scripts = total_scripts - used_scripts
                self.log_message(f"⚠️ {cafe_name}: {remaining_scripts}개 원고가 남았습니다 (URL 있는 행 부족)")
            
            if spare_accounts:
                spare_account_names = [acc[0] for acc in spare_accounts]
                self.log_message(f"🆘 {cafe_name}: {len(spare_accounts)}개 아이디를 여분 풀로 이동: {spare_account_names}")
            
            self.log_message(f"📊 {cafe_name} 매칭 결과: {used_scripts}개 작업 생성, {len(spare_accounts)}개 여분")
            
            # 테이블 업데이트
            self.update_individual_cafe_table(cafe_name)
            
            # 상태 업데이트
            total_mappings = len(cafe_data['id_script_mapping'])
            widgets = cafe_data['widgets']
            widgets['status_label'].setText(f"매칭 현황: {total_mappings}개 계정 매칭 완료")
            widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #e8f4fd; border-radius: 3px;")
            
            # 배분 현황 업데이트
            distribution_text = f"총 {total_scripts}개 원고 → {total_mappings}개 계정에 배분"
            if cafe_data['spare_accounts']:
                distribution_text += f" (여분: {len(cafe_data['spare_accounts'])}개)"
            widgets['distribution_label'].setText(distribution_text)
            
            self.log_message(f"✅ {cafe_name} 매칭 완료: {total_mappings}개 작업")
            
            # 🔥 매칭 완료 후 작업 결과 미리보기 생성
            self.populate_all_tasks_preview(cafe_name)
            
            # 🆕 아이디 관리 탭 데이터 로드
            self.populate_account_management(cafe_name)
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 매칭 실패: {str(e)}")

    def clear_individual_mapping(self, cafe_name):
        """개별 카페 매칭 초기화"""
        self.log_message(f"🗑️ {cafe_name} 매칭 초기화 버튼 클릭됨!")
        try:
            if cafe_name not in self.cafe_data:
                self.log_message(f"❌ 카페 {cafe_name} 데이터를 찾을 수 없습니다.")
                return
                
            cafe_data = self.cafe_data[cafe_name]
            
            # 매칭 데이터 초기화
            cafe_data['id_script_mapping'].clear()
            cafe_data['id_url_assignments'].clear()
            cafe_data['id_comment_block_settings'].clear()
            cafe_data['spare_accounts'].clear()
            
            # 테이블 초기화
            widgets = cafe_data['widgets']
            widgets['mapping_table'].setRowCount(0)
            widgets['spare_table'].setRowCount(0)
            
            # 상태 업데이트
            widgets['status_label'].setText("매칭 현황: 매칭 초기화됨")
            widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
            widgets['distribution_label'].setText("계정 배분 현황: 매칭 후 확인 가능")
            
            self.log_message(f"🗑️ {cafe_name} 매칭 초기화 완료")
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 매칭 초기화 실패: {str(e)}")

    def update_individual_cafe_table(self, cafe_name):
        """개별 카페 테이블 업데이트"""
        try:
            if cafe_name not in self.cafe_data:
                return
                
            cafe_data = self.cafe_data[cafe_name]
            widgets = cafe_data['widgets']
            table = widgets['mapping_table']
            
            # 테이블 초기화
            table.setRowCount(0)
            
            # 매칭 데이터 표시
            for row, (account_id, mapping_data) in enumerate(cafe_data['id_script_mapping'].items()):
                table.insertRow(row)
                
                # 아이디
                table.setItem(row, 0, QTableWidgetItem(account_id))
                
                # 매칭원고 개수
                script_count = len(mapping_data['scripts'])
                table.setItem(row, 1, QTableWidgetItem(f"{script_count}개"))
                
                # 매칭폴더리스트
                keywords_text = ", ".join(mapping_data['keywords'][:3])  # 처음 3개만 표시
                if len(mapping_data['keywords']) > 3:
                    keywords_text += f" 외 {len(mapping_data['keywords'])-3}개"
                table.setItem(row, 2, QTableWidgetItem(keywords_text))
                
                # 댓글차단 체크박스
                checkbox = QCheckBox()
                checkbox.setChecked(mapping_data['block_comments'])
                checkbox.stateChanged.connect(
                    lambda state, aid=account_id: self.update_individual_comment_block(cafe_name, aid, state == 2)
                )
                table.setCellWidget(row, 3, checkbox)
                
                # URL
                assigned_url = mapping_data['assigned_url']
                table.setItem(row, 4, QTableWidgetItem(assigned_url))
            
            # 여분아이디 테이블 업데이트
            self.update_individual_spare_table(cafe_name)
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 테이블 업데이트 실패: {str(e)}")

    def update_individual_spare_table(self, cafe_name):
        """개별 카페 여분아이디 테이블 업데이트"""
        try:
            if cafe_name not in self.cafe_data:
                return
                
            cafe_data = self.cafe_data[cafe_name]
            widgets = cafe_data['widgets']
            spare_table = widgets['spare_table']
            
            # 테이블 초기화
            spare_table.setRowCount(0)
            
            # 여분아이디 표시
            for row, account in enumerate(cafe_data['spare_accounts']):
                spare_table.insertRow(row)
                
                # 아이디
                spare_table.setItem(row, 0, QTableWidgetItem(account[0]))
                
                # 비밀번호
                spare_table.setItem(row, 1, QTableWidgetItem(account[1]))
                
                # 삭제 버튼
                delete_btn = QPushButton("🗑️")
                delete_btn.clicked.connect(lambda _, r=row: self.remove_individual_spare_account(cafe_name, r))
                spare_table.setCellWidget(row, 2, delete_btn)
                
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 여분아이디 테이블 업데이트 실패: {str(e)}")

    def update_individual_comment_block(self, cafe_name, account_id, is_blocked):
        """개별 카페 댓글차단 설정 업데이트"""
        try:
            if cafe_name in self.cafe_data and account_id in self.cafe_data[cafe_name]['id_script_mapping']:
                self.cafe_data[cafe_name]['id_script_mapping'][account_id]['block_comments'] = is_blocked
                self.cafe_data[cafe_name]['id_comment_block_settings'][account_id] = is_blocked
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 댓글차단 설정 실패: {str(e)}")

    def add_spare_account_to_cafe(self, cafe_name):
        """개별 카페에 여분아이디 추가"""
        self.log_message(f"➕ {cafe_name} 여분아이디 추가 버튼 클릭됨!")
        # 기존 add_spare_account 로직을 카페별로 적용
        dialog = QDialog(self)
        dialog.setWindowTitle("여분 아이디 추가")
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        # 아이디 입력
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("아이디:"))
        id_input = QLineEdit()
        id_layout.addWidget(id_input)
        layout.addLayout(id_layout)
        
        # 비밀번호 입력
        pw_layout = QHBoxLayout()
        pw_layout.addWidget(QLabel("비밀번호:"))
        pw_input = QLineEdit()
        pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        pw_layout.addWidget(pw_input)
        layout.addLayout(pw_layout)
        
        # 버튼
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("추가")
        cancel_btn = QPushButton("취소")
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        def add_account():
            account_id = id_input.text().strip()
            password = pw_input.text().strip()
            
            if account_id and password:
                if cafe_name in self.cafe_data:
                    self.cafe_data[cafe_name]['spare_accounts'].append([account_id, password])
                    self.update_individual_spare_table(cafe_name)
                    self.log_message(f"➕ {cafe_name}에 여분아이디 추가: {account_id}")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "경고", "아이디와 비밀번호를 모두 입력해주세요.")
        
        ok_btn.clicked.connect(add_account)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()

    def remove_individual_spare_account(self, cafe_name, row):
        """개별 카페에서 여분아이디 제거"""
        try:
            if cafe_name in self.cafe_data and 0 <= row < len(self.cafe_data[cafe_name]['spare_accounts']):
                removed_account = self.cafe_data[cafe_name]['spare_accounts'].pop(row)
                self.update_individual_spare_table(cafe_name)
                self.log_message(f"🗑️ {cafe_name}에서 여분아이디 제거: {removed_account[0]}")
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 여분아이디 제거 실패: {str(e)}")

    def load_single_cafe_folder(self, folder_path):
        """단일 카페 폴더 로드 (내부용)"""
        try:
            # 카페 폴더 정보 저장
            self.current_cafe_folder = folder_path
            cafe_name = os.path.basename(folder_path)
            
            # 파일 경로들
            urls_file = os.path.join(folder_path, "urls.txt")
            accounts_file = os.path.join(folder_path, "accounts.xlsx")
            scripts_folder = os.path.join(folder_path, "원고")
            
            # 각 파일들 자동 로드
            self.load_urls_from_cafe(urls_file)
            self.load_accounts_from_cafe(accounts_file)
            self.load_scripts_from_cafe(scripts_folder)
            
            # 🆔 계정 사용 횟수 초기화 (새 카페 시작 시)
            self.reset_account_usage()
            
            return True
            
        except Exception as e:
            self.log_message(f"❌ 카페 폴더 로드 실패 ({cafe_name}): {str(e)}")
            return False
    
    def load_urls_from_cafe(self, urls_file):
        """카페 폴더에서 URLs 로드"""
        try:
            with open(urls_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.urls = [line.strip() for line in lines if line.strip() and 'cafe.naver.com' in line]
            
            if self.urls:
                self.url_status_label.setText(f"📄 URLs: {len(self.urls)}개 로드됨")
                self.log_message(f"✅ URL 로드 완료: {len(self.urls)}개")
            else:
                self.url_status_label.setText("📄 URLs: 유효한 URL 없음")
                QMessageBox.warning(self, "경고", "유효한 네이버 카페 URL이 없습니다.")
            
            # 로드된 URLs 반환
            return self.urls
                
        except Exception as e:
            self.url_status_label.setText("📄 URLs: 로드 실패")
            raise Exception(f"URL 파일 로드 실패: {str(e)}")
    
    def load_accounts_from_cafe(self, accounts_file):
        """카페 폴더에서 계정들 로드 (시트1: 답글계정, 시트2: 댓글계정)"""
        try:
            # 시트1: 답글계정 로드 (첫 행을 헤더로 인식)
            reply_df = pd.read_excel(accounts_file, sheet_name=0, header=0)
            
            if len(reply_df.columns) < 2:
                raise Exception("답글 계정 시트에 최소 2개의 열(ID, 패스워드)이 필요합니다.")
            
            self.reply_accounts = []
            self.account_urls = {}  # 🆕 계정별 수정할 URL 저장 (리스트로 변경)
            self.account_rows = []  # 🆕 각 행의 정보를 개별적으로 저장
            
            for _, row in reply_df.iterrows():
                id_ = str(row.iloc[0]).strip()
                pw = str(row.iloc[1]).strip()
                
                # 🆕 C열에서 수정할 URL 읽기
                edit_url = ""
                if len(reply_df.columns) >= 3:
                    edit_url = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                
                if id_ and pw and id_ != 'nan' and pw != 'nan':
                    self.reply_accounts.append((id_, pw))
                    # 🆕 각 행을 개별 작업으로 저장
                    self.account_rows.append({
                        'account_id': id_,
                        'password': pw,
                        'url': edit_url if edit_url and edit_url != 'nan' else ""
                    })
                    
                    # 🆕 계정별 수정할 URL 매핑 (여러 URL 지원) - 호환성 유지
                    if edit_url and edit_url != 'nan':
                        if id_ not in self.account_urls:
                            self.account_urls[id_] = []
                        self.account_urls[id_].append(edit_url)
            
            # 시트2: 댓글계정 로드 (첫 행을 헤더로 인식)
            comment_df = pd.read_excel(accounts_file, sheet_name=1, header=0)
            
            if len(comment_df.columns) < 2:
                raise Exception("댓글 계정 시트에 최소 2개의 열(ID, 패스워드)이 필요합니다.")
            
            self.comment_accounts = []
            for _, row in comment_df.iterrows():
                id_ = str(row.iloc[0]).strip()
                pw = str(row.iloc[1]).strip()
                
                if id_ and pw and id_ != 'nan' and pw != 'nan':
                    self.comment_accounts.append((id_, pw))
            
            # 상태 표시 업데이트
            self.reply_acc_status_label.setText(f"👤 답글 계정: {len(self.reply_accounts)}개 로드됨")
            self.comment_acc_status_label.setText(f"💬 댓글 계정: {len(self.comment_accounts)}개 로드됨")
            
            # 🔄 공용 풀 초기화 (행 기반 데이터 사용)
            with self.reply_pool_lock:
                # 🆕 각 행의 계정을 개별적으로 풀에 추가
                self.available_reply_accounts = []
                
                # 🔍 디버그: account_rows 데이터 확인
                self.log_message(f"🔍 디버그: account_rows 개수 = {len(self.account_rows)}")
                for i, row_data in enumerate(self.account_rows):
                    self.log_message(f"🔍 행{i+1}: {row_data['account_id']} / URL: {bool(row_data['url'])}")
                    if row_data['url']:  # URL이 있는 행만 답글 계정으로 사용
                        self.available_reply_accounts.append((row_data['account_id'], row_data['password']))
                        self.log_message(f"✅ 풀에 추가: {row_data['account_id']}")
                
                self.blocked_reply_accounts.clear()
                
            with self.comment_pool_lock:
                self.available_comment_accounts = self.comment_accounts.copy()
                self.blocked_comment_accounts.clear()
                self.comment_account_index = 0  # 🔄 댓글 계정 순환 인덱스
            
            # 🆔 계정 사용 횟수도 초기화
            self.reset_account_usage()
            
            self.log_message(f"✅ 답글 계정 로드 완료: {len(self.reply_accounts)}개 (풀: {len(self.available_reply_accounts)}개)")
            self.log_message(f"✅ 댓글 계정 로드 완료: {len(self.comment_accounts)}개")
            
            # 🆕 계정별 URL 매핑 정보 로그
            if self.account_urls:
                total_urls = sum(len(urls) for urls in self.account_urls.values())
                self.log_message(f"🔗 계정별 수정 URL 매핑: {len(self.account_urls)}개 계정, 총 {total_urls}개 URL")
                for account_id, edit_urls in self.account_urls.items():
                    for i, edit_url in enumerate(edit_urls):
                        self.log_message(f"   📝 {account_id}[{i+1}] → {edit_url[:50]}...")
            else:
                self.log_message(f"ℹ️ 계정별 수정 URL 없음 (기존 답글 방식 사용)")
            
            self.log_message(f"💾 계정 공용 풀 초기화 완료")
            
            # 로드된 계정들 반환
            return self.reply_accounts, self.comment_accounts
            
        except Exception as e:
            self.reply_acc_status_label.setText("👤 답글 계정: 로드 실패")
            self.comment_acc_status_label.setText("💬 댓글 계정: 로드 실패")
            raise Exception(f"계정 파일 로드 실패: {str(e)}")
    
    def load_scripts_from_cafe(self, scripts_folder):
        """카페 폴더에서 원고 폴더들 로드"""
        try:
            if not os.path.exists(scripts_folder):
                raise Exception("원고 폴더가 존재하지 않습니다.")
            
            # 원고 폴더 내의 하위 폴더들 찾기
            script_folders = []
            for item in os.listdir(scripts_folder):
                item_path = os.path.join(scripts_folder, item)
                if os.path.isdir(item_path):
                    script_folders.append(item_path)
            
            self.script_folders = script_folders
            
            if script_folders:
                self.script_status_label.setText(f"📝 원고 폴더: {len(script_folders)}개 로드됨")
                self.log_message(f"✅ 원고 폴더 로드 완료: {len(script_folders)}개")
                
                # URL-원고 자동 매칭 수행
                # if hasattr(self, 'urls') and self.urls:
                #     self.auto_mapping()
            else:
                self.script_status_label.setText("📝 원고 폴더: 하위 폴더 없음")
                self.log_message("⚠️ 원고 폴더에 하위 폴더가 없습니다.")
            
            # 로드된 원고 폴더들 반환
            return script_folders
                
        except Exception as e:
            self.script_status_label.setText("📝 원고 폴더: 로드 실패")
            raise Exception(f"원고 폴더 로드 실패: {str(e)}")

    def load_proxy_file(self):
        """프록시 파일 로드"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "프록시 파일 선택", "", "Text files (*.txt);;All files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                proxies = [line.strip() for line in lines if line.strip()]
                
                if proxies:
                    # 자동으로 반반 분리
                    mid = len(proxies) // 2
                    self.reply_proxies = proxies[:mid]
                    self.comment_proxies = proxies[mid:]
                    
                    self.proxy_file_label.setText(f"로드됨: 총 {len(proxies)}개 (답글:{len(self.reply_proxies)}, 댓글:{len(self.comment_proxies)})")
                    self.log_message(f"✅ 프록시 로드 완료: 총 {len(proxies)}개")
                else:
                    QMessageBox.warning(self, "경고", "유효한 프록시가 없습니다.")
                    
            except Exception as e:
                QMessageBox.critical(self, "오류", f"프록시 파일 로드 실패:\n{str(e)}")
    



    
    def update_id_mapping_table(self):
        """🆕 ID 기준 매칭 테이블 업데이트"""
        if not hasattr(self, 'id_script_mapping') or not self.id_script_mapping:
            self.mapping_table.setRowCount(0)
            return
        
        # 테이블 행 수 설정
        account_ids = list(self.id_script_mapping.keys())
        self.mapping_table.setRowCount(len(account_ids))
        
        for row, account_id in enumerate(account_ids):
            mapping_data = self.id_script_mapping[account_id]
            
            # 1. 아이디 표시
            self.mapping_table.setItem(row, 0, QTableWidgetItem(account_id))
            
            # 2. 매칭원고 개수 표시
            script_count = len(mapping_data['scripts'])
            script_text = f"{script_count}개" if script_count > 0 else "없음"
            self.mapping_table.setItem(row, 1, QTableWidgetItem(script_text))
            
            # 3. 매칭폴더리스트 (키워드들) 표시
            keywords = mapping_data['keywords']
            if keywords:
                # 키워드들을 쉼표로 구분해서 표시 (너무 길면 생략)
                keywords_text = ', '.join(keywords)
                if len(keywords_text) > 50:  # 너무 길면 축약
                    keywords_text = keywords_text[:47] + "..."
            else:
                keywords_text = "없음"
            self.mapping_table.setItem(row, 2, QTableWidgetItem(keywords_text))
            
            # 4. 댓글차단 체크박스
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            
            checkbox = QCheckBox()
            checkbox.setToolTip("체크하면 이 아이디의 댓글을 차단합니다")
            checkbox.setChecked(mapping_data['block_comments'])
            
            # 체크 상태 변경 시 설정 저장
            def on_id_checkbox_changed(state, current_account_id=account_id):
                is_checked = (state == 2)  # Qt.Checked
                self.update_id_comment_block_setting(current_account_id, is_checked)
            
            checkbox.stateChanged.connect(on_id_checkbox_changed)
            checkbox_layout.addWidget(checkbox)
            self.mapping_table.setCellWidget(row, 3, checkbox_widget)
            
            # 5. URL 표시
            assigned_url = mapping_data['assigned_url']
            url_text = assigned_url if assigned_url else "미배정"
            self.mapping_table.setItem(row, 4, QTableWidgetItem(url_text))
        
        # 매칭 현황 업데이트
        total_mappings = sum(len(data['scripts']) for data in self.id_script_mapping.values())
        self.update_mapping_status(total_mappings)
        
        self.log_message(f"📊 ID 기준 테이블 업데이트 완료: {len(account_ids)}개 아이디")

    def update_id_comment_block_setting(self, account_id, is_blocked):
        """아이디별 댓글 차단 설정 업데이트"""
        if account_id in self.id_script_mapping:
            self.id_script_mapping[account_id]['block_comments'] = is_blocked
            self.id_comment_block_settings[account_id] = is_blocked
            
            if is_blocked:
                self.log_message(f"🚫 댓글 차단 설정: {account_id}")
            else:
                self.log_message(f"✅ 댓글 허용 설정: {account_id}")

    def update_mapping_table(self):
        """매칭 테이블 업데이트 (카페 폴더 방식)"""
        if not hasattr(self, 'urls') or not self.urls:
            self.mapping_table.setRowCount(0)
            return
            
        self.mapping_table.setRowCount(len(self.urls))
        
        # 🔧 계정 배분 계산을 위한 준비 (기본값 사용)
        account_limit = 3  # 카페별 탭에서 개별 관리
        total_scripts_processed = 0  # 전체 처리된 원고 수
        
        total_mappings = 0
        for i, url in enumerate(self.urls):
            # URL 표시
            self.mapping_table.setItem(i, 0, QTableWidgetItem(url))
            
            # 매칭된 폴더들 표시
            mapped_folders = self.url_script_mapping.get(url, [])
            total_mappings += len(mapped_folders)
            
            if mapped_folders:
                folder_text = f"{len(mapped_folders)}개 원고"
            else:
                folder_text = "매칭 안됨"
            
            self.mapping_table.setItem(i, 1, QTableWidgetItem(folder_text))
            
            # 계정 배분 계산
            if len(mapped_folders) > 0:
                # 이 URL에 필요한 계정 범위 계산
                start_script = total_scripts_processed
                end_script = total_scripts_processed + len(mapped_folders) - 1
                
                # 시작 계정과 끝 계정 계산 (1부터 시작)
                start_account = (start_script // account_limit) + 1
                end_account = (end_script // account_limit) + 1
                
                total_scripts_processed += len(mapped_folders)
                
                if start_account == end_account:
                    account_text = f"계정{start_account}"
                else:
                    account_text = f"계정{start_account}~{end_account}"
            else:
                account_text = "-"
            
            self.mapping_table.setItem(i, 2, QTableWidgetItem(account_text))
            
            # 댓글 차단 체크박스
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            
            checkbox = QCheckBox()
            checkbox.setToolTip("체크하면 이 URL의 댓글을 차단합니다")
            # 기존 설정값 복원
            is_blocked = self.url_comment_block_settings.get(url, False)
            checkbox.setChecked(is_blocked)
            
            # 체크 상태 변경 시 설정 저장 - 람다 대신 직접 함수 생성
            def on_checkbox_changed(state, current_url=url):
                # Qt.Checked는 2, Qt.Unchecked는 0
                is_checked = (state == 2)  # Qt.Checked 값 직접 비교
                print(f"[DEBUG] 체크박스 상태 변경 - state: {state}, is_checked: {is_checked}")
                self.update_comment_block_setting(current_url, is_checked)
            
            checkbox.stateChanged.connect(on_checkbox_changed)
            
            checkbox_layout.addWidget(checkbox)
            self.mapping_table.setCellWidget(i, 3, checkbox_widget)
            
            # 설정 버튼
            btn = QPushButton("설정")
            btn.clicked.connect(lambda checked, row=i: self.setup_mapping(row))
            self.mapping_table.setCellWidget(i, 4, btn)
        
        # 매칭 현황 업데이트
        self.update_mapping_status(total_mappings)
    
    def update_comment_block_setting(self, url, is_blocked):
        """URL별 댓글 차단 설정 업데이트"""
        # 디버그 로그 추가
        print(f"[DEBUG] update_comment_block_setting 호출됨 - URL: {url}, is_blocked: {is_blocked}")
        
        self.url_comment_block_settings[url] = is_blocked
        if is_blocked:
            self.log_message(f"🚫 댓글 차단 설정: {url}")
        else:
            self.log_message(f"✅ 댓글 허용 설정: {url}")
        
        # 설정 확인 로그
        print(f"[DEBUG] 현재 차단 설정: {self.url_comment_block_settings}")
    
    def update_account_distribution_status(self):
        """계정 배분 현황 업데이트"""
        if not self.url_script_mapping:
            # self.account_distribution_label.setText("계정 배분 현황: 매칭 후 확인 가능")
            return
        
        account_limit = 3  # 🔧 카페별 탭에서 개별 관리
        total_scripts = sum(len(folders) for folders in self.url_script_mapping.values())
        available_accounts = len(self.reply_accounts) if hasattr(self, 'reply_accounts') else 0
        
        # URL별 필요 계정 수 계산
        url_account_needs = {}
        for url, folders in self.url_script_mapping.items():
            scripts_count = len(folders)
            if scripts_count > 0:
                accounts_needed = (scripts_count + account_limit - 1) // account_limit  # 올림 계산
                url_account_needs[url] = {
                    'scripts': scripts_count,
                    'accounts_needed': accounts_needed,
                    'account_usage': []
                }
        
        # 계정 배분 시뮬레이션
        total_scripts_processed = 0
        
        for url, needs in url_account_needs.items():
            start_script = total_scripts_processed
            end_script = total_scripts_processed + needs['scripts'] - 1
            
            # 이 URL에 사용될 계정들 계산
            for i in range(needs['scripts']):
                account_idx = (total_scripts_processed + i) // account_limit
                needs['account_usage'].append(account_idx)
            
            total_scripts_processed += needs['scripts']
        
        # 상태 텍스트 생성
        # 필요한 계정 수 계산 (마지막 원고가 사용하는 계정 번호 + 1)
        total_accounts_needed = ((total_scripts - 1) // account_limit + 1) if total_scripts > 0 else 0
        
        status_lines = [
            f"📊 계정 배분 현황:",
            f"• 총 원고: {total_scripts}개",
            f"• 계정당 제한: {account_limit}개",
            f"• 필요 계정: {total_accounts_needed}개",
            f"• 보유 계정: {available_accounts}개"
        ]
        
        if total_accounts_needed > available_accounts:
            status_lines.append(f"⚠️ 계정 {total_accounts_needed - available_accounts}개 부족!")
        else:
            status_lines.append("✅ 계정 충분!")
        
        # URL별 상세 정보 (축약)
        status_lines.append("\n📌 URL별 배분:")
        for i, (url, needs) in enumerate(url_account_needs.items()):
            if i < 3:  # 처음 3개만 표시
                account_range = f"계정{min(needs['account_usage'])+1}~{max(needs['account_usage'])+1}"
                status_lines.append(f"• URL{i+1}: {needs['scripts']}개 원고 → {account_range}")
            elif i == 3:
                status_lines.append(f"• ... 외 {len(url_account_needs)-3}개 URL")
                break
        
        # account_distribution_label 제거됨 - 매칭 상태 탭 삭제로 인해 주석 처리
        # self.account_distribution_label.setText("\n".join(status_lines))
        
        # 색상 설정
        # if total_accounts_needed > available_accounts:
        #     color_style = "color: #e74c3c; background-color: #ffe5e5;"
        # else:
        #     color_style = "color: #27ae60; background-color: #e8f8f5;"
        
        # self.account_distribution_label.setStyleSheet(
        #     f"{color_style} padding: 10px; border-radius: 5px; border: 1px solid #ddd; font-family: Consolas, monospace;"
        # )
    
    def on_account_limit_changed(self):
        """계정당 제한 변경 시 계정 배분 현황 업데이트"""
        if hasattr(self, 'url_script_mapping') and self.url_script_mapping:
            self.update_account_distribution_status()
    
    def _delayed_auto_mapping(self):
        """지연된 자동 매칭 실행"""
        # 자동 매칭 비활성화 - 수동으로만 실행
        # if self.urls and self.script_folders:
        #     self.auto_mapping()
        pass
    
    def update_mapping_status(self, total_mappings):
        """🆕 매칭 현황 상태 업데이트 (ID 기준)"""
        # ID 기준 매칭인지 확인
        if hasattr(self, 'id_script_mapping') and self.id_script_mapping:
            # ID 기준 매칭 현황
            assigned_count = len(self.id_script_mapping)
            total_accounts = len(self.reply_accounts) if hasattr(self, 'reply_accounts') else 0
            spare_count = len(self.spare_accounts) if hasattr(self, 'spare_accounts') else 0
            
            if total_mappings == 0:
                status_text = f"매칭 현황: 아직 매칭되지 않음 ❌"
                color = "#e74c3c"
            else:
                # ID별 원고 분배 상황 표시
                id_distribution = []
                for i, (account_id, data) in enumerate(self.id_script_mapping.items()):
                    if i < 3:  # 처음 3개만 표시
                        id_distribution.append(f"{account_id}:{len(data['scripts'])}개")
                    elif i == 3:
                        remaining_count = len(self.id_script_mapping) - 3
                        id_distribution.append(f"외 {remaining_count}개")
                        break
                
                distribution_text = ", ".join(id_distribution)
                status_text = f"✅ ID 기준 매칭 완료: 총 {total_mappings}개 원고 ({distribution_text})"
                
                if spare_count > 0:
                    status_text += f" | 🆘 여분 {spare_count}개"
                
                color = "#27ae60"
        else:
            # 기존 URL 기준 매칭 현황 (호환성)
            if not self.urls:
                status_text = "매칭 현황: URL을 먼저 로드해주세요"
                color = "#999"
            elif not self.script_folders:
                status_text = "매칭 현황: 원고 폴더를 먼저 선택해주세요"
                color = "#999"
            elif total_mappings == 0:
                status_text = f"매칭 현황: {len(self.urls)}개 URL 중 0개 매칭됨 ❌"
                color = "#e74c3c"
            else:
                # URL별 원고 분배 상황 표시
                url_distribution = []
                for i, (url, folders) in enumerate(self.url_script_mapping.items()):
                    if i < 3:  # 처음 3개만 표시
                        url_distribution.append(f"URL{i+1}:{len(folders)}개")
                
                if len(self.url_script_mapping) > 3:
                    url_distribution.append(f"외 {len(self.url_script_mapping)-3}개")
                
                distribution_text = ", ".join(url_distribution)
                status_text = f"매칭 현황: {len(self.urls)}개 URL에 총 {total_mappings}개 원고 배분 ({distribution_text}) ✅"
                color = "#27ae60"
        
        # mapping_status_label 제거됨 - 매칭 상태 탭 삭제로 인해 주석 처리
        # self.mapping_status_label.setText(status_text)
        # self.mapping_status_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
    
    def setup_mapping(self, row):
        """특정 URL에 대한 매칭 설정"""
        if row >= len(self.urls):
            return
        
        url = self.urls[row]
        
        # 선택 다이얼로그
        from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox, QVBoxLayout, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"원고 폴더 선택 - {url}")
        dialog.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("이 URL에 사용할 원고 폴더들을 선택하세요 (다중 선택 가능):"))
        
        folder_list = QListWidget()
        folder_list.setSelectionMode(QListWidget.MultiSelection)
        
        for folder in self.script_folders:
            folder_list.addItem(extract_keyword_from_folder_name(os.path.basename(folder)))
        
        # 기존 선택 복원
        current_mapping = self.url_script_mapping.get(url, [])
        for i, folder in enumerate(self.script_folders):
            if folder in current_mapping:
                folder_list.item(i).setSelected(True)
        
        layout.addWidget(folder_list)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            # 선택된 폴더들 저장
            selected_folders = []
            for i in range(folder_list.count()):
                if folder_list.item(i).isSelected():
                    selected_folders.append(self.script_folders[i])
            
            self.url_script_mapping[url] = selected_folders
            self.update_mapping_table()
            self.log_message(f"✅ {url}에 {len(selected_folders)}개 원고 폴더 매칭 완료")
    
    def auto_mapping(self):
        """🆕 ID 기준 자동 매칭 - 아이디별 원고 배분"""
        if not self.reply_accounts or not self.script_folders:
            QMessageBox.warning(self, "경고", "답글 계정과 원고 폴더를 모두 로드해주세요.")
            return
        
        # 중복 실행 방지
        if hasattr(self, '_mapping_in_progress') and self._mapping_in_progress:
            return
        
        self._mapping_in_progress = True
        
        # 기존 매핑 초기화
        self.id_script_mapping.clear()
        self.id_url_assignments.clear()
        self.id_comment_block_settings.clear()
        
        # 🆕 여분 아이디 완전 초기화 (UI 즉시 반영)
        self.spare_accounts.clear()
        self.update_spare_table()  # 여분아이디 테이블 즉시 업데이트
        self.log_message("🗑️ 여분아이디 초기화 완료 - 새로운 매칭 시작")
        
        # 🔧 설정값 가져오기 (기본값 3개 사용 - 카페별 설정은 각 탭에서 개별 관리)
        account_limit = 3  # 카페별 탭에서 개별 설정되므로 여기서는 기본값만
        
        # 원고 폴더 중복 제거
        unique_script_folders = list(dict.fromkeys(self.script_folders))
        self.script_folders = unique_script_folders
        
        # 아이디별 원고 배정
        script_index = 0
        total_scripts = len(self.script_folders)
        
        for account_idx, account in enumerate(self.reply_accounts):
            account_id = account[0]  # 아이디 추출
            
            # 이 아이디에 배정할 원고들
            assigned_scripts = []
            assigned_keywords = []
            
            # account_limit 개수만큼 원고 배정
            for i in range(account_limit):
                if script_index < total_scripts:
                    folder_path = self.script_folders[script_index]
                    folder_name = os.path.basename(folder_path)
                    keyword = extract_keyword_from_folder_name(folder_name)
                    
                    assigned_scripts.append(folder_path)
                    assigned_keywords.append(keyword)
                    script_index += 1
            
            # 🆕 원고를 실제로 배정받은 아이디만 매핑에 추가
            if assigned_scripts:  # 원고가 있는 경우만
                # URL 순서대로 배정
                assigned_url = self.urls[account_idx % len(self.urls)] if self.urls else ""
                
                # ID별 매핑 저장
                self.id_script_mapping[account_id] = {
                    'scripts': assigned_scripts,
                    'keywords': assigned_keywords,
                    'block_comments': True,  # 🔧 기본값을 켜짐으로 변경
                    'assigned_url': assigned_url
                }
                
                self.id_url_assignments[account_id] = assigned_url
                self.id_comment_block_settings[account_id] = True
        
        # 테이블 업데이트
        self.update_id_mapping_table()
        
        # 결과 로그
        total_assigned = sum(len(data['scripts']) for data in self.id_script_mapping.values())
        accounts_used = len(self.id_script_mapping)
        
        self.log_message(f"✅ ID 기준 자동 매칭 완료:")
        self.log_message(f"   • {accounts_used}개 아이디에 총 {total_assigned}개 원고 배정")
        self.log_message(f"   • 아이디당 최대 {account_limit}개 원고")
        
        if script_index < total_scripts:
            remaining = total_scripts - script_index
            self.log_message(f"   ⚠️ {remaining}개 원고 미배정 (계정 부족)")
        
        # 🆕 자동 여분 아이디 배정: 배정받지 않은 아이디들을 여분 풀로 이동
        unassigned_accounts = []
        assigned_account_ids = set(self.id_script_mapping.keys())
        
        for account in self.reply_accounts:
            account_id = account[0]
            if account_id not in assigned_account_ids:
                # 배정받지 않은 아이디는 여분 아이디로 추가
                unassigned_accounts.append(account)
                # spare_accounts에 중복 추가 방지
                if account not in self.spare_accounts:
                    self.spare_accounts.append(account)
        
        if unassigned_accounts:
            self.log_message(f"   🆘 {len(unassigned_accounts)}개 아이디를 여분 풀로 자동 이동:")
            for account in unassigned_accounts:
                self.log_message(f"      • {account[0]} (여분아이디)")
        else:
            self.log_message(f"   ℹ️ 모든 아이디에 원고 배정됨")
        
        # 🔧 여분아이디 테이블 최종 업데이트 (여유아이디가 없어도 UI 반영 보장)
        self.update_spare_table()
        self.log_message(f"📋 여분아이디 상태: {len(self.spare_accounts)}개")
        
        self._mapping_in_progress = False
    
    def clear_mapping(self):
        """🆕 매칭 초기화 (ID 기준)"""
        # 기존 매핑 초기화
        self.url_script_mapping.clear()
        
        # ID 기준 매핑 초기화
        if hasattr(self, 'id_script_mapping'):
            self.id_script_mapping.clear()
        if hasattr(self, 'id_url_assignments'):
            self.id_url_assignments.clear()
        if hasattr(self, 'id_comment_block_settings'):
            self.id_comment_block_settings.clear()
        
        # 여분아이디 초기화
        if hasattr(self, 'spare_accounts'):
            self.spare_accounts.clear()
            self.update_spare_table()
        
        # 테이블 업데이트
        if hasattr(self, 'id_script_mapping') and hasattr(self, 'update_id_mapping_table'):
            self.update_id_mapping_table()
        else:
            self.update_mapping_table()
        
        self.log_message("🗑️ ID 기준 매칭 전체 초기화 완료 (여분아이디 포함)")

    def add_spare_account(self):
        """🆕 여분 아이디 추가"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox
        from PySide6.QtCore import Qt
        
        dialog = QDialog(self, Qt.WindowFlags())
        dialog.setWindowTitle("여분 아이디 추가")
        dialog.setFixedSize(300, 150)
        
        layout = QFormLayout(dialog)
        
        # 입력 필드
        id_input = QLineEdit()
        id_input.setPlaceholderText("아이디를 입력하세요")
        password_input = QLineEdit()
        password_input.setPlaceholderText("비밀번호를 입력하세요")
        password_input.setEchoMode(QLineEdit.Password)
        
        layout.addRow("아이디:", id_input)
        layout.addRow("비밀번호:", password_input)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            account_id = id_input.text().strip()
            password = password_input.text().strip()
            
            if account_id and password:
                # spare_accounts에 추가
                self.spare_accounts.append([account_id, password])
                self.update_spare_table()
                self.log_message(f"✅ 여분 아이디 추가됨: {account_id}")
            else:
                QMessageBox.warning(self, "경고", "아이디와 비밀번호를 모두 입력해주세요.")

    def remove_spare_account(self, row):
        """🆕 여분 아이디 삭제"""
        if 0 <= row < len(self.spare_accounts):
            removed_account = self.spare_accounts.pop(row)
            self.update_spare_table()
            self.log_message(f"🗑️ 여분 아이디 삭제됨: {removed_account[0]}")

    def update_spare_table(self):
        """🆕 여분아이디 테이블 업데이트 (UI가 있을 때만)"""
        try:
            # UI가 있을 때만 테이블 업데이트
            if hasattr(self, 'spare_table') and self.spare_table:
                self.spare_table.setRowCount(len(self.spare_accounts))
                
                for row, account in enumerate(self.spare_accounts):
                    account_id, password = account
                    
                    # 자동 배정인지 확인 (reply_accounts에 원래 있었던 계정인지 체크)
                    is_auto_assigned = any(acc[0] == account_id for acc in self.reply_accounts)
                    
                    # 아이디 표시 (자동 배정 여부 표시)
                    if is_auto_assigned:
                        display_name = f"{account_id} (자동 배정)"
                        item = QTableWidgetItem(display_name)
                        from PySide6.QtCore import Qt
                        from PySide6.QtGui import QColor, QFont
                        item.setForeground(QColor("#2196F3"))  # 파란색 텍스트
                        font = QFont()
                        font.setBold(True)
                        item.setFont(font)
                    else:
                        display_name = f"{account_id} (수동 추가)"
                        item = QTableWidgetItem(display_name)
                        from PySide6.QtCore import Qt
                        from PySide6.QtGui import QColor, QFont
                        item.setForeground(QColor("#FF9800"))  # 주황색 텍스트
                        font = QFont()
                        font.setBold(True)
                        item.setFont(font)
                    
                    self.spare_table.setItem(row, 0, item)
                    
                    # 비밀번호 표시 (마스킹)
                    masked_password = "*" * len(password)
                    self.spare_table.setItem(row, 1, QTableWidgetItem(masked_password))
                    
                    # 삭제 버튼
                    delete_btn = QPushButton("삭제")
                    delete_btn.clicked.connect(lambda checked, r=row: self.remove_spare_account(r))
                    delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
                    self.spare_table.setCellWidget(row, 2, delete_btn)
            else:
                # UI가 없을 때는 로그만 출력
                self.log_message(f"ℹ️ 여분용 계정 업데이트: {len(self.spare_accounts)}개")
                
        except Exception as e:
            self.log_message(f"⚠️ 여분용 테이블 업데이트 오류: {str(e)}")
            # 오류가 발생해도 계속 진행

    def start_work(self):
        """🏢 작업 시작 (카페별 탭 순차 처리)"""
        # 🔍 로그 파일 상태 확인
        log_health = self.verify_log_file_health()
        if not log_health:
            self.log_message("⚠️ 로그 파일 상태 불량 - 콘솔 로그로 진행")
        else:
            self.log_message("✅ 로그 파일 상태 정상")
        
        # 카페 폴더들 선택 검증
        if not hasattr(self, 'cafe_folders') or not self.cafe_folders:
            QMessageBox.warning(self, "경고", "먼저 '카페 설정' 탭에서 카페 폴더들을 선택해주세요.")
            return
        
        # 카페별 탭 데이터 검증
        if not self.cafe_data:
            QMessageBox.warning(self, "경고", "카페별 탭이 생성되지 않았습니다. 카페 폴더를 다시 선택해주세요.")
            return
        
        # 전체 카페 작업 시작 확인 대화상자
        total_cafes = len(self.cafe_folders)
        cafe_names = [os.path.basename(folder) for folder in self.cafe_folders]
        cafe_list_text = "\n".join([f"   • {name}" for name in cafe_names])
        
        reply = QMessageBox.question(
            self, "전체 작업 시작 확인",
            f"🏢 전체 {total_cafes}개 카페 작업을 시작하시겠습니까?\n\n"
            f"📋 카페 목록:\n{cafe_list_text}\n\n"
            f"📊 작업 방식:\n"
            f"   • 총 카페 수: {total_cafes}개\n"
            f"   • 진행 방식: 카페별 순차 진행\n"
            f"   • 개별 확인: 없음 (자동 연속 진행)\n\n"
            f"⚠️ 작업 중 브라우저를 조작하지 마세요!\n"
            f"각 카페별 세부 정보는 로그에서 확인할 수 있습니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 🆕 저장 설정 (작업 시작 전 한 번만)
        self.setup_auto_save_settings()
        
        # 전체 카페 작업 시작
        self.total_cafes = total_cafes
        self.current_cafe_index = 0
        
        self.log_message(f"🚀 {self.total_cafes}개 카페 순차 작업 시작!")
        
        # 모든 카페 탭 상태를 대기로 설정
        self.initialize_all_cafe_tab_status()
        
        # 첫 번째 카페부터 시작
        self.process_next_cafe()

    def initialize_all_cafe_tab_status(self):
        """🎯 모든 카페 탭 상태를 초기화"""
        try:
            for cafe_name in self.cafe_data.keys():
                # 탭 제목을 대기 상태로 설정
                tab_index = self.cafe_tab_indices.get(cafe_name)
                if tab_index is not None:
                    self.tab_widget.setTabText(tab_index, f"⏳ {cafe_name}")
                
                # 카페 데이터 상태 업데이트
                self.cafe_data[cafe_name]['status'] = 'pending'
                
                # 위젯 상태 업데이트
                if 'widgets' in self.cafe_data[cafe_name]:
                    widgets = self.cafe_data[cafe_name]['widgets']
                    widgets['status_label'].setText("작업 상태: 대기 중...")
                    widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #fff3cd; border-radius: 3px;")
            
            self.log_message("🎯 모든 카페 탭이 대기 상태로 설정됨")
        except Exception as e:
            self.log_message(f"❌ 카페 탭 상태 초기화 실패: {str(e)}")

    def update_cafe_tab_status(self, cafe_name, status):
        """🏷️ 카페 탭 상태 업데이트"""
        try:
            if cafe_name not in self.cafe_data:
                return
            
            # 탭 제목 업데이트
            tab_index = self.cafe_tab_indices.get(cafe_name)
            if tab_index is not None:
                if status == 'working':
                    self.tab_widget.setTabText(tab_index, f"⚡ {cafe_name}")
                elif status == 'completed':
                    self.tab_widget.setTabText(tab_index, f"✅ {cafe_name}")
                elif status == 'failed':
                    self.tab_widget.setTabText(tab_index, f"❌ {cafe_name}")
                else:
                    self.tab_widget.setTabText(tab_index, f"⏳ {cafe_name}")
            
            # 카페 데이터 상태 업데이트
            self.cafe_data[cafe_name]['status'] = status
            
            # 위젯 상태 업데이트
            if 'widgets' in self.cafe_data[cafe_name]:
                widgets = self.cafe_data[cafe_name]['widgets']
                
                if status == 'working':
                    widgets['status_label'].setText("작업 상태: 진행 중...")
                    widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #cce5ff; border-radius: 3px;")
                elif status == 'completed':
                    widgets['status_label'].setText("작업 상태: 완료 ✅")
                    widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #d4edda; border-radius: 3px;")
                elif status == 'failed':
                    widgets['status_label'].setText("작업 상태: 실패 ❌")
                    widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #f8d7da; border-radius: 3px;")
                else:
                    widgets['status_label'].setText("작업 상태: 대기 중...")
                    widgets['status_label'].setStyleSheet("color: #333; font-weight: bold; padding: 5px; background-color: #fff3cd; border-radius: 3px;")
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 탭 상태 업데이트 실패: {str(e)}")

    def focus_on_cafe_tab(self, cafe_name):
        """🎯 해당 카페 탭으로 포커스 이동"""
        try:
            tab_index = self.cafe_tab_indices.get(cafe_name)
            if tab_index is not None:
                self.tab_widget.setCurrentIndex(tab_index)
                self.log_message(f"👀 {cafe_name} 탭으로 포커스 이동")
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 탭 포커스 이동 실패: {str(e)}")
    
    def get_actual_used_accounts(self, cafe_name):
        """🆕 카페별 실제 사용되는 계정만 추출 (여분 제외)"""
        try:
            if cafe_name not in self.cafe_data:
                return []
            
            cafe_data = self.cafe_data[cafe_name]
            
            # id_script_mapping에서 실제 매칭된 계정 ID들 추출
            used_account_ids = list(cafe_data['id_script_mapping'].keys())
            
            # 전체 계정에서 실제 사용되는 계정만 필터링
            actual_accounts = []
            for account in cafe_data['reply_accounts']:
                if account[0] in used_account_ids:
                    actual_accounts.append(account)
            
            self.log_message(f"📋 {cafe_name}: 실제 사용 계정 {len(actual_accounts)}개 추출 (여분 제외)")
            return actual_accounts
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 실제 사용 계정 추출 실패: {str(e)}")
            return []
    
    def get_cafe_account_limit(self, cafe_name):
        """🆕 카페별 계정 제한 설정값 추출"""
        try:
            if cafe_name not in self.cafe_data:
                return 5  # 기본값
            
            widgets = self.cafe_data[cafe_name]['widgets']
            account_limit = widgets['account_limit_spinbox'].value()
            
            self.log_message(f"⚙️ {cafe_name}: 계정당 원고 {account_limit}개 설정 확인")
            return account_limit
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 계정 제한 설정 추출 실패: {str(e)}")
            return 5  # 기본값

    def process_next_cafe(self):
        """🏢 다음 카페 처리 (탭별 순차 진행)"""
        if self.current_cafe_index >= len(self.cafe_folders):
            # 모든 카페 작업 완료
            self.log_message("🎉 모든 카페 작업이 완료되었습니다!")
            
            # 🆕 모든 카페 완료 시 일괄 저장 처리
            self.batch_save_all_results()
            
            # UI 상태 복원
            self.start_btn.setText("🚀 작업 시작")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        
        # 현재 카페 폴더 로드
        current_cafe_folder = self.cafe_folders[self.current_cafe_index]
        cafe_name = os.path.basename(current_cafe_folder)
        
        self.log_message("=" * 60)
        self.log_message(f"📁 [{self.current_cafe_index + 1}/{self.total_cafes}] '{cafe_name}' 폴더 작업 시작")
        self.log_message(f"📂 '{cafe_name}' 폴더의 모든 작업을 진행합니다...")
        self.log_message("=" * 60)
        
        # 🎯 현재 카페 탭 상태를 작업중으로 변경
        self.update_cafe_tab_status(cafe_name, 'working')
        
        # 🎯 해당 카페 탭으로 포커스 이동
        self.focus_on_cafe_tab(cafe_name)
        
        # 카페별 탭 데이터 사용 (기존 개별 로드 대신)
        if cafe_name in self.cafe_data:
            # 카페별 탭 데이터에서 로드
            cafe_data = self.cafe_data[cafe_name]
            
            # 기존 전역 데이터를 현재 카페 데이터로 설정
            self.urls = cafe_data.get('urls', [])
            self.script_folders = cafe_data.get('script_folders', [])
            self.reply_accounts = cafe_data.get('reply_accounts', [])
            self.comment_accounts = cafe_data.get('comment_accounts', [])
            self.id_script_mapping = cafe_data.get('id_script_mapping', {})
            self.spare_accounts = cafe_data.get('spare_accounts', [])
            self.id_comment_block_settings = cafe_data.get('id_comment_block_settings', {})
            self.id_url_assignments = cafe_data.get('id_url_assignments', {})
            self.url_comment_block_settings = cafe_data.get('url_comment_block_settings', {})
            
            # 🆕 카페별 account_rows와 account_urls 복원 (여러 카페 로드 시 혼선 방지)
            self.account_rows = cafe_data.get('account_rows', [])
            self.account_urls = cafe_data.get('account_urls', {})
            
            self.log_message(f"🔄 {cafe_name} 탭 데이터 로드 완료")
        else:
            # 기존 방식으로 폴백
            if not self.load_single_cafe_folder(current_cafe_folder):
                self.log_message(f"❌ {cafe_name} 카페 로드 실패, 다음 카페로 건너뜀")
                self.update_cafe_tab_status(cafe_name, 'failed')
                self.current_cafe_index += 1
                self.process_next_cafe()
                return
        
        # 현재 카페 유효성 검사
        if not self.validate_current_cafe(cafe_name):
            self.update_cafe_tab_status(cafe_name, 'failed')
            self.current_cafe_index += 1
            self.process_next_cafe()
            return
        
        # 현재 카페를 리스트에서 하이라이트
        if hasattr(self, 'cafe_list_widget'):
            self.cafe_list_widget.setCurrentRow(self.current_cafe_index)
        
        # 현재 카페 작업 시작
        self.start_current_cafe_work(cafe_name)
        
        # 🔥 Worker가 실제로 생성되고 시작되는지 확인
        if not hasattr(self, 'worker') or self.worker is None:
            self.log_message(f"❌ {cafe_name} Worker 생성 실패! 직접 생성 시도...")
            
            # 직접 Worker 생성 및 시작
            config = self.build_worker_config(cafe_name)
            self.worker = CafePostingWorker(config, main_window=self)
            self.worker.current_cafe_name = cafe_name
            self.worker.signals.progress.connect(self.log_message)
            self.worker.signals.progress_with_thread.connect(self.log_message_with_thread)
            self.worker.signals.status.connect(self.status_label.setText)
            self.worker.signals.finished.connect(self.work_finished)
            self.worker.signals.error.connect(self.work_error)
            self.worker.signals.result_saved.connect(self.add_result)
            self.worker.start()
            
            self.log_message(f"✅ {cafe_name} Worker 수동 생성 및 시작 완료!")
    
    def build_worker_config(self, cafe_name):
        """Worker를 위한 config 생성"""
        # 카페별 설정값 추출
        cafe_account_limit = self.get_cafe_account_limit(cafe_name)
        actual_reply_accounts = self.get_actual_used_accounts(cafe_name)
        cafe_spare_accounts = self.cafe_data.get(cafe_name, {}).get('spare_accounts', [])
        cafe_comment_accounts = self.cafe_data.get(cafe_name, {}).get('comment_accounts', [])
        
        # 🚨 카페별 계정 완전 분리 확인 로그
        reply_ids = [acc[0] for acc in actual_reply_accounts]
        comment_ids = [acc[0] for acc in cafe_comment_accounts]
        self.log_message(f"🔧 {cafe_name} Worker Config 생성:")
        self.log_message(f"   📋 답글 계정: {len(reply_ids)}개 - {', '.join(reply_ids[:5])}{'...' if len(reply_ids) > 5 else ''}")
        self.log_message(f"   💬 댓글 계정: {len(comment_ids)}개 - {', '.join(comment_ids[:5])}{'...' if len(comment_ids) > 5 else ''}")
        self.log_message(f"   🆘 여분 계정: {len(cafe_spare_accounts)}개")
        
        # 설정 구성
        config = {
            'reply_accounts': actual_reply_accounts,
            'comment_accounts': cafe_comment_accounts,
            'reply_proxies': self.reply_proxies if hasattr(self, 'reply_proxies') else [],
            'comment_proxies': self.comment_proxies if hasattr(self, 'comment_proxies') else [],
            'urls': self.urls,
            'url_script_mapping': self.url_script_mapping,
            'thread_count': self.thread_count_spin.value(),
            'account_limit': cafe_account_limit,
            'url_comment_block_settings': self.url_comment_block_settings,
            'main_window': self,
            'id_script_mapping': self.id_script_mapping,
            'spare_accounts': cafe_spare_accounts,
            'id_comment_block_settings': self.id_comment_block_settings,
            'id_url_assignments': self.id_url_assignments,
            'account_urls': self.account_urls if hasattr(self, 'account_urls') else {},
            'account_rows': self.account_rows if hasattr(self, 'account_rows') else [],
            'current_cafe_name': cafe_name  # 🔥 현재 카페명 명시적 전달
        }
        
        return config
    
    def validate_current_cafe(self, cafe_name):
        """현재 카페 유효성 검사"""
        if not hasattr(self, 'reply_accounts') or not self.reply_accounts:
            self.log_message(f"❌ {cafe_name}: 답글 계정 없음, 건너뜀")
            return False
        
        if not hasattr(self, 'comment_accounts') or not self.comment_accounts:
            self.log_message(f"❌ {cafe_name}: 댓글 계정 없음, 건너뜀")
            return False
        
        if not hasattr(self, 'urls') or not self.urls:
            self.log_message(f"❌ {cafe_name}: URL 없음, 건너뜀")
            return False
        
        # 🆕 ID 기준 매칭 또는 기존 URL 기준 매칭 확인
        has_id_mapping = hasattr(self, 'id_script_mapping') and self.id_script_mapping
        has_url_mapping = hasattr(self, 'url_script_mapping') and self.url_script_mapping
        
        if not has_id_mapping and not has_url_mapping:
            self.log_message(f"❌ {cafe_name}: 원고 매칭 없음, 건너뜀")
            return False
        
        return True
    
    def start_current_cafe_work(self, cafe_name):
        """현재 카페 작업 시작"""
        
        # 🔄 카페별 계정 완전 분리 (다른 카페 계정 차단)
        if cafe_name in self.cafe_data:
            cafe_reply_accounts = self.cafe_data[cafe_name]['reply_accounts'][:]
            cafe_comment_accounts = self.cafe_data[cafe_name]['comment_accounts'][:]
            
            with self.reply_pool_lock:
                # 🚨 완전 분리: 현재 카페 계정만 사용
                self.available_reply_accounts = cafe_reply_accounts
                self.blocked_reply_accounts = []
                
            with self.comment_pool_lock:
                # 🚨 완전 분리: 현재 카페 계정만 사용
                self.available_comment_accounts = cafe_comment_accounts
                self.blocked_comment_accounts = []
            
            # 계정 사용 횟수 초기화
            self.reset_account_usage()
            
            # 🔍 디버그: 로드된 계정 확인
            reply_ids = [acc[0] for acc in cafe_reply_accounts]
            comment_ids = [acc[0] for acc in cafe_comment_accounts]
            self.log_message(f"🔄 {cafe_name}: 계정 풀 완전 분리 완료")
            self.log_message(f"   📋 답글 계정 {len(reply_ids)}개: {', '.join(reply_ids[:5])}{'...' if len(reply_ids) > 5 else ''}")
            self.log_message(f"   💬 댓글 계정 {len(comment_ids)}개: {', '.join(comment_ids[:5])}{'...' if len(comment_ids) > 5 else ''}")
        
        # 🆕 총 작업 개수 계산 (ID 기준 우선, URL 기준 호환)
        if hasattr(self, 'id_script_mapping') and self.id_script_mapping:
            total_work_count = sum(len(data['scripts']) for data in self.id_script_mapping.values())
        else:
            total_work_count = sum(len(folders) for folders in self.url_script_mapping.values())
        
        # 작업 개수 업데이트
        self.work_count_label.setText(f"총 {total_work_count}개 작업")
        self.work_count_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        
        # 🆕 카페별 설정값 추출
        cafe_account_limit = self.get_cafe_account_limit(cafe_name)
        actual_reply_accounts = self.get_actual_used_accounts(cafe_name)
        cafe_spare_accounts = self.cafe_data.get(cafe_name, {}).get('spare_accounts', [])
        cafe_comment_accounts = self.cafe_data.get(cafe_name, {}).get('comment_accounts', [])  # 🔧 카페별 댓글 계정
        
        # 설정 구성 (카페별 맞춤 설정)
        config = {
            'reply_accounts': actual_reply_accounts,  # 🔧 실제 사용 계정만 전달
            'comment_accounts': cafe_comment_accounts,  # 🔧 카페별 댓글 계정 사용
            'reply_proxies': self.reply_proxies,
            'comment_proxies': self.comment_proxies,
            'urls': self.urls,
            'url_script_mapping': self.url_script_mapping,
            'thread_count': self.thread_count_spin.value(),
            'account_limit': cafe_account_limit,  # 🔧 카페별 설정값 사용
            'url_comment_block_settings': self.url_comment_block_settings,  # 댓글 차단 설정
            'main_window': self,  # 🆕 ID 기준 데이터 접근을 위한 메인 윈도우 참조
            # 🆕 ID 기준 데이터 직접 추가
            'id_script_mapping': getattr(self, 'id_script_mapping', {}),
            'id_comment_block_settings': getattr(self, 'id_comment_block_settings', {}),
            'spare_accounts': cafe_spare_accounts  # 🔧 카페별 여분 계정 사용
        }
        
        # 🔧 카페별 댓글 계정을 전역 변수에 설정 (get_comment_account_from_pool에서 사용하기 위해)
        self.comment_accounts = cafe_comment_accounts
        self.available_comment_accounts = cafe_comment_accounts.copy()
        self.blocked_comment_accounts.clear()  # 차단 목록 초기화
        
        self.log_message(f"⚙️ {cafe_name}: 실제 사용 계정 {len(actual_reply_accounts)}개, 여분 {len(cafe_spare_accounts)}개")
        self.log_message(f"⚙️ {cafe_name}: 댓글 계정 {len(cafe_comment_accounts)}개 (카페별 전용)")
        self.log_message(f"⚙️ {cafe_name}: 계정당 원고 {cafe_account_limit}개 설정으로 실행")
        
        # 🔍 디버깅: 실제 사용될 계정 목록 출력
        if actual_reply_accounts:
            account_names = [acc[0] for acc in actual_reply_accounts]
            self.log_message(f"📋 {cafe_name}: 실제 사용 계정 목록: {account_names}")
        else:
            self.log_message(f"⚠️ {cafe_name}: 실제 사용할 계정이 없습니다!")
        
        # 🔍 디버깅: 여분 계정 목록 출력
        if cafe_spare_accounts:
            spare_names = [acc[0] for acc in cafe_spare_accounts]
            self.log_message(f"🆘 {cafe_name}: 여분 계정 목록: {spare_names}")
        else:
            self.log_message(f"ℹ️ {cafe_name}: 여분 계정이 없습니다")
        
        # 스레드 수에 따라 로그창 동적 생성
        thread_count = config['thread_count']
        self.create_thread_log_widgets(thread_count)
        
        # 계정 필요량 계산 (카페별 설정 기준)
        account_limit = cafe_account_limit  # 카페별 설정값 사용
        accounts_needed = (total_work_count + account_limit - 1) // account_limit  # 올림 계산
        
        # 카페 작업 시작 로그 (개별 확인 없이 자동 진행)
        self.log_message(f"📝 [{cafe_name}] 카페 작업 세부사항:")
        self.log_message(f"   • 스레드 수: {config['thread_count']}개")
        self.log_message(f"   • URL 수: {len(config['urls'])}개") 
        self.log_message(f"   • 총 원고 수: {total_work_count}개")
        self.log_message(f"   • 필요 답글 계정: {accounts_needed}개")
        self.log_message(f"   • 보유 답글 계정: {len(config['reply_accounts'])}개")
        self.log_message(f"   • 댓글 계정: {len(config['comment_accounts'])}개 (카페별 전용)")
        
        # 🔍 로그 파일 상태 최종 확인
        if not self.verify_log_file_health():
            self.log_message("⚠️ 로그 파일 문제 감지 - 작업 시작 전 확인 필요")
        
        # 워커 시작
        self.worker = CafePostingWorker(config, main_window=self)
        self.worker.current_cafe_name = cafe_name  # 🔥 카페명 전달
        self.worker.signals.progress.connect(self.log_message)
        self.worker.signals.progress_with_thread.connect(self.log_message_with_thread)  # 🔥 수정: 직접 함수 연결
        self.worker.signals.status.connect(self.status_label.setText)
        self.worker.signals.finished.connect(self.work_finished)
        self.worker.signals.error.connect(self.work_error)
        self.worker.signals.result_saved.connect(self.add_result)
        
        # 🔍 주기적 로그 상태 체크 타이머 시작 (5분마다)
        if not hasattr(self, 'log_check_timer'):
            self.log_check_timer = QTimer()
            self.log_check_timer.timeout.connect(self.periodic_log_check)
            self.log_check_timer.start(300000)  # 5분 = 300,000ms
            self.log_message("⏰ 로그 상태 주기 체크 시작 (5분마다)")
        
        self.worker.start()
        
        # UI 상태 변경
        self.start_btn.setText("⏳ 작업 중...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(f"[{cafe_name}] 작업 중...")
        self.log_message(f"🚀 [{cafe_name}] 카페 작업이 시작되었습니다!")
    
    def stop_work(self):
        """작업 중지"""
        if self.worker:
            reply = QMessageBox.question(
                self, "작업 중지", "작업을 중지하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.log_message("⏹️ 작업 중지 요청됨...")
                
                # 🛑 휴식 타이머도 중지
                if hasattr(self, 'rest_timer') and self.rest_timer:
                    self.rest_timer.stop()
                    delattr(self, 'rest_timer')
                    self.log_message("⏰ 휴식 타이머 중지됨")
                
                # 📌 작업 중지 후 UI 상태 업데이트
                self.start_btn.setText("🚀 작업 시작")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.status_label.setText("작업 중지됨")
                
                # 📌 결과가 있으면 저장 버튼 활성화
                if len(self.results) > 0:
                    self.save_result_btn.setEnabled(True)
                    self.log_message(f"💾 저장 가능한 결과: {len(self.results)}개")
    
    def reset_all(self):
        """프로그램 상태 전체 초기화"""
        reply = QMessageBox.question(
            self, "전체 초기화", 
            "프로그램 상태를 완전히 초기화하시겠습니까?\n\n"
            "초기화 내용:\n"
            "• 작업 진행 상태 초기화\n"
            "• 결과 목록 초기화\n"
            "• 차단된 계정 목록 초기화\n"
            "• 계정 사용 횟수 초기화\n"
            "• Chrome 프로세스 강제 종료\n"
            "• 로그 텍스트 초기화\n\n"
            "⚠️ 이 작업은 되돌릴 수 없습니다!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.log_message("🔄 전체 초기화를 시작합니다...")
                
                # 1. 작업 중지 (진행 중인 경우)
                if self.worker and self.worker.is_running:
                    self.worker.stop()
                    self.log_message("⏹️ 진행 중인 작업 중지됨")
                
                # 2. 자동화 전용 Chrome 프로세스만 선택적 정리
                self.log_message("🎯 자동화 전용 Chrome 프로세스 선택적 정리 중...")
                try:
                    import psutil
                    killed_count = 0
                    protected_count = 0
                    
                    # 워커가 추적 중인 모든 Chrome PID 수집
                    automation_pids = []
                    if hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'thread_chrome_pids'):
                        with self.worker.drivers_lock:
                            for thread_pids in self.worker.thread_chrome_pids.values():
                                automation_pids.extend(thread_pids)
                    
                    # 추적된 PID들 정리
                    for pid in automation_pids:
                        try:
                            if psutil.pid_exists(pid):
                                process = psutil.Process(pid)
                                process.terminate()
                                killed_count += 1
                        except:
                            pass
                    
                    # 자동화 식별자가 있는 Chrome 프로세스만 추가 정리
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if 'chrome' in proc.info['name'].lower():
                                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                                
                                # 자동화 프로그램 식별자 확인
                                is_automation = any(identifier in cmdline for identifier in [
                                    'chrome_t0_', 'chrome_t1_', 'chrome_t2_', 'chrome_t3_', 'chrome_t4_',
                                    'remote-debugging-port=922', 'AutomationControlled', 
                                    'excludeSwitches', 'useAutomationExtension=false'
                                ])
                                
                                if is_automation and proc.info['pid'] not in automation_pids:
                                    proc.terminate()
                                    killed_count += 1
                                elif not is_automation:
                                    protected_count += 1
                        except:
                            continue
                    
                    self.log_message(f"✅ 선택적 Chrome 정리 완료 (자동화: {killed_count}개 종료, 사용자: {protected_count}개 보호)")
                except Exception as e:
                    self.log_message(f"⚠️ Chrome 프로세스 정리 중 오류: {str(e)}")
                
                # 3. 계정 풀 상태 초기화
                if hasattr(self, 'reply_pool_lock'):
                    with self.reply_pool_lock:
                        self.blocked_reply_accounts.clear()
                        if hasattr(self, 'reply_accounts'):
                            self.available_reply_accounts = self.reply_accounts.copy()
                
                if hasattr(self, 'comment_pool_lock'):
                    with self.comment_pool_lock:
                        self.blocked_comment_accounts.clear()
                        if hasattr(self, 'comment_accounts'):
                            self.available_comment_accounts = self.comment_accounts.copy()
                            self.comment_account_index = 0
                
                self.log_message("✅ 계정 풀 상태 초기화 완료")
                
                # 4. 계정 사용 횟수 초기화
                self.reset_account_usage()
                self.log_message("✅ 계정 사용 횟수 초기화 완료")
                
                # 5. 결과 목록 초기화
                self.results.clear()
                if hasattr(self, 'result_table'):
                    self.result_table.setRowCount(0)
                self.log_message("✅ 결과 목록 초기화 완료")
                
                # 6. 작업 진행 상태 초기화
                try:
                    # work_progress.json 파일 삭제
                    if os.path.exists("work_progress.json"):
                        os.remove("work_progress.json")
                        self.log_message("✅ 작업 진행 상태 파일 삭제 완료")
                except Exception as e:
                    self.log_message(f"⚠️ 작업 진행 상태 파일 삭제 중 오류: {str(e)}")
                
                if hasattr(self, 'progress_bar'):
                    self.progress_bar.setValue(0)
                if hasattr(self, 'status_label'):
                    self.status_label.setText("대기 중...")
                
                self.log_message("✅ 작업 진행 상태 초기화 완료")
                
                # 7. UI 버튼 상태 초기화
                if hasattr(self, 'start_btn'):
                    self.start_btn.setText("🚀 작업 시작")
                    self.start_btn.setEnabled(True)
                if hasattr(self, 'stop_btn'):
                    self.stop_btn.setEnabled(False)
                if hasattr(self, 'save_result_btn'):
                    self.save_result_btn.setEnabled(False)
                
                self.log_message("✅ UI 상태 초기화 완료")
                
                # 8. 로그 텍스트 초기화 (마지막에)
                QTimer.singleShot(1000, self.clear_logs)  # 1초 후 로그 초기화
                
                self.log_message("🎉 전체 초기화가 완료되었습니다!")
                
                QMessageBox.information(self, "초기화 완료", 
                    "프로그램 상태가 성공적으로 초기화되었습니다!\n\n"
                    "• 모든 Chrome 프로세스가 종료되었습니다\n"
                    "• 계정 상태가 초기화되었습니다\n"
                    "• 작업 결과가 초기화되었습니다\n\n"
                    "이제 새로운 작업을 시작할 수 있습니다.")
                
            except Exception as e:
                self.log_message(f"❌ 초기화 중 오류 발생: {str(e)}")
                QMessageBox.warning(self, "초기화 오류", 
                    f"초기화 중 오류가 발생했습니다:\n{str(e)}\n\n"
                    f"프로그램을 재시작하는 것을 권장합니다.")
    
    def clear_logs(self):
        """로그 텍스트 초기화"""
        if hasattr(self, 'log_text'):
            self.log_text.clear()
            self.log_message("📝 로그가 초기화되었습니다.")
    
    def work_finished(self):
        """🏢 작업 완료 (카페별 탭 시스템)"""
        # 여러 카페 처리 중인 경우
        if hasattr(self, 'total_cafes') and hasattr(self, 'current_cafe_index'):
            current_cafe_folder = self.cafe_folders[self.current_cafe_index]
            cafe_name = os.path.basename(current_cafe_folder)
            
            # 🎯 완료된 카페 탭 상태를 완료로 업데이트
            self.update_cafe_tab_status(cafe_name, 'completed')
            
            # 완료된 카페를 리스트에서 체크 표시로 변경
            if hasattr(self, 'cafe_list_widget'):
                item = self.cafe_list_widget.item(self.current_cafe_index)
                if item:
                    item.setText(f"✅ {cafe_name}")
            
            # 🎯 작업 완료 로그 및 결과 저장
            self.log_message(f"✅ [{self.current_cafe_index + 1}/{self.total_cafes}] {cafe_name} 카페 작업 완료!")
            self.log_message(f"📂 '{cafe_name}' 폴더의 모든 작업이 완료되었습니다!")
            
            # 🆕 카페별 결과 자동 저장 (다이얼로그 없음)
            if len(self.results) > 0:
                self.store_cafe_results(cafe_name)
                # 🔄 결과는 초기화하지 않고 계속 누적 (작업결과 탭에서 이어서 확인)
                self.log_message("📊 결과는 누적하여 계속 표시됩니다")
            else:
                self.log_message(f"ℹ️ {cafe_name} 처리된 결과가 없습니다")
            
            # 다음 카페로 이동
            self.current_cafe_index += 1
            
            # 마지막 카페가 아니면 5분 휴식
            if self.current_cafe_index < len(self.cafe_folders):
                next_cafe_name = os.path.basename(self.cafe_folders[self.current_cafe_index])
                self.log_message("=" * 60)
                self.log_message(f"💤 '{cafe_name}' 폴더 작업 완료!")
                self.log_message(f"⏰ 5분 휴식 후 '{next_cafe_name}' 폴더 작업을 시작합니다...")
                self.log_message("=" * 60)
                
                # 1단계: 크롬 완전 정리
                self.complete_chrome_cleanup()
                
                # 2단계: 5분 휴식 시작
                self.start_5minute_rest()
            else:
                # 마지막 카페면 바로 종료 처리
                self.process_next_cafe()
            return
        
        # 단일 카페 또는 모든 카페 완료 시
        self.start_btn.setText("🚀 작업 시작")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("작업 완료!")
        self.save_result_btn.setEnabled(True)
        
        # 🆕 모든 작업 완료 시 일괄 저장 처리
        if len(self.results) > 0 or self.pending_results:
            # 현재 결과도 저장 (단일 카페인 경우)
            if len(self.results) > 0 and not hasattr(self, 'total_cafes'):
                current_cafe_name = "단일작업"
                self.store_cafe_results(current_cafe_name)
            
            # 일괄 저장 완료 알림
            self.batch_save_all_results()
            
        else:
            QMessageBox.information(self, "작업 완료", 
                f"작업이 완료되었지만 처리된 결과가 없습니다.")
    
    def complete_chrome_cleanup(self):
        """🎯 자동화 전용 크롬 프로세스 선택적 정리 (사용자 Chrome 보호)"""
        try:
            self.log_message("🎯 자동화 전용 크롬 프로세스 선택적 정리 시작...")
            
            # 1. 현재 워커의 모든 드라이버 종료
            if hasattr(self, 'worker') and self.worker:
                try:
                    self.worker.stop()
                    self.log_message("🚫 워커 중지 완료")
                except:
                    pass
            
            # 2. 자동화 전용 크롬 프로세스만 선택적 종료
            import psutil
            killed_count = 0
            protected_count = 0
            
            try:
                # 워커가 추적 중인 모든 Chrome PID 수집
                automation_pids = []
                if hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'thread_chrome_pids'):
                    with self.worker.drivers_lock:
                        for thread_pids in self.worker.thread_chrome_pids.values():
                            automation_pids.extend(thread_pids)
                
                # 추적된 PID들 우선 정리
                for pid in automation_pids:
                    try:
                        if psutil.pid_exists(pid):
                            process = psutil.Process(pid)
                            process.terminate()
                            killed_count += 1
                    except:
                        pass
                
                # 자동화 식별자가 있는 Chrome 프로세스 추가 정리
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if 'chrome' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                            
                            # 자동화 프로그램 식별자 확인
                            is_automation = any(identifier in cmdline for identifier in [
                                'chrome_t0_', 'chrome_t1_', 'chrome_t2_', 'chrome_t3_', 'chrome_t4_',
                                'remote-debugging-port=922', 'remote-debugging-port=924', 
                                'remote-debugging-port=926', 'remote-debugging-port=928',
                                'AutomationControlled', 'excludeSwitches', 'incognito'
                            ])
                            
                            if is_automation and proc.info['pid'] not in automation_pids:
                                proc.terminate()
                                killed_count += 1
                            elif not is_automation:
                                protected_count += 1
                    except:
                        continue
                
                self.log_message(f"✅ 선택적 Chrome 정리 완료 (자동화: {killed_count}개 종료, 사용자: {protected_count}개 보호)")
                
            except Exception as e:
                self.log_message(f"⚠️ Chrome 프로세스 정리 중 오류: {str(e)}")
            
            # 3. 메모리 정리
            import gc
            gc.collect()
            self.log_message("🧽 메모리 가비지 컬렉션 완료")
            
            # 4. 임시 폴더 정리 시도
            try:
                import tempfile
                import shutil
                import glob
                
                temp_dirs = glob.glob(f"{tempfile.gettempdir()}/chrome_t*")
                cleaned_dirs = 0
                for temp_dir in temp_dirs:
                    try:
                        # 🔥 캐시 폴더만 삭제 (IP 설정 유지)
                        cache_folders = ["Cache", "Code Cache", "GPUCache"]
                        for cache_folder in cache_folders:
                            cache_path = os.path.join(temp_dir, cache_folder)
                            if os.path.exists(cache_path):
                                shutil.rmtree(cache_path, ignore_errors=True)
                        
                        # Session Storage와 Local Storage도 정리 (용량 절약)
                        storage_folders = ["Session Storage", "Local Storage", "Web Data"]
                        for storage_folder in storage_folders:
                            storage_path = os.path.join(temp_dir, storage_folder)
                            if os.path.exists(storage_path):
                                try:
                                    if os.path.isfile(storage_path):
                                        os.remove(storage_path)
                                    else:
                                        shutil.rmtree(storage_path, ignore_errors=True)
                                except:
                                    pass
                        
                        cleaned_dirs += 1
                    except:
                        pass
                
                if cleaned_dirs > 0:
                    self.log_message(f"🗂️ 임시 폴더 {cleaned_dirs}개 캐시 정리 완료 (IP 설정 유지)")
            except:
                pass
            
            self.log_message("✅ 크롬 정리 완료 - 시스템 준비됨")
            
        except Exception as e:
            self.log_message(f"⚠️ 크롬 정리 중 오류: {str(e)}")
    
    def start_5minute_rest(self):
        """5분 휴식 시작 (카운트다운 포함)"""
        self.rest_seconds = 300  # 5분 = 300초
        self.log_message("⏰ 5분 휴식 시작 - 다음 카페 준비 중...")
        
        # 1초마다 카운트다운 업데이트
        self.rest_timer = QTimer()
        self.rest_timer.timeout.connect(self.update_rest_countdown)
        self.rest_timer.start(1000)  # 1초마다
        
        # 첫 번째 카운트다운 즉시 표시
        self.update_rest_countdown()
    
    def update_rest_countdown(self):
        """휴식 카운트다운 업데이트"""
        if not hasattr(self, 'rest_seconds'):
            return
            
        minutes = self.rest_seconds // 60
        seconds = self.rest_seconds % 60
        
        if self.rest_seconds > 0:
            self.log_message(f"⏰ 휴식 중... {minutes:02d}:{seconds:02d} 남음")
            self.rest_seconds -= 1
        else:
            # 휴식 완료
            if hasattr(self, 'rest_timer'):
                self.rest_timer.stop()
                delattr(self, 'rest_timer')
            
            # 다음 카페 이름 가져오기
            if self.current_cafe_index < len(self.cafe_folders):
                next_cafe_name = os.path.basename(self.cafe_folders[self.current_cafe_index])
                self.log_message("=" * 60)
                self.log_message(f"✅ 5분 휴식 완료!")
                self.log_message(f"🚀 이제 '{next_cafe_name}' 폴더 작업을 시작합니다!")
                self.log_message("=" * 60)
            else:
                self.log_message("✅ 5분 휴식 완료! 다음 카페 시작합니다")
            
            # 1초 후 다음 카페 시작 (UI 업데이트 여유)
            QTimer.singleShot(1000, self.process_next_cafe)
    
    def work_error(self, error_msg):
        """작업 오류"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("오류 발생")
        QMessageBox.critical(self, "오류", f"작업 중 오류 발생:\n{error_msg}")
    
    def add_partial_result(self, partial_result):
        """📌 답글 시작 시 부분 결과 추가 (기존 preview 행 업데이트)"""
        # 🔥 unique_key가 없으면 생성
        if 'unique_key' not in partial_result or not partial_result.get('unique_key'):
            # thread_id는 partial_result에서 가져오거나 기본값 사용
            thread_id = partial_result.get('thread_id', 0)
            target_url = partial_result.get('원본URL', '')
            target_script_folder = partial_result.get('script_folder', '')
            unique_key = generate_unique_key(target_url, target_script_folder, thread_id)
            partial_result['unique_key'] = unique_key
            self.log_message(f"🔑 부분 결과에 unique_key 생성: {unique_key[:50]}...")
        
        # 🔥 답글아이디 + script_folder로 매칭 (연쇄 답글 대응)
        target_account_id = partial_result.get('답글아이디', '')
        target_script_folder = partial_result.get('script_folder', '')
        target_url = partial_result.get('원본URL', '')  # 현재 작업 URL (연쇄된 URL일 수 있음)
        
        existing_row = None
        # 먼저 답글아이디 + script_folder로 찾기
        for i, existing_result in enumerate(self.results):
            if (existing_result.get('답글아이디', '') == target_account_id and  # 답글아이디가 일치하고
                existing_result.get('script_folder', '') == target_script_folder):  # 스크립트 폴더가 일치
                existing_row = i
                break
        
        # 못 찾았으면 대기중 상태인 행 찾기 (초기 상태)
        if existing_row is None:
            for i, existing_result in enumerate(self.results):
                if (existing_result.get('script_folder', '') == target_script_folder and  # 스크립트 폴더가 일치하고
                    existing_result.get('답글아이디', '') == '⏳ 대기중'):  # 아직 대기 상태인 행
                    existing_row = i
                    break
        
        if existing_row is not None:
            # 🔥 기존 preview 행 업데이트
            self.results[existing_row]['답글아이디'] = partial_result.get('답글아이디', '')
            self.results[existing_row]['답글아이디로그인아이피'] = '작업 중...'
            self.results[existing_row]['답글URL'] = '등록 중...'
            self.results[existing_row]['댓글상황'] = '대기 중...'
            self.results[existing_row]['_row_index'] = existing_row
            
            # 🔥 cafe_name도 업데이트
            if 'cafe_name' not in self.results[existing_row] or not self.results[existing_row].get('cafe_name'):
                current_cafe = partial_result.get('cafe_name', '') or getattr(self, 'current_cafe_name', '')
                if not current_cafe and hasattr(self, 'worker') and self.worker:
                    current_cafe = getattr(self.worker, 'current_cafe_name', '')
                if current_cafe:
                    self.results[existing_row]['cafe_name'] = current_cafe
            
            # 🔥 연쇄 답글인 경우 원본URL도 업데이트
            if target_url and target_url != self.results[existing_row].get('원본URL', ''):
                self.results[existing_row]['원본URL'] = target_url
                self.result_table.setItem(existing_row, 5, QTableWidgetItem(target_url))
                self.log_message(f"🔗 연쇄 답글 - 원본URL 업데이트: {target_url[:50]}...")
            
            # 테이블 업데이트
            self.result_table.setItem(existing_row, 1, QTableWidgetItem(partial_result.get('답글아이디', '')))
            self.result_table.setItem(existing_row, 2, QTableWidgetItem('작업 중...'))
            self.result_table.setItem(existing_row, 4, QTableWidgetItem('등록 중...'))
            self.result_table.setItem(existing_row, 6, QTableWidgetItem('대기 중...'))
            
            row = existing_row
            self.log_message(f"📝 기존 preview 행 업데이트: {target_url} - {partial_result.get('답글아이디', '')}")
        else:
            # preview 행이 없는 경우 (이상한 경우) 새로 추가
            # 🔥 cafe_name 추가
            current_cafe = partial_result.get('cafe_name', '') or getattr(self, 'current_cafe_name', '')
            if not current_cafe and hasattr(self, 'worker') and self.worker:
                current_cafe = getattr(self.worker, 'current_cafe_name', '')
            
            full_result = {
                '폴더명': partial_result.get('폴더명', ''),
                '답글아이디': partial_result.get('답글아이디', ''),
                '답글아이디로그인아이피': '작업 중...',  # 나중에 업데이트
                '답글등록상태': '-',  # 나중에 업데이트 (O/X/-)
                '답글URL': '등록 중...',  # 나중에 업데이트
                '원본URL': partial_result.get('원본URL', ''),
                '댓글상황': '대기 중...',  # 나중에 업데이트
                '댓글차단': '⏳ 대기중',  # 초기 상태
                'cafe_name': current_cafe,  # 🔥 카페명 추가
                '_row_index': None  # 테이블 행 번호 저장용
            }
            
            # 테이블에 추가
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            full_result['_row_index'] = row
            
            # 기본 정보만 표시 (새로운 순서로)
            self.result_table.setItem(row, 0, QTableWidgetItem(full_result['폴더명']))
            self.result_table.setItem(row, 1, QTableWidgetItem(full_result['답글아이디']))
            self.result_table.setItem(row, 2, QTableWidgetItem(full_result['답글아이디로그인아이피']))
            self.result_table.setItem(row, 3, QTableWidgetItem(full_result['답글등록상태']))
            self.result_table.setItem(row, 4, QTableWidgetItem(full_result['답글URL']))
            self.result_table.setItem(row, 5, QTableWidgetItem(full_result['원본URL']))
            self.result_table.setItem(row, 6, QTableWidgetItem(full_result['댓글상황']))
            self.result_table.setItem(row, 7, QTableWidgetItem(full_result['댓글차단']))
            
            # results에 추가
            self.results.append(full_result)
            self.log_message(f"📝 새 작업 행 추가 (preview 없음): {target_url} - {partial_result.get('답글아이디', '')}")
        
        # 📌 결과가 추가되면 저장 버튼 활성화
        if len(self.results) > 0:
            self.save_result_btn.setEnabled(True)
        
        # 🆕 아이디 사용 시작 시 통계 업데이트
        account_id = partial_result.get('답글아이디', '')
        cafe_name = partial_result.get('cafe_name', '')
        
        if account_id and account_id != '⏳ 대기중' and cafe_name:
            # 아이디 통계가 있으면 "작업중" 상태로 업데이트
            if account_id in self.account_stats:
                stats = self.account_stats[account_id]
                
                # 작업 진행 중 카운트 증가
                stats.setdefault(f'{cafe_name}_in_progress', 0)
                stats[f'{cafe_name}_in_progress'] += 1
                
                # 상태를 "작업중"으로 변경
                if stats.get('status') != '여분':  # 여분 아이디는 상태 유지
                    stats['status'] = '작업중'
                
                # 마지막 사용 시간 업데이트
                stats['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                
                # 테이블 즉시 업데이트
                self.update_account_table()
                self.update_account_summary()
                
                self.log_message(f"📊 {account_id} 작업 시작 - 아이디 관리 통계 업데이트")
        
        # 작업 중인 항목 색상 변경 (노란색 배경)
        for col in range(8):  # 8개 열로 변경
            item = self.result_table.item(row, col)
            if item:
                item.setBackground(QColor(255, 255, 200))  # 연한 노란색
        
        # 테이블 스크롤을 맨 아래로 - 사용자 요청으로 제거
        # self.result_table.scrollToBottom()
        
        return row  # 행 번호 반환 (나중에 업데이트할 때 사용)
    
    def update_result(self, row_index, update_data):
        """📌 답글/댓글 완료 시 결과 업데이트"""
        if row_index < len(self.results):
            # results 업데이트
            if '답글아이디로그인아이피' in update_data:
                self.results[row_index]['답글아이디로그인아이피'] = update_data['답글아이디로그인아이피']
            if '답글URL' in update_data:
                self.results[row_index]['답글URL'] = update_data['답글URL']
                # 답글등록상태도 함께 업데이트
                if '오류:' in str(update_data['답글URL']) or update_data['답글URL'] == '실패':
                    self.results[row_index]['답글등록상태'] = 'X'
                elif update_data['답글URL'] != '등록 중...':
                    self.results[row_index]['답글등록상태'] = 'O'
            if '댓글상황' in update_data:
                self.results[row_index]['댓글상황'] = update_data['댓글상황']
            if '댓글차단' in update_data:
                self.results[row_index]['댓글차단'] = update_data['댓글차단']
            
            # 테이블 업데이트 (새로운 순서로)
            if '답글아이디로그인아이피' in update_data:
                self.result_table.setItem(row_index, 2, QTableWidgetItem(update_data['답글아이디로그인아이피']))
            if '답글URL' in update_data:
                self.result_table.setItem(row_index, 4, QTableWidgetItem(update_data['답글URL']))
                # 답글등록상태 테이블도 업데이트
                status = self.results[row_index]['답글등록상태']
                self.result_table.setItem(row_index, 3, QTableWidgetItem(status))
            if '댓글상황' in update_data:
                self.result_table.setItem(row_index, 6, QTableWidgetItem(update_data['댓글상황']))
            if '댓글차단' in update_data:
                self.result_table.setItem(row_index, 7, QTableWidgetItem(update_data['댓글차단']))
            
            # 📌 성공/실패에 따른 색상 변경
            is_failure = (update_data.get('답글아이디로그인아이피') == '실패' or 
                         '오류:' in str(update_data.get('답글URL', '')))
            
            # 📌 댓글 완료 여부 확인 (더 진한 초록색)
            comment_status = update_data.get('댓글상황', self.results[row_index].get('댓글상황', ''))
            is_all_complete = ('완료' in comment_status and '개' in comment_status)
            
            # 📌 댓글 차단 완료 여부 확인
            comment_block_status = update_data.get('댓글차단', self.results[row_index].get('댓글차단', ''))
            is_comment_blocked = ('✅' in comment_block_status or '➖' in comment_block_status)
            
            for col in range(8):  # 8개 열로 변경
                item = self.result_table.item(row_index, col)
                if item:
                    if is_failure:
                        item.setBackground(QColor(255, 200, 200))  # 연한 빨간색 (실패)
                    elif is_all_complete and is_comment_blocked:
                        item.setBackground(QColor(100, 255, 100))  # 가장 진한 초록색 (모든 작업 완료)
                    elif is_all_complete:
                        item.setBackground(QColor(150, 255, 150))  # 진한 초록색 (댓글까지 완료)
                    elif '답글URL' in update_data and update_data['답글URL'] != '등록 중...':
                        item.setBackground(QColor(200, 255, 200))  # 연한 초록색 (답글만 완료)
            
            # 📌 결과가 업데이트되면 저장 버튼 활성화
            if len(self.results) > 0:
                self.save_result_btn.setEnabled(True)
            
            # 🔥 답글 완료 시 아이디 관리 통계 업데이트
            if '답글URL' in update_data and update_data['답글URL'] != '등록 중...':
                self.update_account_stats_from_result(self.results[row_index])

    def add_result(self, result):
        """결과 추가 (기존 행 업데이트 또는 새 행 추가)"""
        # 🔥 cafe_name이 없으면 현재 카페명 추가
        if 'cafe_name' not in result or not result.get('cafe_name'):
            current_cafe = getattr(self, 'current_cafe_name', '')
            if not current_cafe and hasattr(self, 'worker') and self.worker:
                current_cafe = getattr(self.worker, 'current_cafe_name', '')
            if current_cafe:
                result['cafe_name'] = current_cafe
                self.log_message(f"📋 결과에 카페명 추가: {current_cafe}")
        
        # 댓글상황이 없으면 기본값 설정
        if '댓글상황' not in result:
            result['댓글상황'] = '미작성'
        
        # 댓글차단이 없으면 기본값 설정
        if '댓글차단' not in result:
            result['댓글차단'] = '⏳ 대기중'
        
        # 답글등록상태 설정
        if '답글등록상태' not in result:
            if '답글URL' in result:
                if '오류:' in str(result['답글URL']) or result['답글URL'] == '실패':
                    result['답글등록상태'] = 'X'
                elif result['답글URL'] != '등록 중...':
                    result['답글등록상태'] = 'O'
                else:
                    result['답글등록상태'] = '-'
            else:
                result['답글등록상태'] = '-'
        
        # 🔥 기존 "대기중" 행 찾아서 업데이트 또는 새 행 추가
        existing_row = self.find_existing_preview_row(result)
        
        if existing_row is not None:
            # 기존 행 업데이트
            self.results[existing_row] = result
            self.update_table_row(existing_row, result)
            self.log_message(f"📝 작업 행 업데이트: {result.get('원본URL', 'Unknown')} - {result.get('답글아이디', 'Unknown')}")
        else:
            # 새 행 추가 (기존 방식)
            self.results.append(result)
            
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            self.update_table_row(row, result)
            self.log_message(f"📝 새 작업 행 추가: {result.get('원본URL', 'Unknown')} - {result.get('답글아이디', 'Unknown')}")
        
        # 🆕 아이디 관리 통계 업데이트
        self.update_account_stats_from_result(result)
        
        # 📌 결과가 추가되면 저장 버튼 활성화
        if len(self.results) > 0:
            self.save_result_btn.setEnabled(True)
    
    def find_existing_preview_row(self, result):
        """기존 행 찾기 (unique_key 우선 매칭)"""
        try:
            # 🔥 1순위: unique_key로 정확히 매칭
            target_unique_key = result.get('unique_key', '')
            if target_unique_key:
                for i, existing_result in enumerate(self.results):
                    if existing_result.get('unique_key', '') == target_unique_key:
                        self.log_message(f"🔑 unique_key 매칭 성공: {target_unique_key[:50]}...")
                        return i
            
            # 🔥 2순위: 답글아이디와 스크립트 폴더로 매칭 (기존 방식)
            target_account_id = result.get('답글아이디', '')
            target_script_folder = result.get('script_folder', '')
            
            for i, existing_result in enumerate(self.results):
                if (existing_result.get('답글아이디', '') == target_account_id and  # 답글아이디가 일치하고
                    existing_result.get('script_folder', '') == target_script_folder):  # 스크립트 폴더가 일치
                    self.log_message(f"📝 기존 매칭 방식: {target_account_id} + {os.path.basename(target_script_folder) if target_script_folder else 'None'}")
                    return i
            
            # 🔥 3순위: 답글아이디가 아직 할당되지 않은 경우 (대기중인 preview 행)
            if target_account_id in ['⏳ 대기중', '작업 중...', '']:
                for i, existing_result in enumerate(self.results):
                    if (existing_result.get('script_folder', '') == target_script_folder and  # 스크립트 폴더가 일치하고
                        existing_result.get('답글아이디', '') in ['⏳ 대기중', '작업 중...', '']):  # 아직 아이디가 할당되지 않은 상태
                        self.log_message(f"⏳ 대기중 행 매칭: {os.path.basename(target_script_folder) if target_script_folder else 'None'}")
                        return i
            
            self.log_message(f"❌ 매칭 실패 - 새 행 생성: {target_account_id}")
            return None
        except Exception as e:
            self.log_message(f"⚠️ 행 매칭 오류: {str(e)}")
            return None
    
    def update_table_row(self, row, result):
        """테이블 특정 행 업데이트"""
        try:
            self.result_table.setItem(row, 0, QTableWidgetItem(result.get('폴더명', '')))
            self.result_table.setItem(row, 1, QTableWidgetItem(result['답글아이디']))
            self.result_table.setItem(row, 2, QTableWidgetItem(result['답글아이디로그인아이피']))
            self.result_table.setItem(row, 3, QTableWidgetItem(result['답글등록상태']))
            self.result_table.setItem(row, 4, QTableWidgetItem(result['답글URL']))
            self.result_table.setItem(row, 5, QTableWidgetItem(result['원본URL']))
            self.result_table.setItem(row, 6, QTableWidgetItem(result['댓글상황']))
            self.result_table.setItem(row, 7, QTableWidgetItem(result['댓글차단']))
        except Exception as e:
            self.log_message(f"❌ 테이블 행 업데이트 실패: {str(e)}")
    
    def setup_auto_save_settings(self):
        """🆕 작업 시작 시 저장 설정"""
        # 자동 저장 여부 확인
        reply = QMessageBox.question(
            self, "저장 설정",
            "🗂️ 작업 완료된 카페별 결과를 자동으로 저장하시겠습니까?\n\n"
            "✅ 예: 각 카페 작업 완료 시 자동 저장 (추천)\n"
            "❌ 아니요: 수동으로 저장\n\n"
            "※ 자동 저장 시 한 번만 저장 폴더를 선택하면 됩니다!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 저장 폴더 선택
            save_directory = QFileDialog.getExistingDirectory(
                self, "저장 폴더 선택", "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            
            if save_directory:
                self.auto_save_enabled = True
                self.save_directory = save_directory
                self.log_message(f"💾 자동 저장 활성화: {save_directory}")
                QMessageBox.information(self, "설정 완료", 
                    f"자동 저장이 설정되었습니다!\n\n📁 저장 위치: {save_directory}\n\n"
                    f"각 카페 작업 완료 시 '카페명_날짜시간.csv' 형식으로 자동 저장됩니다.")
            else:
                self.auto_save_enabled = False
                self.log_message("⚠️ 저장 폴더를 선택하지 않아 자동 저장이 비활성화됩니다")
        else:
            self.auto_save_enabled = False
            self.log_message("ℹ️ 수동 저장 모드로 진행합니다")
    
    def generate_filename(self, cafe_name):
        """🆕 카페명과 날짜로 파일명 자동 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_cafe_name = re.sub(r'[<>:"/\\|?*]', '_', cafe_name)  # 파일명에 사용 불가한 문자 제거
        return f"{safe_cafe_name}_{timestamp}.csv"
    
    def store_cafe_results(self, cafe_name):
        """🆕 카페별 결과 임시 저장"""
        if self.results:
            self.pending_results[cafe_name] = self.results.copy()
            self.log_message(f"📋 {cafe_name} 결과 임시 저장: {len(self.results)}개 항목")
            
            # 자동 저장이 활성화된 경우 바로 저장
            if self.auto_save_enabled and self.save_directory:
                self.auto_save_cafe_results(cafe_name)
    
    def auto_save_cafe_results(self, cafe_name):
        """🆕 카페별 결과 자동 저장 (다이얼로그 없음)"""
        try:
            if cafe_name in self.pending_results:
                filename = self.generate_filename(cafe_name)
                file_path = os.path.join(self.save_directory, filename)
                
                # 메인 결과 저장
                df = pd.DataFrame(self.pending_results[cafe_name])
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                # 계정 상태 로그 저장 (별도 파일)
                account_status_file = file_path.replace('.csv', '_계정상태로그.csv')
                if hasattr(self.worker, 'account_status_log') and self.worker.account_status_log:
                    account_status_data = []
                    for account_id, status_info in self.worker.account_status_log.items():
                        account_status_data.append({
                            '계정아이디': account_id,
                            '상태': status_info['status'], 
                            '계정타입': status_info['type'],
                            '스레드ID': status_info['thread_id'],
                            '확인시각': status_info['timestamp']
                        })
                    
                    if account_status_data:
                        status_df = pd.DataFrame(account_status_data)
                        status_df.to_csv(account_status_file, index=False, encoding='utf-8-sig')
                
                self.log_message(f"💾 {cafe_name} 자동 저장 완료: {filename}")
                
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 자동 저장 실패: {str(e)}")
    
    def batch_save_all_results(self):
        """🆕 모든 카페 결과 일괄 저장 알림"""
        if self.auto_save_enabled and self.pending_results:
            # 저장된 파일들 목록 생성
            saved_files = []
            total_results = 0
            
            for cafe_name in self.pending_results.keys():
                # 실제 저장된 파일명 찾기 (저장 디렉터리에서)
                try:
                    files_in_dir = os.listdir(self.save_directory)
                    safe_cafe_name = re.sub(r'[<>:"/\\|?*]', '_', cafe_name)
                    
                    # 해당 카페 관련 파일들 찾기
                    cafe_files = [f for f in files_in_dir if f.startswith(safe_cafe_name) and f.endswith('.csv') and '_계정상태로그' not in f]
                    
                    if cafe_files:
                        # 가장 최신 파일 선택
                        latest_file = max(cafe_files, key=lambda f: os.path.getctime(os.path.join(self.save_directory, f)))
                        saved_files.append(f"📄 {latest_file}")
                        total_results += len(self.pending_results[cafe_name])
                    else:
                        # 파일이 없으면 예상 파일명으로 표시
                        filename = self.generate_filename(cafe_name)
                        saved_files.append(f"📄 {filename}")
                        total_results += len(self.pending_results[cafe_name])
                        
                except Exception as e:
                    # 오류 시 예상 파일명으로 표시
                    filename = self.generate_filename(cafe_name)
                    saved_files.append(f"📄 {filename}")
                    total_results += len(self.pending_results[cafe_name])
            
            if saved_files:
                file_list = "\n".join(saved_files)
                QMessageBox.information(self, "저장 완료", 
                    f"🎉 모든 카페 결과가 자동 저장되었습니다!\n\n"
                    f"📊 총 처리 결과: {total_results}개 작업\n"
                    f"📁 저장 위치: {self.save_directory}\n\n"
                    f"📋 저장된 파일들:\n{file_list}")
            else:
                QMessageBox.information(self, "알림", "저장할 결과가 없습니다.")
                
        elif self.auto_save_enabled and not self.pending_results:
            QMessageBox.information(self, "알림", "저장할 카페 결과가 없습니다.")
        else:
            # 수동 저장 모드일 때는 기존 save_results 호출
            if len(self.results) > 0 or self.pending_results:
                self.save_results()
            else:
                QMessageBox.information(self, "알림", "저장할 결과가 없습니다.")

    def populate_account_management(self, cafe_name):
        """아이디 관리 탭에 매칭된 계정 정보 로드"""
        try:
            if cafe_name not in self.cafe_data:
                return
                
            cafe_data = self.cafe_data[cafe_name]
            id_script_mapping = cafe_data.get('id_script_mapping', {})
            
            if not id_script_mapping:
                return
            
            self.log_message(f"📊 {cafe_name} 아이디 관리 정보 생성 중...")
            
            # 각 계정별로 통계 생성
            for account_id, mapping_data in id_script_mapping.items():
                scripts = mapping_data.get('scripts', [])
                
                # 계정 통계 초기화 또는 업데이트
                if account_id not in self.account_stats:
                    self.account_stats[account_id] = {
                        'cafes': {},
                        'total_assigned': 0,
                        'total_completed': 0,
                        'total_failed': 0,
                        'last_used': '-',
                        'status': '대기중'
                    }
                
                # 🔥 카페별 작업 수 업데이트 (중복 방지)
                old_count = self.account_stats[account_id]['cafes'].get(cafe_name, 0)
                self.account_stats[account_id]['cafes'][cafe_name] = len(scripts)
                # total_assigned는 차이만큼만 더하기
                self.account_stats[account_id]['total_assigned'] += (len(scripts) - old_count)
            
            # 🆕 여분 아이디도 추가
            spare_accounts = cafe_data.get('spare_accounts', [])
            for spare_account in spare_accounts:
                account_id = spare_account[0]  # 아이디
                
                if account_id not in self.account_stats:
                    self.account_stats[account_id] = {
                        'cafes': {},
                        'total_assigned': 0,
                        'total_completed': 0,
                        'total_failed': 0,
                        'last_used': '-',
                        'status': '여분'  # 🔥 여분 상태 표시
                    }
                else:
                    # 🔥 이미 등록된 아이디도 여분 상태로 변경
                    self.account_stats[account_id]['status'] = '여분'
                
                # 여분 아이디는 작업이 0개
                self.account_stats[account_id]['cafes'][f"{cafe_name}_여분"] = 0
            
            # 테이블 업데이트
            self.update_account_table()
            
            # 요약 정보 업데이트
            self.update_account_summary()
            
            self.log_message(f"✅ {cafe_name} 아이디 관리 정보 생성 완료")
            
        except Exception as e:
            self.log_message(f"❌ {cafe_name} 아이디 관리 정보 생성 실패: {str(e)}")

    def update_account_table(self):
        """아이디 관리 테이블 업데이트"""
        self.account_table.setRowCount(0)
        
        for account_id, stats in self.account_stats.items():
            # 각 카페별로 행 추가
            for cafe_name, task_count in stats['cafes'].items():
                row = self.account_table.rowCount()
                self.account_table.insertRow(row)
                
                # 진행률 계산
                progress = 0
                if task_count > 0:
                    cafe_completed = stats.get(f'{cafe_name}_completed', 0)
                    progress = int((cafe_completed / task_count) * 100)
                
                # 상태 가져오기 (표시용 상태 결정)
                base_status = stats['status']
                
                # 카페별 진행 상태 표시 (숫자 포함)
                completed = stats.get(f'{cafe_name}_completed', 0)
                failed = stats.get(f'{cafe_name}_failed', 0)
                
                if progress == 100 and task_count > 0:
                    if failed > 0:
                        display_status = f"{completed}개 작성 ({failed}실패)"
                    else:
                        display_status = f"{completed}개 작성"
                elif progress > 0:
                    display_status = f"{completed}/{task_count} 작업중"
                elif base_status == "여분":
                    display_status = "여분"
                elif base_status == "주의":
                    display_status = f"{completed}개 작성 ({failed}실패)"
                elif base_status == "완료":
                    total_completed = stats.get('total_completed', 0)
                    total_failed = stats.get('total_failed', 0)
                    if total_failed > 0:
                        display_status = f"{total_completed}개 작성 ({total_failed}실패)"
                    else:
                        display_status = f"{total_completed}개 작성"
                else:
                    display_status = base_status
                
                # 테이블 아이템 설정
                self.account_table.setItem(row, 0, QTableWidgetItem(account_id))
                self.account_table.setItem(row, 1, QTableWidgetItem(cafe_name))
                self.account_table.setItem(row, 2, QTableWidgetItem(str(task_count)))
                self.account_table.setItem(row, 3, QTableWidgetItem(str(stats.get(f'{cafe_name}_completed', 0))))
                self.account_table.setItem(row, 4, QTableWidgetItem(str(stats.get(f'{cafe_name}_failed', 0))))
                self.account_table.setItem(row, 5, QTableWidgetItem(f"{progress}%"))
                
                # 상태 아이템 (색상 설정)
                status_item = QTableWidgetItem(display_status)
                if display_status == "완료":
                    status_item.setBackground(QColor(200, 255, 200))  # 연한 녹색
                elif display_status == "작업중":
                    status_item.setBackground(QColor(255, 255, 200))  # 연한 노란색
                elif display_status == "실패" or display_status == "주의":
                    status_item.setBackground(QColor(255, 200, 200))  # 연한 빨간색
                elif display_status == "여분":
                    status_item.setBackground(QColor(200, 220, 255))  # 연한 파란색
                self.account_table.setItem(row, 6, status_item)
                
                self.account_table.setItem(row, 7, QTableWidgetItem(stats['last_used']))

    def update_account_summary(self):
        """아이디 관리 요약 정보 업데이트"""
        total = len(self.account_stats)
        active = sum(1 for stats in self.account_stats.values() if stats['status'] != '차단')
        blocked = total - active
        today_used = sum(1 for stats in self.account_stats.values() 
                        if stats['last_used'] != '-' and stats['last_used'].startswith(datetime.now().strftime('%Y-%m-%d')))
        
        self.total_accounts_label.setText(f"총 아이디: {total}개")
        self.active_accounts_label.setText(f"활성: {active}개")
        self.blocked_accounts_label.setText(f"차단: {blocked}개")
        self.today_used_label.setText(f"오늘 사용: {today_used}개")
    
    def export_account_stats(self):
        """아이디 관리 통계 내보내기"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "통계 저장", 
                f"아이디통계_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['아이디', '카페', '할당작업', '완료', '실패', '성공률', '상태', '마지막사용'])
                    
                    for account_id, stats in self.account_stats.items():
                        for cafe_name, task_count in stats['cafes'].items():
                            completed = stats.get(f'{cafe_name}_completed', 0)
                            failed = stats.get(f'{cafe_name}_failed', 0)
                            success_rate = 0
                            if completed + failed > 0:
                                success_rate = round((completed / (completed + failed)) * 100, 1)
                            
                            writer.writerow([
                                account_id,
                                cafe_name,
                                task_count,
                                completed,
                                failed,
                                f"{success_rate}%",
                                stats['status'],
                                stats['last_used']
                            ])
                
                QMessageBox.information(self, "성공", f"통계가 저장되었습니다:\n{filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"통계 저장 실패:\n{str(e)}")
    
    def refresh_account_stats(self):
        """아이디 관리 통계 새로고침"""
        try:
            # 모든 카페의 매칭 데이터를 다시 로드
            for cafe_name in self.cafe_data.keys():
                self.populate_account_management(cafe_name)
            
            self.log_message("✅ 아이디 관리 통계 새로고침 완료")
            
        except Exception as e:
            self.log_message(f"❌ 아이디 관리 통계 새로고침 실패: {str(e)}")
    
    def save_account_results(self):
        """아이디 관리 결과 수동 저장"""
        try:
            # 저장할 데이터가 있는지 확인
            if not self.account_stats:
                QMessageBox.information(self, "알림", "저장할 아이디 관리 데이터가 없습니다.")
                return
            
            # 파일 대화상자
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"아이디관리_{timestamp}.csv"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, 
                "아이디 관리 결과 저장", 
                default_filename,
                "CSV 파일 (*.csv);;모든 파일 (*.*)"
            )
            
            if filename:
                # CSV 파일로 저장
                with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # 헤더 작성
                    writer.writerow([
                        '답글 아이디', '카페', '할당작업', '완료', 
                        '실패', '진행률', '상태', '마지막 사용'
                    ])
                    
                    # 데이터 작성
                    for account_id, stats in self.account_stats.items():
                        for cafe_name, task_count in stats['cafes'].items():
                            # 진행률 계산
                            progress = 0
                            if task_count > 0:
                                cafe_completed = stats.get(f'{cafe_name}_completed', 0)
                                progress = int((cafe_completed / task_count) * 100)
                            
                            # 상태 결정
                            status = stats['status']
                            if progress == 100:
                                status = "완료"
                            elif progress > 0:
                                status = "작업중"
                            
                            writer.writerow([
                                account_id,
                                cafe_name,
                                task_count,
                                stats.get(f'{cafe_name}_completed', 0),
                                stats.get(f'{cafe_name}_failed', 0),
                                f"{progress}%",
                                status,
                                stats['last_used']
                            ])
                
                self.log_message(f"✅ 아이디 관리 결과가 저장되었습니다: {filename}")
                QMessageBox.information(self, "저장 완료", f"파일이 저장되었습니다:\n{filename}")
                
        except Exception as e:
            self.log_message(f"❌ 아이디 관리 결과 저장 실패: {str(e)}")
            QMessageBox.critical(self, "오류", f"저장 중 오류가 발생했습니다:\n{str(e)}")

    def update_account_stats_from_result(self, result):
        """작업 결과를 바탕으로 아이디 관리 통계 업데이트"""
        try:
            account_id = result.get('답글아이디', '')
            cafe_name = result.get('cafe_name', '')
            
            # 🔥 cafe_name이 없으면 현재 카페명 사용
            if not cafe_name:
                cafe_name = getattr(self, 'current_cafe_name', '')
                if not cafe_name and hasattr(self, 'worker') and self.worker:
                    cafe_name = getattr(self.worker, 'current_cafe_name', '')
            
            if not account_id or account_id == '⏳ 대기중' or not cafe_name:
                if not cafe_name:
                    self.log_message(f"⚠️ 아이디 통계 업데이트 실패: cafe_name 없음 (계정: {account_id})")
                return
            
            # 통계 업데이트
            if account_id in self.account_stats:
                stats = self.account_stats[account_id]
                
                self.log_message(f"📊 {account_id} 통계 업데이트 시작 - 카페: {cafe_name}, 상태: {result.get('답글등록상태', 'Unknown')}")
                
                # 작업 진행 중 카운트 감소
                if f'{cafe_name}_in_progress' in stats and stats[f'{cafe_name}_in_progress'] > 0:
                    stats[f'{cafe_name}_in_progress'] -= 1
                    self.log_message(f"📉 {account_id} 진행중 카운트 감소: {cafe_name}_in_progress = {stats[f'{cafe_name}_in_progress']}")
                
                # 작업 상태 확인
                if result.get('답글등록상태') == 'O':
                    stats.setdefault(f'{cafe_name}_completed', 0)
                    stats[f'{cafe_name}_completed'] += 1
                    stats['total_completed'] += 1
                    self.log_message(f"✅ {account_id} 완료 카운트 증가: {cafe_name}_completed = {stats[f'{cafe_name}_completed']}, total = {stats['total_completed']}")
                elif result.get('답글등록상태') == 'X':
                    stats.setdefault(f'{cafe_name}_failed', 0)
                    stats[f'{cafe_name}_failed'] += 1
                    stats['total_failed'] += 1
                    self.log_message(f"❌ {account_id} 실패 카운트 증가: {cafe_name}_failed = {stats[f'{cafe_name}_failed']}, total = {stats['total_failed']}")
                else:
                    self.log_message(f"⚠️ {account_id} 알 수 없는 상태: {result.get('답글등록상태', 'None')}")
                
                # 마지막 사용 시간 업데이트
                stats['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                
                # 상태 업데이트 (여분 상태는 유지)
                if stats.get('status') != '여분':  # 🔥 여분 아이디는 상태 유지!
                    # 진행 중인 작업이 있는지 확인
                    has_in_progress = any(
                        stats.get(key, 0) > 0 
                        for key in stats.keys()
                        if key.endswith('_in_progress')
                    )
                    
                    # 모든 작업이 완료되었는지 확인
                    total_assigned = stats.get('total_assigned', 0)
                    total_completed = stats.get('total_completed', 0)
                    total_failed = stats.get('total_failed', 0)
                    all_done = (total_completed + total_failed) >= total_assigned
                    
                    if has_in_progress:
                        stats['status'] = '작업중'
                        self.log_message(f"📊 {account_id} 상태: 작업중 (진행 중인 작업 있음)")
                    elif all_done and total_assigned > 0:
                        if total_failed > 0:
                            stats['status'] = '주의'
                            self.log_message(f"📊 {account_id} 상태: 주의 (실패 {total_failed}건)")
                        else:
                            stats['status'] = '완료'
                            self.log_message(f"📊 {account_id} 상태: 완료 (모든 작업 성공)")
                    else:
                        stats['status'] = '활성'
                        self.log_message(f"📊 {account_id} 상태: 활성")
                
                # 테이블 업데이트
                self.update_account_table()
                self.update_account_summary()
            else:
                self.log_message(f"⚠️ {account_id} 아이디 관리에서 찾을 수 없음 - 통계 업데이트 불가")
                
        except Exception as e:
            self.log_message(f"⚠️ 아이디 통계 업데이트 실패: {str(e)}")
    
    def save_results(self):
        """결과 저장 (수동 저장용)"""
        if not self.results:
            QMessageBox.warning(self, "경고", "저장할 결과가 없습니다.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "결과 저장", f"카페포스팅_결과_{timestamp}.csv", 
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                # 메인 결과 저장
                df = pd.DataFrame(self.results)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                # 📌 계정 상태 로그 저장 (별도 파일)
                account_status_file = file_path.replace('.csv', '_계정상태로그.csv')
                if hasattr(self.worker, 'account_status_log') and self.worker.account_status_log:
                    account_status_data = []
                    for account_id, status_info in self.worker.account_status_log.items():
                        account_status_data.append({
                            '계정아이디': account_id,
                            '상태': status_info['status'], 
                            '계정타입': status_info['type'],
                            '스레드ID': status_info['thread_id'],
                            '확인시각': status_info['timestamp']
                        })
                    
                    if account_status_data:
                        status_df = pd.DataFrame(account_status_data)
                        status_df.to_csv(account_status_file, index=False, encoding='utf-8-sig')
                        self.log_message(f"📋 계정 상태 로그 저장: {account_status_file}")
                
                QMessageBox.information(self, "완료", f"결과가 저장되었습니다:\n{file_path}")
                self.log_message(f"💾 결과 저장 완료: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"결과 저장 실패:\n{str(e)}")
    
    def force_save_results(self):
        """강제 저장 (우클릭 메뉴용)"""
        if not self.results:
            QMessageBox.information(self, "알림", "저장할 결과가 없습니다.")
            return
        
        # 저장 버튼을 활성화하고 저장 함수 호출
        self.save_result_btn.setEnabled(True)
        self.save_results()
    
    def create_thread_log_widgets(self, thread_count):
        """스레드 수에 따라 동적으로 로그창 생성"""
        # 기존 로그 위젯들 제거
        for widget in self.log_widgets.values():
            widget.deleteLater()
        self.log_widgets.clear()
        
        # 기본 로그창도 제거
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.deleteLater()
            self.log_text = None
        
        # 레이아웃 클리어
        while self.log_layout.count():
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if thread_count == 1:
            # 1개일 때: 전체 화면
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            log_widget.setFont(QFont("Consolas", 9))
            self.log_widgets[0] = log_widget
            self.log_layout.addWidget(log_widget)
            
        elif thread_count == 2:
            # 2개일 때: 좌우 분할
            splitter = QSplitter(Qt.Horizontal)
            for i in range(2):
                log_widget = QTextEdit()
                log_widget.setReadOnly(True)
                log_widget.setFont(QFont("Consolas", 9))
                self.log_widgets[i] = log_widget
                
                frame = QFrame()
                frame.setFrameStyle(QFrame.Box)
                layout = QVBoxLayout(frame)
                layout.addWidget(QLabel(f"스레드 {i+1}"))
                layout.addWidget(log_widget)
                splitter.addWidget(frame)
            
            self.log_layout.addWidget(splitter)
            
        elif thread_count <= 4:
            # 3-4개일 때: 2x2 그리드
            grid = QGridLayout()
            for i in range(thread_count):
                log_widget = QTextEdit()
                log_widget.setReadOnly(True)
                log_widget.setFont(QFont("Consolas", 9))
                self.log_widgets[i] = log_widget
                
                frame = QFrame()
                frame.setFrameStyle(QFrame.Box)
                layout = QVBoxLayout(frame)
                layout.addWidget(QLabel(f"스레드 {i+1}"))
                layout.addWidget(log_widget)
                
                row = i // 2
                col = i % 2
                grid.addWidget(frame, row, col)
            
            grid_widget = QWidget()
            grid_widget.setLayout(grid)
            self.log_layout.addWidget(grid_widget)
            
        else:
            # 5개 이상: 복잡한 레이아웃
            main_layout = QVBoxLayout()
            
            # 상단: 1-2번 스레드 (큰 창)
            top_splitter = QSplitter(Qt.Horizontal)
            for i in range(min(2, thread_count)):
                log_widget = QTextEdit()
                log_widget.setReadOnly(True)
                log_widget.setFont(QFont("Consolas", 9))
                self.log_widgets[i] = log_widget
                
                frame = QFrame()
                frame.setFrameStyle(QFrame.Box)
                layout = QVBoxLayout(frame)
                layout.addWidget(QLabel(f"스레드 {i+1}"))
                layout.addWidget(log_widget)
                top_splitter.addWidget(frame)
            
            main_layout.addWidget(top_splitter, 2)  # 2배 크기
            
            # 하단: 나머지 스레드 (작은 창)
            if thread_count > 2:
                bottom_layout = QHBoxLayout()
                for i in range(2, thread_count):
                    log_widget = QTextEdit()
                    log_widget.setReadOnly(True)
                    log_widget.setFont(QFont("Consolas", 9))
                    self.log_widgets[i] = log_widget
                    
                    frame = QFrame()
                    frame.setFrameStyle(QFrame.Box)
                    layout = QVBoxLayout(frame)
                    layout.addWidget(QLabel(f"스레드 {i+1}"))
                    layout.addWidget(log_widget)
                    bottom_layout.addWidget(frame)
                
                bottom_widget = QWidget()
                bottom_widget.setLayout(bottom_layout)
                main_layout.addWidget(bottom_widget, 1)  # 1배 크기
            
            main_widget = QWidget()
            main_widget.setLayout(main_layout)
            self.log_layout.addWidget(main_widget)
    
    def log_message(self, message, thread_id=None):
        """로그 메시지 추가 (스레드별 라우팅 지원)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # txt 파일에 로그 기록 (개선된 오류 처리)
        try:
            if hasattr(self, 'logger') and self.logger:
                self.logger.info(message)
            else:
                # 로거가 없으면 콘솔에라도 출력
                print(f"[LOG] {message}")
        except Exception as e:
            # 로그 실패 시 콘솔에 오류 출력
            print(f"⚠️ 로그 기록 실패: {e} - 메시지: {message}")
        
        # 스레드별 로그창이 있고 thread_id가 지정된 경우
        if thread_id is not None and thread_id in self.log_widgets:
            log_widget = self.log_widgets[thread_id]
        else:
            # 🔥 수정: thread_id가 없는 경우 모든 로그창에 표시하지 않고 첫 번째만 사용
            if hasattr(self, 'log_text') and self.log_text:
                log_widget = self.log_text
            elif self.log_widgets and len(self.log_widgets) == 1:
                # 스레드가 1개인 경우에만 첫 번째 로그창 사용
                log_widget = list(self.log_widgets.values())[0]
            elif thread_id is None and self.log_widgets:
                # thread_id가 명시되지 않은 일반 로그는 모든 창에 표시하지 않음
                return
            else:
                return  # 로그창이 없으면 무시
        
        log_widget.append(log_entry)
        
        # 스크롤을 맨 아래로
        cursor = log_widget.textCursor()
        cursor.movePosition(QTextCursor.End)
        log_widget.setTextCursor(cursor)
        
        # UI 업데이트
        QApplication.processEvents()

    def log_message_with_thread(self, message, thread_id):
        """스레드별 로그 메시지 처리 (시그널 연결용)"""
        self.log_message(message, thread_id)

    # 🔄 === 공용 풀 시스템 메서드들 ===
    def get_reply_account_from_pool(self, thread_id=None):
        """스레드별 전용 답글 계정에서 사용 가능한 계정 가져오기 (같은 아이디 우선 사용, 여분용 제외)"""
        account_limit = getattr(self.worker, 'config', {}).get('account_limit', 3) if hasattr(self, 'worker') and self.worker else 3  # 🔧 기본값 3으로 변경
        
        with self.reply_pool_lock:
            # 스레드별 전용 계정 가져오기
            if thread_id is not None and hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'thread_accounts'):
                thread_reply_accounts = self.worker.thread_accounts.get('reply', {}).get(thread_id, [])
                self.log_message(f"🎯 스레드{thread_id} 전용 답글 계정 {len(thread_reply_accounts)}개에서 선택")
            else:
                # 기존 방식 (스레드 분배 없는 경우)
                thread_reply_accounts = self.available_reply_accounts
                self.log_message(f"⚠️ 스레드별 분배 없음 - 공용 풀에서 선택")
            
            # 🚫 여분용 아이디를 일반 순환에서 제외
            if hasattr(self, 'spare_accounts') and self.spare_accounts:
                spare_account_ids = set(acc[0] for acc in self.spare_accounts)
                thread_reply_accounts = [acc for acc in thread_reply_accounts if acc[0] not in spare_account_ids]
                if spare_account_ids:
                    excluded_spare_names = list(spare_account_ids)
                    self.log_message(f"🆘 스레드{thread_id} 여분용 아이디 제외: {excluded_spare_names} (일반 순환 제외)")
            
            # 🔄 차단된 계정들을 스레드별 리스트에서 영구 제거 (반복 로그인 방지)
            if thread_id is not None and hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'thread_accounts'):
                original_thread_accounts = self.worker.thread_accounts.get('reply', {}).get(thread_id, [])
                blocked_accounts_removed = []
                
                # 차단된 계정들을 원본 리스트에서 제거
                for account in original_thread_accounts[:]:  # 복사본에서 순회
                    account_id = account[0]
                    if account_id in self.blocked_reply_accounts:
                        original_thread_accounts.remove(account)
                        blocked_accounts_removed.append(account_id)
                
                if blocked_accounts_removed:
                    self.log_message(f"🗑️ 스레드{thread_id} 답글 계정 리스트에서 차단된 계정 제거: {blocked_accounts_removed}")
                    # 제거 후 업데이트된 리스트로 다시 가져오기 (여분용 제외 재적용)
                    updated_accounts = self.worker.thread_accounts.get('reply', {}).get(thread_id, [])
                    if hasattr(self, 'spare_accounts') and self.spare_accounts:
                        spare_account_ids = set(acc[0] for acc in self.spare_accounts)
                        thread_reply_accounts = [acc for acc in updated_accounts if acc[0] not in spare_account_ids]
                    else:
                        thread_reply_accounts = updated_accounts
            
            # 🎯 같은 아이디 우선 사용: 사용 중인 계정이 제한에 도달하지 않았으면 계속 사용
            currently_using_accounts = []
            other_available_accounts = []
            
            for account in thread_reply_accounts:  # 이미 차단된 계정과 여분용은 제거된 상태
                account_id = account[0]  # 계정 아이디 추출
                
                # 이중 체크: 혹시 누락된 차단 계정이 있는지 확인
                if account_id not in self.blocked_reply_accounts:
                    current_usage = self.get_account_usage_count(account_id)
                    
                    if current_usage < account_limit:
                        if current_usage > 0:
                            # 이미 사용 중인 계정 (우선순위 높음)
                            currently_using_accounts.append(account)
                        else:
                            # 아직 사용하지 않은 계정 (우선순위 낮음)
                            other_available_accounts.append(account)
                    else:
                        self.log_message(f"🚫 답글 계정 {account_id} 사용 제한 도달 ({current_usage}/{account_limit})")
                else:
                    # 여기까지 오면 안 되지만, 혹시를 위한 로그
                    self.log_message(f"⚠️ 차단된 답글 계정 {account_id}이 여전히 리스트에 있음 - 긴급 제거 필요")
            
            # 🥇 1순위: 이미 사용 중인 계정 중 가장 적게 사용된 것
            if currently_using_accounts:
                selected_account = min(currently_using_accounts, key=lambda acc: self.get_account_usage_count(acc[0]))
                current_usage = self.get_account_usage_count(selected_account[0])
                
                self.log_message(f"🥇 스레드{thread_id} 같은 아이디 계속 사용: {selected_account[0]} (사용: {current_usage}/{account_limit})")
                return selected_account
            
            # 🥈 2순위: 아직 사용하지 않은 계정 중 선택
            elif other_available_accounts:
                selected_account = other_available_accounts[0]  # 첫 번째 미사용 계정
                current_usage = self.get_account_usage_count(selected_account[0])
                
                self.log_message(f"🥈 스레드{thread_id} 새 답글 계정 시작: {selected_account[0]} (사용: {current_usage}/{account_limit})")
                return selected_account
            
            self.log_message(f"❌ 스레드{thread_id} 사용 가능한 답글 계정이 없습니다! (모든 계정이 제한 도달 또는 차단됨)")
            return None

    def get_comment_account_from_pool(self, exclude_account_id=None):
        """댓글 계정 순환 방식으로 사용 가능한 계정 가져오기 (차단된 계정과 특정 계정 제외)"""
        with self.comment_pool_lock:
            if not self.available_comment_accounts:
                self.log_message("❌ 사용 가능한 댓글 계정이 없습니다!")
                return None
            
            total_accounts = len(self.available_comment_accounts)
            attempts = 0
            
            # 제외할 계정 ID 로그
            if exclude_account_id:
                self.log_message(f"🚫 댓글 계정 선택 시 {exclude_account_id} 제외")
            
            # 모든 계정을 한 바퀴 돌면서 차단되지 않고 제외 대상이 아닌 계정 찾기
            while attempts < total_accounts:
                # 현재 인덱스의 계정 가져오기
                account = self.available_comment_accounts[self.comment_account_index]
                
                # 다음 인덱스로 이동 (순환)
                self.comment_account_index = (self.comment_account_index + 1) % total_accounts
                attempts += 1
                
                # 차단되지 않고, 제외 대상도 아닌 계정이면 반환
                if account not in self.blocked_comment_accounts and account[0] != exclude_account_id:
                    available_count = total_accounts - len(self.blocked_comment_accounts)
                    if exclude_account_id:
                        available_count -= 1  # 제외 계정도 빼기
                    self.log_message(f"🔄 댓글 계정 순환 할당: {account[0]} (사용 가능: {available_count}개)")
                    return account
            
            self.log_message("❌ 모든 댓글 계정이 차단되었거나 제외되었습니다!")
            return None

    def mark_reply_account_blocked(self, account):
        """답글 계정을 차단 목록에 추가"""
        with self.reply_pool_lock:
            self.blocked_reply_accounts.add(account)
            self.log_message(f"🚫 답글 계정 차단 추가: {account}")

    def mark_comment_account_blocked(self, account):
        """댓글 계정을 차단 목록에 추가"""
        with self.comment_pool_lock:
            self.blocked_comment_accounts.add(account)
            self.log_message(f"🚫 댓글 계정 차단 추가: {account}")

    # 🆔 === 계정 사용 횟수 관리 ===
    def get_account_usage_count(self, account_id):
        """계정의 현재 사용 횟수 반환"""
        if hasattr(self, 'worker') and self.worker:
            with self.worker.account_usage_lock:
                return self.worker.account_usage_count.get(account_id, 0)
        return 0

    def increment_account_usage(self, account_id):
        """계정 사용 횟수 증가"""
        if hasattr(self, 'worker') and self.worker:
            with self.worker.account_usage_lock:
                current = self.worker.account_usage_count.get(account_id, 0)
                self.worker.account_usage_count[account_id] = current + 1
                self.log_message(f"📊 계정 {account_id} 사용 횟수 증가: {current + 1}")
                return current + 1
        return 0

    def reset_account_usage(self):
        """모든 계정 사용 횟수 초기화"""
        if hasattr(self, 'worker') and self.worker:
            with self.worker.account_usage_lock:
                self.worker.account_usage_count.clear()
                self.log_message("🔄 모든 계정 사용 횟수 초기화")

    def get_pool_status(self):
        """공용 풀 상태 반환"""
        with self.reply_pool_lock:
            reply_available = len(self.available_reply_accounts)
            reply_blocked = len(self.blocked_reply_accounts)
        
        with self.comment_pool_lock:
            comment_available = len(self.available_comment_accounts)
            comment_blocked = len(self.blocked_comment_accounts)
        
        return {
            'reply_available': reply_available,
            'reply_blocked': reply_blocked,
            'comment_available': comment_available,
            'comment_blocked': comment_blocked
        }
    
    def save_gpt_config(self):
        """GPT API 설정 저장"""
        try:
            api_key = self.gpt_api_key_input.text().strip()
            model = self.gpt_model_combo.currentText()
            
            app_config['gpt_api_key'] = api_key
            app_config['gpt_model'] = model
            
            save_app_config()
            
            self.log_message("✅ GPT API 설정이 저장되었습니다.")
            
        except Exception as e:
            self.log_message(f"❌ GPT API 설정 저장 실패: {str(e)}")
    
    def closeEvent(self, event):
        """🎯 프로그램 종료 시 자동화 전용 크롬 프로세스만 선택적 정리 (사용자 Chrome 보호)"""
        try:
            self.log_message("🔄 프로그램 종료 중 - 자동화 전용 크롬 프로세스 정리...")
            
            # 진행 중인 작업 중지
            if hasattr(self, 'worker') and self.worker and self.worker.is_running:
                self.worker.stop()
                self.log_message("⏹️ 진행 중인 작업 중지됨")
            
            # 사용자 Chrome 감지
            try:
                import psutil
                killed_count = 0
                protected_count = 0
                
                # 워커가 추적 중인 자동화 Chrome PID 수집
                automation_pids = []
                if hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'thread_chrome_pids'):
                    try:
                        with self.worker.drivers_lock:
                            for thread_pids in self.worker.thread_chrome_pids.values():
                                automation_pids.extend(thread_pids)
                    except:
                        pass
                
                # 모든 Chrome 프로세스 검사
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if 'chrome' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                            
                            # 자동화 프로그램이 생성한 것인지 확인
                            is_automation = (
                                proc.info['pid'] in automation_pids or  # 추적된 PID이거나
                                any(identifier in cmdline for identifier in [  # 자동화 식별자가 있거나
                                    'chrome_t', 'remote-debugging-port=922', 'AutomationControlled',
                                    'excludeSwitches', 'useAutomationExtension=false', 
                                    'disable-blink-features=AutomationControlled'
                                ])
                            )
                            
                            if is_automation:
                                proc.terminate()
                                killed_count += 1
                            else:
                                protected_count += 1
                                
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                    except:
                        continue
                
                if killed_count > 0:
                    self.log_message(f"🚫 자동화 Chrome 프로세스 {killed_count}개 정리 완료")
                if protected_count > 0:
                    self.log_message(f"🛡️ 사용자 Chrome 프로세스 {protected_count}개 보호됨")
                if killed_count == 0 and protected_count == 0:
                    self.log_message("✅ 정리할 Chrome 프로세스가 없습니다")
                    
            except Exception as e:
                self.log_message(f"⚠️ Chrome 프로세스 정리 중 오류: {str(e)}")
            
            self.log_message("👋 프로그램이 정상적으로 종료됩니다 (사용자 Chrome 보호됨)")
            
        except Exception as e:
            print(f"프로그램 종료 중 오류: {e}")
        
        # 기본 종료 이벤트 처리
        event.accept()

# 앱 설정 파일 관리
app_config = {}

def load_app_config():
    global app_config
    try:
        if os.path.exists('app_config.json'):
            with open('app_config.json', 'r', encoding='utf-8') as f:
                app_config = json.load(f)
    except Exception as e:
        print(f"설정 파일 로드 실패: {e}")
        app_config = {}
    
    # 기본값 설정
    if 'gpt_api_key' not in app_config:
        app_config['gpt_api_key'] = ''
    if 'gpt_model' not in app_config:
        app_config['gpt_model'] = 'gpt-4o'

def save_app_config():
    global app_config
    try:
        with open('app_config.json', 'w', encoding='utf-8') as f:
            json.dump(app_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"설정 파일 저장 실패: {e}")

# 초기 설정 로드
load_app_config()

def main():
    """메인 함수"""
    # 🔐 라이선스 체크 (프로그램 시작 전)
    if not check_license():
        print("❌ 라이선스 인증 실패 - 프로그램을 종료합니다.")
        return
    
    print("=" * 60)
    print(f"🤖 네이버 카페 포스팅 자동화 프로그램 v{__version__}")
    print(f"📅 빌드 날짜: {__build_date__}")
    print(f"👨‍💻 개발자: {__author__}")
    print("=" * 60)
    print("⚠️  중요 경고:")
    print("   • 이 프로그램은 교육 목적으로만 사용하세요")
    print("   • 네이버 이용약관 및 카페 운영정책을 준수해주세요")
    print("   • 사용으로 인한 모든 책임은 사용자에게 있습니다")
    print("=" * 60)
    
    # 🔄 업데이트 확인 (백그라운드에서)
    try:
        print("🔄 업데이트 확인 중... (백그라운드)")
        threading.Thread(target=check_and_handle_updates, daemon=True).start()
    except Exception as e:
        print(f"⚠️ 업데이트 확인 실패: {e}")
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 애플리케이션 정보 설정
    app.setApplicationName("네이버 카페 포스팅 자동화 프로그램")
    app.setApplicationVersion("1.0")
    
    try:
        # 메인 윈도우 생성 및 표시
        window = CafePostingMainWindow()
        window.show()
        
        # 프로그램 실행
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"프로그램 실행 중 오류가 발생했습니다: {e}")
        QMessageBox.critical(None, "오류", f"프로그램 실행 중 오류가 발생했습니다:\n{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
