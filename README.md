# valopoint

VCT 지역 리그 성적 → 국제 대회(Masters/Champions) 파워 스코어 및 대진표 승부예측. 개인 사용, 비상업.

## 모델
- **2단계 Elo**: 유효 전력 = 팀 레이팅 + 지역 레이팅. 국내전은 지역 항이 상쇄되고, 국제전 결과가 팀과 지역 오프셋을 함께 갱신 → 지역 리그 성적이 글로벌 전력으로 연결됨.
- 세트 점수(+선택적 라운드 득실) 마진 반영, 비활동 시 지역 평균으로 회귀(로스터/시즌 변동).
- Bo1/3/5 시리즈 확률은 맵 승률에서 계산, 대진표는 몬테카를로(임의 더블엘리미/GSL 포맷을 JSON DAG로 정의).
- `backtest`: 과거 데이터만으로 국제전을 walk-forward 예측(log loss / Brier / accuracy).

## 사용
    pip install -e '.[dev]'
    valopoint synth data/sample_synth.csv      # 합성 데모 데이터(실제 VCT 데이터 아님)
    valopoint rank data/sample_synth.csv
    valopoint predict data/sample_synth.csv AMER_T1 PAC_T1 --bo 3
    valopoint bracket data/sample_synth.csv examples/masters_8team_double_elim.json
    valopoint backtest data/sample_synth.csv

입력 CSV 스키마는 `valopoint/data.py` 참고.

## 다음 단계
1. 실제 데이터 수집기(CSV 출력) — 소스 결정 필요(아래 질문).
2. 맵/에이전트 풀, 선수 단위 stat(ACS, rating) 기반 피처로 확장, 하이퍼파라미터 튜닝(backtest 기준).
