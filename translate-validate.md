# 번역 검증 파이프라인 스펙

## 개요

번역된 Markdown 파일을 자동으로 검증하는 파이프라인. nltk로 1차 필터링 후 문제
단락만 LLM에 넘겨 토큰 사용량을 최소화.

---

## 설계 원칙

- **토큰 절약 우선**: nltk로 무해한 단락을 걸러내고, 의심스러운 단락만 LLM 검증
- **단락 단위 처리**: 문서 전체가 아닌 단락 단위로 비교
- **비파괴적**: 원본 번역 파일을 수정하지 않고 리포트만 출력
- **선택적 자동수정**: 플래그된 단락을 재번역할지 사람이 결정

---

## 파일 구조

```
medium-translator/
├── validate.py              # CLI 진입점
├── validators/
│   ├── nltk_filter.py       # 1단계: 문장 수 비교 (토큰 0)
│   ├── llm_validator.py     # 2단계: Claude API 정밀 검증
│   └── reporter.py          # 3단계: 리포트 생성
├── reports/
│   └── {slug}_report.json   # 검증 결과 저장
└── output/
    └── {slug}/
        ├── index.md         # 번역본 (검증 대상)
        └── original.md      # 원문 — main.py가 번역과 함께 자동 저장
```

> `original.md`는 `main.py translate` 실행 시 항상 함께 저장됨. 별도 생성
> 불필요.

---

## 파이프라인 단계

### 1단계 — nltk 필터 (토큰 0 소모)

원문과 번역의 단락별 문장 수를 비교해 의심스러운 단락을 추출.

```python
import nltk

def detect_missing_sentences(src_paragraphs, tgt_paragraphs):
    """
    단락별 문장 수 비교.
    차이가 THRESHOLD 이상인 단락 인덱스를 반환.
    """
    flagged = []

    for i, (src, tgt) in enumerate(zip(src_paragraphs, tgt_paragraphs)):
        src_count = len(nltk.sent_tokenize(src, language='english'))
        tgt_count = len(nltk.sent_tokenize(tgt))  # 한국어는 마침표 기준

        if abs(src_count - tgt_count) > SENTENCE_DIFF_THRESHOLD:
            flagged.append({
                "index": i,
                "src_count": src_count,
                "tgt_count": tgt_count,
                "diff": abs(src_count - tgt_count)
            })

    return flagged
```

**SENTENCE_DIFF_THRESHOLD 기본값: 1**

- 1문장 이상 차이나면 플래그
- 기술문서 특성상 긴 문장이 많아 너무 엄격하면 오탐 증가
- CLI 옵션으로 조정 가능

**한국어 문장 분리 주의사항**

- nltk 기본 tokenizer는 한국어 마침표(`。`, `.`) 기준
- `kss` (Korean Sentence Splitter) pip 패키지로 교체하면 정확도 향상

```python
# 선택적으로 kss 사용
try:
    import kss
    tgt_count = len(kss.split_sentences(tgt))
except ImportError:
    tgt_count = len(nltk.sent_tokenize(tgt))
```

---

### 2단계 — LLM 검증 (플래그된 단락만)

1단계에서 플래그된 단락만 Claude API로 검증.

```python
def validate_paragraph_with_llm(src_para, tgt_para):
    prompt = """
    아래는 영어 원문과 한국어 번역입니다.
    다음 항목을 검증하고 JSON으로만 응답하세요. 다른 텍스트는 출력하지 마세요.

    원문:
    {src}

    번역:
    {tgt}

    응답 형식:
    {{
        "missing_sentences": bool,       // 누락된 문장 여부
        "meaning_distorted": bool,       // 의미 왜곡 여부
        "issue_description": str | null, // 문제 설명 (없으면 null)
        "suggestion": str | null         // 수정 제안 (없으면 null)
    }}
    """.format(src=src_para, tgt=tgt_para)

    # Claude API 호출
    response = call_claude_api(prompt)
    return parse_json_response(response)
```

**LLM 호출 최적화**

- 단락이 짧으면 (100자 미만) LLM 검증 스킵
- 코드블록 단락은 검증 스킵
- 배치 처리: 플래그된 단락 여러 개를 한 번에 요청 가능

---

### 3단계 — 리포트 생성

