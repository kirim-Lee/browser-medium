LI 스펙

## 개요

Medium 아티클을 이미 로그인된 Chrome 브라우저 세션(browser-harness)으로
크롤링하여 이미지·코드블록을 보존한 채 한국어 Markdown 파일로 저장하는 CLI 도구.

---

## 기술 스택

| 항목            | 선택               | 이유                                                     |
| --------------- | ------------------ | -------------------------------------------------------- |
| 언어            | Python 3.11+       | 파싱/번역 생태계 풍부                                    |
| 크롤링          | `browser-harness`  | 이미 로그인된 Chrome에 CDP로 연결, 별도 세션 관리 불필요 |
| HTML 파싱       | `beautifulsoup4`   | 선택적 요소 처리 편리                                    |
| HTML→MD 변환    | `markdownify`      | 포맷 보존 품질 우수                                      |
| 번역            | `deepl` (공식 SDK) | 공식 API, 월 500k자 무료, 한국어 품질 우수               |
| 번역 검증       | `nltk` + `kss`     | 1차 문장 수 비교 필터 (토큰 0 소모)                      |
| 번역 검증 (LLM) | `anthropic`        | 의심 단락만 Claude API로 정밀 검증                       |
| 이미지 다운로드 | `httpx`            | 비동기 처리 가능                                         |
| CLI             | `click`            | 직관적인 CLI 인터페이스 구성                             |
| 환경변수        | `python-dotenv`    | DeepL·Anthropic API 키 관리                              |

---

## 프로젝트 구조

```
medium-translator/
├── main.py                  # CLI 진입점
├── crawler.py               # browser-harness로 HTML 가져오기
├── parser.py                # HTML 파싱 및 요소 분리
├── translator.py            # DeepL 번역 처리
├── converter.py             # HTML → Markdown 변환
├── downloader.py            # 이미지 다운로드
├── validate.py              # 번역 검증 CLI 진입점
├── validators/
│   ├── nltk_filter.py       # 1단계: 문장 수 비교 (토큰 0)
│   ├── llm_validator.py     # 2단계: Claude API 정밀 검증
│   └── reporter.py          # 3단계: 리포트 생성
├── .env                     # DeepL·Anthropic API 키 (gitignore)
├── .env.example             # 키 템플릿 (커밋 가능)
├── requirements.txt
├── output/                  # 번역 결과 저장 폴더
│   └── {slug}/
│       ├── index.md         # 번역본
│       ├── original.md      # 원문 (검증용)
│       └── images/
│           └── *.png / *.jpg
└── reports/                 # 검증 리포트
    └── {slug}_report.json
```

---

## CLI 인터페이스

### 기본 사용법

```bash
# 단일 아티클 번역
python main.py translate <URL>

# 번역 후 자동 검증까지
python main.py translate <URL> --validate

# 저장 경로 지정
python main.py translate <URL> --output ./my-docs

# 번역 없이 MD만 추출 (원문)
python main.py translate <URL> --no-translate

# 이미지 다운로드 스킵
python main.py translate <URL> --no-images
```

> `save-cookies` 커맨드 없음 — 이미 로그인된 Chrome 세션을 browser-harness가
> 자동으로 사용.

### 옵션 목록

| 옵션             | 기본값     | 설명                             |
| ---------------- | ---------- | -------------------------------- |
| `--output`, `-o` | `./output` | 저장 디렉토리                    |
| `--no-translate` | False      | 번역 스킵, 원문 MD만 저장        |
| `--no-images`    | False      | 이미지 다운로드 스킵             |
| `--lang`         | `KO`       | 번역 대상 언어 코드 (DeepL 형식) |
| `--validate`     | False      | 번역 완료 후 자동 검증 실행      |

---

## 크롤링 방식 (browser-harness)

```python
browser-harness <<'PY'
new_tab("https://medium.com/@user/article-slug")
wait_for_load()
html = js("document.documentElement.outerHTML")
PY
```

- 별도 로그인/쿠키 관리 불필요 — 사용자의 Chrome에 CDP로 연결
- JS 렌더링 완료 후 HTML 추출
- 페이월 아티클도 로그인 세션으로 접근 가능

---

## Slug 추출

URL 마지막 path segment를 그대로 사용:

```
https://medium.com/@user/how-to-build-api-a1b2c3d4e5f6
                         └─────────────────────────────┘
                              출력 폴더: output/how-to-build-api-a1b2c3d4e5f6/
```

```python
from urllib.parse import urlparse
slug = urlparse(url).path.split('/')[-1]
```

---

## 파싱 및 변환 규칙

### Medium 아티클 DOM 구조

Medium은 대부분의 클래스명이 난독화되어 있지만 `pw-` 접두사 클래스는 안정적으로
유지됨.

