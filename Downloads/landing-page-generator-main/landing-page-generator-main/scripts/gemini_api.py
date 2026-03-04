"""
Gemini API를 사용하여 상세페이지 섹션 이미지를 생성하는 모듈
Gemini 3 Pro Image Preview 모델 사용
"""

import os
import json
import base64
import time
from pathlib import Path
from typing import Optional
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 3 Pro Image Preview 모델 (Nano Banana Pro)
MODEL_NAME = "gemini-3-pro-image-preview"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"


# Gemini Text 모델
TEXT_MODEL_NAME = "gemini-2.5-flash"
GEMINI_TEXT_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL_NAME}:generateContent"

def generate_text_prompts(brief: dict) -> Optional[dict]:
    """
    Gemini Text API를 사용하여 13개 섹션의 이미지 생성 프롬프트를 동적으로 기획/작성합니다.
    (기존 에이전트 단계들: Intake -> Research -> Copy -> Design -> Prompt Generation 을 하나의 LLM 호출로 통합)
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        return None

    product_name = brief.get("product_name", "제품명")
    features = brief.get("features", "특징 없음")
    
    system_prompt = f"""너는 최고 수준의 한국어 카피라이터이자 랜딩페이지 기획자야. 
네 임무는 사용자가 제공한 제품 정보를 바탕으로 [타겟 리서치 -> 카피라이팅 -> 디자인 기획]을 수행한 뒤, 
최종적으로 Gemini Image API가 렌더링할 수 있는 13개 섹션의 프롬프트를 완벽한 JSON 형식으로 출력하는 거야.

[제품 정보]
- 제품/서비스명: {product_name}
- 제공된 특징/정보: {features}

[기획 및 카피라이팅 가이드 (반드시 적용할 것)]
1. 타겟 리서치: 이 제품을 살 사람들의 진짜 고통(Pain)과 욕구(Desire)를 분석해.
2. Section 01 (Hero): 매력적인 헤드라인과 제품의 핵심 혜택을 보여줘.
3. Section 02 (Pain): 타겟이 겪고 있는 3가지 구체적인 고충을 적어줘 ("이런 고민 하셨나요?").
4. Section 03 (Problem): 그 고충이 고객 탓이 아니라 기존 제품들의 한계 때문임을 지적해.
5. Section 04 (Story): 불편했던 과거(Before)에서 이 제품을 만난 후의 편안한 미래(After)를 대비시켜.
6. Section 05 (Solution): 드디어 이 제품을 해결책으로 제시해.
7. Section 06 (How It Works): 이 제품만의 3가지 특별한 기능/작동 방식을 설명해.
8. Section 07 (Social Proof): 가상의 높은 만족도와 고객 후기 3개를 작성해.
9. Section 08 (Authority): 이 제품을 만든 브랜드의 전문성과 신뢰도를 보여줘.
10. Section 09 (Benefits): 제품을 샀을 때 얻는 혜택들을 나열해.
11. Section 10 (Risk Removal): 100% 만족 보장, 품질 보증 등 구매의 망설임을 없애는 문구를 넣어.
12. Section 11 (Comparison): 일반 제품(X)과 우리 제품(O)의 확실한 차이를 비교해.
13. Section 13 (Final CTA): 마지막으로 강렬한 구매 유도(할인 가격, 한정 혜택 등)를 해.

[프롬프트 작성 필수 규칙]
각 섹션별로 프롬프트(prompt)를 작성할 때, 아래의 내용을 반드시 영문 프롬프트 안에 포함해야 해.
다만, 레이아웃 안에 들어가는 텍스트(Headline, Subheadline, Text 등)는 네가 위에서 기획한 **매력적인 한국어 카피**를 그대로 넣어줘.

모든 prompt의 시작 부분에 아래 스타일 앵커를 반드시 포함해:
"=== CRITICAL REQUIREMENTS ===
1. EXACT DIMENSIONS: Image must be EXACTLY 1200px wide
2. FULL BLEED: Content fills ENTIRE 1200px width with NO margins or borders
3. The attached reference image is the ACTUAL PRODUCT — show this exact product

