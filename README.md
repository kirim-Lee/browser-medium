# browser-medium

Medium 아티클을 크롤링해 이미지·코드블록을 보존한 채 한국어 Markdown으로
번역하는 CLI 도구.

## 필수 설치

**1. Python 패키지**

```bash
pip install beautifulsoup4 markdownify deepl httpx click python-dotenv nltk kss pygments
```

**2. nltk 데이터 (최초 1회)**

```bash
python3 -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

**3. Node 패키지**

```bash
npm install
```

**4. browser-harness**

```bash
git clone https://github.com/browser-use/browser-harness ~/Developer/browser-harness
cd ~/Developer/browser-harness
uv tool install -e .
```

**5. 환경변수**

```bash
cp .env.example .env
```

`.env`에 DeepL API 키 입력:

```
DEEPL_AUTH_KEY=your-key-here
```

> DeepL 무료 키 발급: [deepl.com/en/pro-api](https://www.deepl.com/en/pro-api)
> (월 500k자 무료)

---

## 최초 실행 — Medium 로그인

전용 Chrome 프로필에 Medium 로그인이 필요합니다 **(최초 1회)**.

```bash
npm run chrome
```

Chrome이 열리면 Medium에 로그인 후 창을 닫으세요. 이후부터는 자동 로그인이
유지됩니다.

---

## 매번 실행 전 — Chrome 시작

번역 전에 Chrome을 먼저 백그라운드로 실행해야 합니다.

```bash
npm run chrome &
```

---

## 사용법

### 번역 + 검증 한번에

```bash
npm run run-all -- https://medium.com/...
```

### 번역만

```bash
npm run translate -- https://medium.com/...
npm run translate -- https://medium.com/... --no-images
npm run translate -- https://medium.com/... --lang EN  # 번역 언어 변경
```

### 번역 품질 검증

```bash
npm run validate -- output/{slug}/
npm run validate -- output/{slug}/ --nltk-only   # LLM 없이 빠른 검증
npm run validate -- output/{slug}/ --auto-fix    # 이슈 자동 수정
```

### 미리보기

```bash
npm run preview -- {slug}
```

---

## 출력 구조

```
output/
└── {slug}/
    ├── index.md      # 번역본
    ├── original.md   # 원문 (검증용)
    └── images/
        └── *.png / *.jpg

reports/
└── {slug}_report.json  # 검증 리포트
```
