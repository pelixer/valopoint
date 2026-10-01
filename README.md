# valopoint

VCT 지역리그·국제전 **선수 stat** 기반 파워포인트(PP)와 국제전 승부/대진 예측. 개인 사용 웹앱(아이폰 Safari 홈화면 추가).

```
vlr.gg ──scrape──▶ data/rows/*.csv ──model──▶ web/public/data/model.json ──▶ Svelte PWA (GitHub Pages)
                   (선수×맵 단위)      (Python)                              (대진 시뮬은 브라우저에서)
```

## 모델 요약 (`valopoint/model.py`)

| 단계 | 내용 | 편향 방지 |
|---|---|---|
| 1. 입력 | 맵 단위 선수 기록 → 라운드당 KPR·DPR·APR·FKPR·FDPR·ADR·KAST | 경기 길이 편향 제거. Rating/ACS는 같은 입력의 고정 조합이라 제외 |
| 2. 표준화 | 역할군(타격대/척후대/전략가/감시자) 내 표준화 | 역할상 킬이 많은 포지션 우대 방지 |
| 3. 가중치 | 맵 라운드 승률 ~ 양 팀 stat 합 차이 (ridge 회귀) | 가중치를 사람이 정하지 않고 데이터로 학습 |
| 4. 상대 보정 | 관측값 += 상대팀 전력/5 | 약팀 상대로 부풀린 stat 보정 |
| 5. 분해 | θ(선수, 맵, 요원) = 지역 + 선수 + 선수×요원 + 선수×맵 | 계층적 경험적 베이즈 축소(k = σ²/τ², 데이터로 추정). 표본 적은 조합은 선수 전체값으로 수렴 |
| 6. 강건성 | Huber 절단, 시간 감쇠(반감기 180일), 2년 창 | 한 판 폭발·오래된 기록 영향 제한 |

- **PP = 100 + 1000·θ**: 100 = 평균 선수, +10 PP ≈ 팀 라운드 승률 +1%p. 팀 전력 = 로스터 5명 합.
- **지역 보정**: 국내전에서는 지역 항이 상쇄되고 국제전 stat으로만 식별 → 모든 리그를 하나의 스케일로 환산.
- **국제전 2년 성적 반영** (`predict.fit_gamma`): walk-forward로 얻은 *사전(out-of-sample)* 전력 차로
  `logit P = β·logit P_이론(ΔS) + γ_지역A − γ_지역B` 를 최근 2년 국제전 맵 결과에 적합(시간 가중).
- **맵 → 시리즈**: 라운드 승률 q = 0.5 + ΔS → 13선승(연장 포함) 맵 승률 → 밴/픽 순서(Bo1/3/5)대로 각 팀이
  자기에게 가장 불리한 맵 밴, 가장 유리한 맵 픽 → 시리즈 승률(선밴 양쪽 평균).
- **실시간 갱신**: 국제전 진행 중에는 매 경기일마다 재적합. 진행 중 대회 가중치 `w_live`, 반감기, 축소 배수
  `k_mult` 를 `valopoint tune` 으로 과거 대회에 대해 비교(시행착오 단계).

## 사용

```bash
pip install -e '.[dev]'
valopoint events --years 2025 2026     # vlr.gg에서 VCT 이벤트 목록 → data/events.json (검토·수정 가능)
valopoint scrape                        # 이벤트별 매치 페이지 수집 → data/rows/<event_id>.csv (캐시·1.5초 간격)
valopoint players --map lotus --agent omen
valopoint backtest                      # 국제전: 라이브 갱신 vs 대회 전 고정 vs Elo
valopoint tune --grid '{"w_live":[1,2,4],"half_life_days":[90,180,365]}'
valopoint export                        # web/public/data/model.json

valopoint synth /tmp/syn && valopoint --data /tmp/syn export --source synthetic   # 합성 데이터 데모
```

웹앱:

```bash
cd web && npm install && npm run dev     # 로컬
npm test                                 # 엔진(JS) 테스트: Python과 동일 결과 검증
```

## 대진표 추가 (`data/brackets/*.json`)

```json
{
  "id": "champions-2026", "name": "Champions 2026 플레이오프",
  "teams": ["시드1 팀명", "시드2", "..."],
  "matches": [
    {"id": "UB-QF1", "a": "S1", "b": "S8", "best_of": 3, "round": "상위 8강"},
    {"id": "LB-R1A", "a": "L:UB-QF1", "b": "L:UB-QF2", "best_of": 3, "round": "하위 1R"},
    {"id": "GF", "a": "W:UB-F", "b": "W:LB-F", "best_of": 5, "round": "결승"}
  ],
  "final": "GF",
  "results": {"UB-QF1": "승리팀명"}
}
```
`S<n>` = n번 시드, `W:<id>`/`L:<id>` = 해당 경기 승자/패자. 경기는 실행 순서대로 나열.
`results` 는 공식 결과, 앱에서 탭해서 고정하는 결과는 기기에만 저장됩니다(가정 시나리오).
팀명은 vlr.gg 표기와 같아야 합니다.

## 배포

- **GitHub Pages** (`.github/workflows/deploy-pages.yml`): Settings → Pages → Source를 **GitHub Actions**로 한 번 설정.
  주소는 `https://<owner>.github.io/valopoint/` → iPhone Safari에서 열고 공유 → 홈 화면에 추가.
- **데이터 갱신** (`update-data.yml`, 매일 00:00 KST): 이벤트 탐색 → stat 수집 → 대진 갱신 → 모델 재적합 → 재배포.
- **대진 갱신** (`update-bracket.yml`, 매일 12:00 KST): 진행 중인 가장 중요한 대회(국제전 > 퍼시픽 > 아메리카스 > EMEA > CN)의 대진·결과만 갱신.
  수동 실행: Actions 탭 → 워크플로 선택 → Run workflow.

## 현재 상태

- 모델·백테스트·웹앱은 **합성 데이터**로 검증됨 (숨긴 정답 복원: 선수 r≈0.96, 선수×요원 r≈0.64, 약한 지역 식별).
- vlr.gg 파서(`valopoint/scrape/vlr.py`)는 개발 환경에서 vlr.gg 접근이 막혀 **실제 페이지로 아직 검증되지 않음**.
  첫 Actions 실행 로그(매치별 row 수)로 확인 필요.
