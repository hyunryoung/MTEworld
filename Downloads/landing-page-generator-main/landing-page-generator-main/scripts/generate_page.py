"""
상세페이지 전체 생성 파이프라인
입력 정보를 받아 최종 PNG/PDF까지 생성합니다.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gemini_api import generate_image, test_api_connection, generate_text_prompts
from scripts.stitch_images import stitch_from_directory, create_preview


# 섹션별 기본 높이
SECTION_HEIGHTS = {
    "01_hero": 800,
    "02_pain": 600,
    "03_problem": 500,
    "04_story": 700,
    "05_solution": 400,
    "06_how_it_works": 600,
    "07_social_proof": 800,
    "08_authority": 500,
    "09_benefits": 700,
    "10_risk_removal": 500,
    "11_comparison": 400,
    "12_target_filter": 400,
    "13_final_cta": 600
}


def create_sample_brief() -> Dict[str, Any]:
    """
    제품 정보 Brief를 생성합니다.
    """
    return {
        "product_name": "Oyster 프리미엄 유모차",
        "one_liner": "아이와 부모 모두를 위한 프리미엄 유모차, 가볍고 안전한 외출의 시작",
        "target_audience": "0~3세 자녀를 둔 30대 초보 부모, 디자인과 안전성 모두 중시하는 육아맘/육아대디",
        "main_problem": "무겁고 접기 힘든 유모차, 울퉁불퉁한 길에서 흔들림, 디자인 타협",
        "key_benefit": "한 손 폴딩, 올터레인 서스펜션, 프리미엄 샴페인골드 디자인으로 편안하고 안전한 외출",
        "price": {
            "original": "1,290,000원",
            "discounted": "890,000원",
            "period": ""
        },
        "urgency": {
            "type": "quantity",
            "value": "봄 시즌 한정 100대",
            "bonus": "레인커버 + 컵홀더 무료 증정"
        },
        "style_preset": "elegant",
        "brand_colors": {
            "primary": "#C4A882",
            "secondary": "#E8DDD3",
            "accent": "#8B6F4E"
        },
        "reference_image": str(PROJECT_ROOT / "TEST.PNG")
    }


def generate_section_prompts(brief: Dict[str, Any], progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Dict]:
    """
    Brief 정보를 바탕으로 13개 섹션의 Gemini 프롬프트를 생성합니다.
    """
    if progress_callback:
        progress_callback(0, 13, "카피라이팅 및 기획 중 (AI가 내용을 작성 중입니다...)")
        
    print("AI is planning and copywriting...")
    prompts = generate_text_prompts(brief)
    
    if prompts is None:
        print("Failed to generate dynamic prompts, falling back to static templates.")
        # 최소한의 기본 템플릿 반환 (실패 시)
        prompts = {
            "01_hero": {
                "prompt": f"Create a hero section for {brief.get('product_name', 'product')}. EXACT DIMENSIONS: 1200x800 pixels. FULL BLEED.",
                "width": 1200, "height": 800, "filename": "01_hero.png"
            }
        }
        
    return prompts


def save_prompts(prompts: Dict, output_path: str):
    """프롬프트를 JSON 파일로 저장"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"Prompts saved: {output_path}")


def generate_landing_page(
    brief: Optional[Dict[str, Any]] = None,
    output_dir: str = "output",
    skip_generation: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Optional[str]:
    """
    전체 상세페이지 생성 파이프라인을 실행합니다.

    Args:
        brief: 제품 정보 (없으면 샘플 사용)
        output_dir: 출력 디렉토리
        skip_generation: True면 이미지 생성 스킵 (스티칭만)
        progress_callback: (현재_인덱스, 전체_섹션_수, 현재_섹션키) 형식의 콜백 함수

    Returns:
        최종 페이지 경로
    """
    output_dir = str(PROJECT_ROOT / output_dir)
    sections_dir = os.path.join(output_dir, "sections")

    # 디렉토리 생성
    Path(sections_dir).mkdir(parents=True, exist_ok=True)

    if brief is None:
        print("Using sample brief...")
        brief = create_sample_brief()

    # Brief 저장
    brief_path = os.path.join(output_dir, "structured_brief.json")
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"Brief saved: {brief_path}")

    # 프롬프트 생성
    print("\nGenerating prompts...")
    prompts = generate_section_prompts(brief)
    prompts_path = os.path.join(output_dir, "gemini_prompts.json")
    save_prompts(prompts, prompts_path)

    if not skip_generation:
        # API 연결 테스트
        print("\nTesting API connection...")
        if not test_api_connection():
            print("API connection failed. Check your GEMINI_API_KEY.")
            return None

        # 참조 이미지 경로
        ref_image = brief.get("reference_image")

        # 섹션별 이미지 생성
        print("\nGenerating section images...")
        if ref_image:
            print(f"Reference image: {ref_image}")
        
        total_sections = len(prompts)
        for i, (section_key, section_data) in enumerate(prompts.items()):
            if progress_callback:
                progress_callback(i + 1, total_sections, section_key)
                
            print(f"\n{'='*50}")
            print(f"Generating: {section_key} ({i+1}/{total_sections})")
            print(f"{'='*50}")

            output_path = os.path.join(sections_dir, section_data["filename"])

            result = generate_image(
                prompt=section_data["prompt"],
                output_path=output_path,
                width=section_data["width"],
                height=section_data["height"],
                reference_image_path=ref_image
            )

            if not result:
                print(f"Warning: Failed to generate {section_key}")

            # API 레이트 리밋 방지
            import time
            time.sleep(3)

    # 이미지 스티칭
    print("\n" + "="*50)
    print("Stitching final page...")
    print("="*50)

    final_png = os.path.join(output_dir, "final_page.png")
    final_pdf = os.path.join(output_dir, "final_page.pdf")

    # PNG 생성
    result = stitch_from_directory(sections_dir, final_png)

    if result:
        # PDF도 생성
        stitch_from_directory(sections_dir, final_pdf)

        # 미리보기 생성
        preview_path = os.path.join(output_dir, "preview.png")
        create_preview(final_png, preview_path, max_height=2000)

        print("\n" + "="*50)
        print("COMPLETE!")
        print("="*50)
        print(f"Final PNG: {final_png}")
        print(f"Final PDF: {final_pdf}")
        print(f"Preview: {preview_path}")

        return final_png

    return None


if __name__ == "__main__":
    # 샘플 상세페이지 생성
    result = generate_landing_page(
        brief=None,  # 샘플 사용
        output_dir="output",
        skip_generation=False  # 실제 생성
    )

    if result:
        print(f"\nSuccess! Check: {result}")
    else:
        print("\nFailed to generate landing page")
