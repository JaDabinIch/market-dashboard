# 증시 각도기 · 시장 대시보드

원자재 · 환율 · 금리 가격을 매일 오전 **6:40 (한국시간)** 에 자동으로 기록하고,
**당일 종가와 직전 거래일(전일) 종가를 비교**해서 보여주는 웹페이지입니다.
GitHub Pages 로 호스팅되며, GitHub Actions 가 매일 스스로 데이터를 갱신합니다.
(내 컴퓨터·이 세션과 무관하게 GitHub 서버에서 자동으로 돌아갑니다.)

접속 주소: `https://<내-깃허브아이디>.github.io/<저장소이름>`

---

## 추적 항목 (총 25개)

| 그룹 | 항목 |
|------|------|
| **원자재** | WTI, 브렌트, 가솔린, VIX, 금, 은, 구리, 알루미늄, 비트코인 |
| **환율** | 달러지수, 유로/달러, 달러/엔, 달러/위안, 달러/원, 유로/원, 엔/원 |
| **금리** | 미국 10·5·2·1년물·3개월물·30년물, 일본 10·30년물, 독일 10년물 |

데이터 소스(모두 무료·회원가입 불필요): 미국 국채는 **미국 재무부** 공식 일별 금리,
그 외는 **stooq.com** 일별 종가, 예비 소스로 **Yahoo Finance**.

---

## 처음 한 번만 하는 설정 (약 5분)

### 1. GitHub 저장소 만들기
1. https://github.com 에서 로그인 (계정이 없으면 무료 가입)
2. 오른쪽 위 **＋ → New repository**
3. **Repository name**: 예) `market-dashboard`
4. **Public** 선택 (GitHub Pages 무료 사용을 위해 공개로 둡니다)
5. **Create repository** 클릭

### 2. 파일 올리기
받은 압축파일(`market-dashboard.zip`)을 풀면 아래 구조가 나옵니다. 폴더 구조를 그대로 유지해야 합니다.

```
├─ index.html                    ← 화면 (자동 생성/갱신됨)
├─ template.html                 ← 디자인 템플릿
├─ fetch_data.py                 ← 데이터 수집 스크립트
├─ requirements.txt
├─ data/
│   └─ history.json              ← 누적 데이터 (자동 갱신됨)
└─ .github/
    └─ workflows/
        └─ update.yml            ← 매일 자동 실행 설정
```

올리는 방법 (둘 중 하나):

- **드래그앤드롭(쉬움)**: 저장소 첫 화면의 *uploading an existing file* 링크 클릭 →
  압축을 푼 폴더 안의 **모든 파일과 폴더**를 그대로 끌어다 놓기 → *Commit changes*.
  (`.github` 폴더가 안 보이면 숨김폴더 표시를 켜거나, 아래 git 방식을 사용하세요.)
- **git 사용(권장, `.github`까지 확실히 올라감)**:
  ```bash
  cd market-dashboard
  git init
  git add .
  git commit -m "first commit"
  git branch -M main
  git remote add origin https://github.com/<내아이디>/<저장소이름>.git
  git push -u origin main
  ```

### 3. Actions 쓰기 권한 켜기
저장소 → **Settings** → **Actions** → **General** →
아래 **Workflow permissions** 에서 **Read and write permissions** 선택 → **Save**.
(자동화가 갱신된 데이터를 저장소에 커밋하려면 필요합니다.)

### 4. GitHub Pages 켜기
저장소 → **Settings** → **Pages** →
**Source** 를 **Deploy from a branch** 로,
**Branch** 를 **main / (root)** 로 지정 → **Save**.
잠시 뒤 접속 URL(`https://<아이디>.github.io/<저장소이름>`)이 표시됩니다.

### 5. 첫 데이터 채우기 (즉시 실행)
저장소 → **Actions** 탭 → 왼쪽 **시장 데이터 업데이트** →
오른쪽 **Run workflow** 버튼 클릭.
1~2분 뒤 실행이 끝나면 `index.html` 에 실제 값이 채워지고, 페이지가 갱신됩니다.
(파일을 처음 푸시할 때도 자동으로 한 번 실행됩니다.)

끝입니다. 이후에는 **매일 오전 6:40(KST)** 에 자동으로 갱신됩니다.
> GitHub Actions 스케줄은 서버 사정에 따라 몇 분 늦게 실행될 수 있습니다(정상).

---

## 자주 하는 것

### 항목 추가 / 제거 / 순서 변경
`fetch_data.py` 파일 위쪽의 `GROUPS` 목록만 수정하면 됩니다. 예:
```python
{"key": "ng", "name": "천연가스", "icon": "🔥", "dec": 3, "thousands": False,
 "sources": [("stooq", "ng.f"), ("yahoo", "NG=F")]},
```
- `key`: 내부 식별자(영문, 겹치지 않게)
- `dec`: 소수점 자리수 · `thousands`: 천단위 콤마 여부
- `sources`: 순서대로 시도할 소스. `("stooq","심볼")`, `("yahoo","심볼")`, 미국채는 `("ust","10 Yr")`

수정 후 저장소에 커밋하면 다음 실행부터 반영됩니다.

### 기록 시각 바꾸기
`.github/workflows/update.yml` 의 `cron: "40 21 * * *"` 값을 바꿉니다.
값은 **UTC 기준**이며 `분 시 * * *` 순서입니다.
한국시간 06:40 = UTC 21:40 → `40 21 * * *`.
(예: 한국시간 08:00 → UTC 23:00 → `0 23 * * *`)

### 로고 넣기
저장소 **최상위**(`index.html` 과 같은 위치)에 로고 이미지를 **`logo.png`** 라는 이름으로 올리면
오른쪽 위에 자동으로 표시됩니다. (흰색 로고 권장 — 배경이 어둡습니다.)
`logo.png` 가 없으면 기본 "증시 각도기" 텍스트가 대신 표시됩니다.
크기를 바꾸려면 `template.html` 의 `.brand-logo` 의 `height:34px` 값을 조정하세요.

### 디자인 색/글꼴 손보기
`template.html` 상단 `:root` 의 색상 변수(`--up` 상승 빨강, `--down` 하락 파랑 등)와
CSS 를 수정하면 됩니다.

---

## 참고 / 알아두기

- **구리·알루미늄 단위**: 무료로 안정적으로 받을 수 있는 소스를 기준으로 표시합니다.
  구리는 미국 선물(약 4.3 USD/lb), 알루미늄은 약 2,600 USD/t 수준으로 나옵니다.
  특정 단위(예: LME, 원화 환산)를 원하시면 알려주세요 — 소스를 바꿔 드립니다.
- **주말·공휴일**: 시장이 닫혀 있으면 값이 직전 거래일과 같아 변화가 0으로 표시됩니다(정상).
- **어떤 항목이 비어(—) 보일 때**: Actions 실행 로그에서 해당 항목의
  `[WARN] ... 모든 소스 실패` 메시지를 확인하면 원인을 알 수 있습니다. 심볼만 바꾸면 대부분 해결됩니다.
- 데이터는 참고용이며, 투자 판단 전에는 원자료를 확인하세요.