=== PHOTOGRAPHY STYLE (MANDATORY) ===
- Use REALISTIC PHOTOGRAPHY style, NOT illustrations or cartoons
- The product must look exactly like the reference image
- Professional photography lighting and composition"

[JSON 출력 형식]
13개 섹션 (01_hero, 02_pain, 03_problem, 04_story, 05_solution, 06_how_it_works, 07_social_proof, 08_authority, 09_benefits, 10_risk_removal, 11_comparison, 12_target_filter, 13_final_cta)의 키를 가진 JSON 객체만 반환해. 
마크다운 백틱(```json) 없이 순수 JSON만 출력해.

예시:
{{
  "01_hero": {{
    "prompt": "Create a hero section... [스타일 앵커]... Layout: - Headline: '네가 쓴 한국어 카피' ...",
    "width": 1200,
    "height": 800,
    "filename": "01_hero.png"
  }},
  "02_pain": {{
    "prompt": "...",
    "width": 1200,
    "height": 600,
    "filename": "02_pain.png"
  }}
  // ... 나머지 11개 섹션
}}
"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }

    try:
        print(f"Calling Text API: {TEXT_MODEL_NAME} for copywriting...")
        response = requests.post(
            f"{GEMINI_TEXT_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return None

        result = response.json()
        candidates = result.get("candidates", [])
        if not candidates:
            return None

        text_response = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
        
        # Clean up possible markdown wrappers
        text_response = text_response.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
            
        prompts_dict = json.loads(text_response.strip())
        return prompts_dict

    except Exception as e:
        print(f"Text API Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_image(
    prompt: str,
    output_path: str,
    width: int = 1200,
    height: int = 1200,
    reference_image_path: Optional[str] = None
) -> Optional[str]:
    """
    Gemini API를 사용하여 이미지를 생성합니다.

    Args:
        prompt: 이미지 생성 프롬프트
        output_path: 저장할 파일 경로
        width: 이미지 너비
        height: 이미지 높이
        reference_image_path: 참조 제품 이미지 경로 (멀티모달)

    Returns:
        저장된 파일 경로 또는 None (실패시)
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        return None

    full_prompt = f"""Generate a PHOTOREALISTIC professional image.

=== ABSOLUTE DIMENSION REQUIREMENTS ===
1. EXACT SIZE: {width}x{height} pixels - NO EXCEPTIONS
2. FULL BLEED: Content fills ENTIRE {width}x{height} canvas with NO margins
3. DIMENSION LOCK: Output MUST be exactly {width}x{height} pixels

=== PRODUCT REFERENCE IMAGE ===
The attached image is the ACTUAL PRODUCT being advertised.
You MUST use this exact product appearance in the generated landing page section.
- Maintain the product's exact shape, color, and design details
- Show the product from attractive angles appropriate for the section
- The product in the output must be clearly recognizable as the same product

=== ULTRA-REALISTIC PHOTOGRAPHY STYLE (CRITICAL - MUST FOLLOW) ===

CAMERA QUALITY:
- Shot on professional DSLR (Canon 5D Mark IV / Sony A7R IV quality)
- High resolution, sharp details, professional color grading
- Natural depth of field with beautiful bokeh where appropriate

HUMAN MODELS (when showing people):
- REAL Korean models with NATURAL skin texture
- Natural expressions, professionally styled

PRODUCT PHOTOGRAPHY:
- Show the ACTUAL product from the reference image
- Luxury brand advertising quality
- Realistic reflections, material textures
- Professional studio or lifestyle setting

LIGHTING:
- Professional studio lighting with soft diffusion
- Natural shadows and highlights

ABSOLUTELY AVOID:
- Cartoon, illustration, vector art, or graphic design style
- Changing the product's appearance from the reference image
- Generic stock photo feel
- AI-generated artifacts

=== CONTENT ===
{prompt}

=== FINAL QUALITY CHECKLIST ===
✓ Image is EXACTLY {width}x{height} pixels
✓ Product matches the reference image exactly
✓ Looks like a REAL photograph, not digital art
✓ Could be mistaken for actual brand advertisement
✓ Korean text is elegant and perfectly readable"""

    headers = {
        "Content-Type": "application/json"
    }

    # API payload 구성: 참조 이미지가 있으면 멀티모달
    parts = []

    if reference_image_path and os.path.exists(reference_image_path):
        with open(reference_image_path, "rb") as img_file:
            image_b64 = base64.b64encode(img_file.read()).decode("utf-8")
        ext = Path(reference_image_path).suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")
        parts.append({"inlineData": {"mimeType": mime_type, "data": image_b64}})
        print(f"  Reference image attached: {reference_image_path}")

    parts.append({"text": full_prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }

    try:
        print(f"Calling API: {MODEL_NAME}")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=180  # 3분 타임아웃
        )

        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            error_text = response.text[:500] if len(response.text) > 500 else response.text
            print(f"Response: {error_text}")
            return None

        result = response.json()

        # 응답에서 이미지 데이터 추출
        candidates = result.get("candidates", [])
        if not candidates:
            print("Error: No candidates in response")
            print(f"Full response: {json.dumps(result, indent=2)[:1000]}")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])

        for part in parts:
            if "inlineData" in part:
                image_data = part["inlineData"]["data"]
                mime_type = part["inlineData"].get("mimeType", "image/png")
                image_bytes = base64.b64decode(image_data)

                # 디렉토리 생성
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                print(f"Image saved: {output_path} ({mime_type})")
                return output_path

        # 이미지가 없으면 텍스트 응답 확인
        for part in parts:
            if "text" in part:
                print(f"Text response: {part['text'][:200]}")

        print("Error: No image data in response")
        return None

    except requests.exceptions.Timeout:
        print("Error: Request timed out (180s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed - {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_sections(
    prompts_file: str,
    output_dir: str,
    delay_between: float = 2.0
) -> list:
    """
    모든 섹션 이미지를 순차적으로 생성합니다.

    Args:
        prompts_file: gemini_prompts.json 파일 경로
        output_dir: 출력 디렉토리
        delay_between: API 호출 간 대기 시간 (초)

    Returns:
        생성된 이미지 경로 리스트
    """
    with open(prompts_file, "r", encoding="utf-8") as f:
        prompts_data = json.load(f)

    generated_images = []
    total_sections = len(prompts_data)

    for i, (section_key, section_data) in enumerate(prompts_data.items(), 1):
        print(f"\n[{i}/{total_sections}] Generating {section_key}...")

        prompt = section_data["prompt"]
        width = section_data.get("width", 1200)
        height = section_data.get("height", 600)
        filename = section_data.get("filename", f"{section_key}.png")

        output_path = os.path.join(output_dir, filename)

        result = generate_image(prompt, output_path, width, height)

        if result:
            generated_images.append(result)
        else:
            print(f"Warning: Failed to generate {section_key}")

        # API 레이트 리밋 방지를 위한 대기
        if i < total_sections:
            print(f"Waiting {delay_between}s before next request...")
            time.sleep(delay_between)

    print(f"\nGeneration complete: {len(generated_images)}/{total_sections} images")
    return generated_images


def test_api_connection() -> bool:
    """
    API 연결을 테스트합니다.
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found")
        return False

    print(f"API Key found: {GEMINI_API_KEY[:10]}...")

    # 간단한 텍스트 생성으로 연결 테스트
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": "Say 'API connection successful' in Korean."}]
        }]
    }

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            print("API connection successful!")
            return True
        else:
            print(f"API test failed: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"API test error: {e}")
        return False


if __name__ == "__main__":
    # API 연결 테스트
    print("Testing Gemini API connection...")
    test_api_connection()