```json
{
  "file": "output/article-slug/index.md",
  "validated_at": "2024-01-01T00:00:00",
  "summary": {
    "total_paragraphs": 30,
    "nltk_flagged": 4,
    "llm_confirmed_issues": 1,
    "tokens_used": 850,
    "tokens_saved_estimate": 14200
  },
  "issues": [
    {
      "paragraph_index": 7,
      "src_sentence_count": 4,
      "tgt_sentence_count": 2,
      "llm_confirmed": true,
      "issue_description": "3번째 문장이 번역에서 누락됨",
      "suggestion": "... 번역 제안 ...",
      "src_text": "...",
      "tgt_text": "..."
    }
  ],
  "nltk_only_flags": [
    {
      "paragraph_index": 12,
      "note": "LLM 검증 결과 문제 없음 (오탐)"
    }
  ]
}
```

---

## CLI 인터페이스

```bash
# 기본 검증 (output/{slug}/ 경로 자동 참조)
python validate.py output/article-slug/

# 파일 직접 지정
python validate.py <translated_md_file> <original_md_file>

# 임계값 조정
python validate.py index.md original.md --threshold 2

# nltk 필터만 (LLM 호출 없음, 무료)
python validate.py index.md original.md --nltk-only

# 문제 단락 자동 재번역
python validate.py index.md original.md --auto-fix

# 리포트 저장 경로 지정
python validate.py index.md original.md --report ./reports/
```

### 옵션 목록

| 옵션           | 기본값       | 설명                      |
| -------------- | ------------ | ------------------------- |
| `--threshold`  | `1`          | 문장 수 차이 허용 범위    |
| `--nltk-only`  | False        | LLM 호출 없이 nltk만 실행 |
| `--auto-fix`   | False        | 문제 단락 자동 재번역     |
| `--skip-short` | `100`        | 이 글자 수 미만 단락 스킵 |
| `--report`     | `./reports/` | 리포트 저장 경로          |
| `--no-report`  | False        | 리포트 파일 저장 안 함    |

---

## medium-translator 파이프라인 연동

`main.py translate --validate` 플래그로 번역 완료 후 자동 실행.

변경 사항:

1. **`original.md` 자동 저장** — 번역 전 원문 블록을 `converter.py`로 변환해
   함께 저장. `main.py` 5줄 추가로 해결.

2. **`--validate` 플래그** — 번역 완료 후 `run_validator(md_path, src_path)`
   호출.

```python
# main.py (연동 부분, 동기 방식)
original = blocks_to_markdown(title, blocks, url)          # 번역 전 블록 사용
(output_dir / "original.md").write_text(original, encoding="utf-8")

# --validate 플래그가 있을 때만 실행
if validate:
    from validators.reporter import run_validator
    report = run_validator(output_dir / "index.md", output_dir / "original.md")
    issues = report["summary"]["llm_confirmed_issues"]
    if issues > 0:
        click.echo(f"[warn] {issues}개 단락에 문제가 있습니다 — 리포트: {report['report_path']}")
    else:
        click.echo("검증 완료 — 이슈 없음")
```

---

## 토큰 절약 효과 추정

아티클 평균 30단락 기준:

| 방식             | 토큰 소모 | 비용 (Claude Sonnet 기준) |
| ---------------- | --------- | ------------------------- |
| 전체 LLM 검증    | ~15,000   | ~$0.045                   |
| nltk 필터 후 LLM | ~800      | ~$0.002                   |
| **절약률**       | **~95%**  | **~$0.043 절약**          |

100편 번역 기준 누적 절약: ~$4.3

---

## 의존성

```bash
pip install nltk kss anthropic

# nltk 데이터 다운로드 (최초 1회)
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

### 환경변수

```bash
# .env
ANTHROPIC_API_KEY=your-anthropic-key-here
```

---

## 개발 순서

1. `nltk_filter.py` — 문장 수 비교 로직
2. `kss` 연동 — 한국어 문장 분리 정확도 향상
3. `llm_validator.py` — Claude API 연동 + JSON 파싱
4. `reporter.py` — 리포트 생성 및 저장
5. `validate.py` — CLI 통합
6. `main.py` 연동 — 번역 파이프라인에 자동 실행 추가