| 요소            | 셀렉터                                 |
| --------------- | -------------------------------------- |
| 아티클 컨테이너 | `article.meteredContent`               |
| 제목            | `h1.pw-post-title`                     |
| 부제목          | `h2.pw-subtitle-paragraph`             |
| 본문 단락       | `p.pw-post-body-paragraph`             |
| 본문 소제목     | `h2` (pw- 클래스 없는 것, 아티클 내부) |
| 코드블록        | `pre`                                  |
| 이미지          | `figure img`                           |
| 인용구          | `blockquote`                           |

추출 순서는 DOM 순서 그대로 유지 (querySelector**All** → 배열 순회).

### 처리 대상 요소

| 요소                         | 처리 방법                                        |
| ---------------------------- | ------------------------------------------------ |
| 제목 (h1~h4)                 | 번역 후 MD 헤딩으로 변환                         |
| 본문 텍스트                  | 번역                                             |
| 코드블록 (`<pre>`, `<code>`) | **번역 안 함**, 원문 그대로 MD 코드블록으로 변환 |
| 인라인 코드                  | **번역 안 함**, 백틱으로 감싸기                  |
| 이미지 (`<img>`)             | 로컬 다운로드 후 상대경로로 교체                 |
| 링크 (`<a>`)                 | 원문 URL 유지, 링크 텍스트만 번역                |
| 인용구 (`<blockquote>`)      | 번역 후 MD `>` 인용으로 변환                     |
| 수평선, 구분자               | 그대로 유지                                      |

### 코드블록 보호 로직

번역 전 코드블록을 플레이스홀더로 치환 후, 번역 완료 뒤 복원:

```
[CODE_BLOCK_0], [CODE_BLOCK_1] ... 로 임시 치환
→ 텍스트 번역
→ 플레이스홀더를 원본 코드로 복원
```

---

## 출력 Markdown 형식

````markdown
# 번역된 제목

> 원문: [원문 제목](원문 URL)  
> 번역일: 2024-01-01

---

번역된 본문 내용...

![이미지 설명](./images/image1.png)

```python
# 코드블록은 번역 안 함 (원문 그대로)
def hello():
    print("Hello, World!")
```
````

번역된 내용 계속...

````

---

## 이미지 처리

1. `<img>` src URL 수집
2. `./output/{slug}/images/` 폴더에 다운로드
3. MD 내 경로를 `./images/파일명` 으로 교체
4. Medium CDN 이미지, gif, webp 모두 지원

---

## 번역 처리 방식 (DeepL)

```python
import deepl
translator = deepl.Translator(auth_key)
result = translator.translate_text(text, target_lang="KO")
````

- 단락 단위로 번역 요청
- 한 번에 너무 긴 텍스트는 **문단 단위로 분할** 후 순차 번역
- 코드블록은 플레이스홀더로 보호하여 번역 대상에서 제외
- 실패 시 원문 유지 후 로그 출력

### 환경변수 설정

```bash
# .env
DEEPL_AUTH_KEY=your-deepl-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
```

```bash
# .env.example (커밋용)
DEEPL_AUTH_KEY=
ANTHROPIC_API_KEY=
```

---

## 에러 처리

| 상황                      | 처리                              |
| ------------------------- | --------------------------------- |
| 페이월 감지               | 에러 메시지 출력 후 종료          |
| browser-harness 연결 실패 | Chrome 실행 여부 확인 안내 메시지 |
| 이미지 다운로드 실패      | 원본 URL 유지, 경고 로그          |
| 번역 API 실패             | 원문 유지, 경고 로그              |
| DeepL 할당량 초과         | 명확한 에러 메시지 출력 후 종료   |
| 네트워크 타임아웃         | 3회 재시도 후 종료                |
| 검증 중 LLM API 실패      | nltk 결과만 리포트, 경고 로그     |

---

## 의존성 설치

```bash
pip install beautifulsoup4 markdownify deepl httpx click python-dotenv anthropic nltk kss

# nltk 데이터 다운로드 (최초 1회)
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

> `playwright` 불필요 — browser-harness가 Chrome CDP 연결을 담당.

---

## 개발 순서 (추천)

1. Medium 링크 분석 → DOM 셀렉터 확정 (browser-harness로 실시간 탐색)
2. `crawler.py` — browser-harness로 HTML 가져오기
3. `parser.py` — 코드블록/이미지 분리 로직
4. `converter.py` — HTML → MD 변환
5. `translator.py` — DeepL 번역 + 플레이스홀더 처리
6. `downloader.py` — 이미지 로컬 저장
7. `main.py` — CLI 전체 통합

---

## 주의사항

- `.env` 는 반드시 `.gitignore` 에 추가
- DeepL 무료 tier: 월 500,000자 제한
- Medium 구조 변경 시 CSS 셀렉터 업데이트 필요
- 개인 사용 목적으로만 사용 (Medium ToS 준수)
