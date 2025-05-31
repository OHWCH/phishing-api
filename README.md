# 📞 PhishingBlock - 보이스피싱 탐지 AI API

Flask 기반 보이스피싱 탐지 서버입니다.  
음성 파일을 입력으로 받아 Google STT를 통해 텍스트로 변환하고,  
LSTM 딥러닝 모델로 위험도를 예측한 후,  
필요시 LLM(대형 언어 모델)로 2차 정밀 분석을 수행합니다.

---

## ✅ 주요 기능

- 🎧 음성 파일(STT) → 텍스트 자동 변환
- 🧠 LSTM 모델 기반 보이스피싱 위험도 예측
- 🧠 위험도가 높으면 LLM으로 정밀 분석
- 📦 JSON 형식 응답 반환 (앱 연동 가능)

---

## 🖥️ API 사용법

### 📡 `/analyze` (POST)

**요청**
- Content-Type: `multipart/form-data`
- 파라미터: `audio` (wav 파일)

**응답**
```json
{
  "recognized_text": "안녕하세요 고객님, 대출 조건 안내드립니다",
  "risk_score": 0.8274,
  "model_result": "보이스피싱 의심됨",
  "llm_result": "보이스피싱입니다"
}
