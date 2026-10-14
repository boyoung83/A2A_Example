# 교대 인수인계 보고서 생성기

작업 메모를 Claude API(`claude-opus-5-5`)로 정리해 **발생한 일 / 조치한 내용 / 현재 상태 / 다음 근무자 확인 사항 / 미확인 사항**으로 나눈 보고서를 만듭니다. 결과는 화면에 출력되고 `reports/` 폴더에 텍스트 파일로 저장됩니다.

## 1. 설치

```powershell
python -m pip install -r requirements.txt
```

Python 3.10 이상이 필요합니다.

## 2. API 키 설정

`.env.example`을 `.env`로 복사하고 키를 넣습니다. `.env`는 `.gitignore`에 들어 있어 git에 올라가지 않습니다.

```
ANTHROPIC_API_KEY=sk-ant-...
```

`ANTHROPIC_API_KEY` 환경변수가 설정되어 있으면 `.env`보다 우선합니다.

## 3. 실행

```powershell
# 메모를 직접 붙여넣기 (빈 줄에서 Enter 두 번으로 입력 끝)
python handover_report.py

# 메모 파일 하나
python handover_report.py --file 참고\작업메모_01_라벨이상.txt

# 폴더 안의 메모(.txt) 전부, 각각 보고서 생성
python handover_report.py --dir 참고

# 저장 폴더 지정
python handover_report.py --file 메모.txt --out 보고서
```

저장 파일 이름: `reports/인수인계_<원본이름>_<YYYYMMDD_HHMMSS>.txt` (원문 메모가 보고서 끝에 함께 붙습니다)

## 4. 보고서 읽는 법

- `- 메모에 기록 없음`: 메모에 그 항목에 해당하는 내용이 없음
- `- ○○: 미확인`: 메모에서 확인하지 못했다고 했거나, 기록이 없는 원인·수량·시각
- `※ 자동 점검 경고`: 프로그램이 원문과 대조해 의심스러운 부분을 찾은 것입니다.
  - 원문에 없는 숫자 (예: 메모에 없는 라벨 수량)
  - 원문에 없는 근거 문장
  - 원문에 없는 "해결/완료/정상화" 같은 단정 표현

  경고가 있으면 해당 문장을 원문 메모와 직접 대조하세요. 경고가 있어도 보고서는 저장됩니다.

## 5. 테스트

```powershell
python -m pytest
```

API를 호출하지 않는 테스트입니다.
