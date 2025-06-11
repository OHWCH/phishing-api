from flask import Flask, request, jsonify
import os
import pickle
import uuid
import requests
import speech_recognition as sr
from sentence_transformers import SentenceTransformer
import numpy as np

# ---------------------- 설정 ----------------------
MODEL_PATH = "sbert_classifier.pkl"
UPLOAD_PATH = "temp.wav"
THRESHOLD = 0.5
LLM_API_KEY = os.environ.get("LLM_API_KEY")

# ---------------------- Flask 서버 초기화 ----------------------
app = Flask(__name__)

# ---------------------- 클래스: 모델 로더 ----------------------
class ModelLoader:
    def __init__(self, model_path):
        print("🔁 SBERT 임베딩 모델과 분류기 로딩 중...")
        self.sbert = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        with open(model_path, "rb") as f:
            self.classifier = pickle.load(f)
        print("✅ 모델 로딩 완료!")

# ---------------------- 클래스: 음성 인식기 ----------------------
class STTProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def transcribe(self, audio_path):
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data, language="ko-KR")
                return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            raise Exception(f"Google STT 오류: {str(e)}")

# ---------------------- 클래스: 위험도 예측기 ----------------------
class RiskAnalyzer:
    def __init__(self, model_loader):
        self.sbert = model_loader.sbert
        self.classifier = model_loader.classifier

    def predict(self, text):
        embedding = self.sbert.encode([text])
        score = float(self.classifier.predict_proba(embedding)[0][1])  # 보이스피싱 확률
        return score

# ---------------------- 클래스: LLM 분석기 ----------------------
class LLMAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key

    def analyze(self, text):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "tngtech/deepseek-r1t-chimera:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 보이스피싱 탐지 전문가입니다. "
                        "아래 문장이 보이스피싱인지 판단해 주세요. "
                        "보이스피싱의 기준은 다음과 같습니다\n"
                        "- 금전 요구(송금, 입금, 대출, 투자 권유 등)\n"
                        "- 긴박한 상황 조성(자녀 사고, 검찰·경찰 사칭, 계좌 정지, 개인정보 노출 등)\n"
                        "- 전화나 문자 등으로 개인정보, 금융정보를 요구하거나 조작된 링크 클릭을 유도\n"
                        "- 말투나 단어에서 불안, 협박, 회유, 급박함이 느껴질 경우\n"
                        "- 감정적으로 압박하며 죄책감을 유도하는 경우\n"
                        "- 금전을 빌려달라는 요구를 통해 상대방을 공범으로 만들려는 경우가 있는경우\n"
                        "해당 문장이 위 기준에 부합하면 “보이스피싱입니다”, 그렇지 않으면 “정상 대화입니다” 라고 **딱 한 문장만 출력**하십시오."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"].strip()
                return result
            else:
                return "LLM 분석 오류"
        except Exception as e:
            return f"LLM 연결 실패: {str(e)}"

# ---------------------- 초기화 ----------------------
model_loader = ModelLoader(MODEL_PATH)
stt = STTProcessor()
analyzer = RiskAnalyzer(model_loader)
llm = LLMAnalyzer(LLM_API_KEY)

# ---------------------- API 라우터 ----------------------
@app.route("/analyze", methods=["POST"])
def analyze_audio():
    if "audio" not in request.files:
        return jsonify({"error": "audio 파일이 필요합니다."}), 400

    temp_filename = f"{uuid.uuid4().hex}.wav"
    audio = request.files["audio"]
    audio.save(temp_filename)

    try:
        text = stt.transcribe(temp_filename)
        if text is None:
            return jsonify({"error": "음성을 인식하지 못했습니다."}), 400

        score = analyzer.predict(text)
        result = "보이스피싱 의심됨" if score > THRESHOLD else "정상 대화"

        llm_result = None
        if score > THRESHOLD:
            llm_result = llm.analyze(text)
            if llm_result not in ["보이스피싱입니다", "정상 대화입니다"]:
                llm_result = "LLM 분석 오류 또는 판단 불가"

        return jsonify({
            "recognized_text": text,
            "risk_score": score,
            "model_result": result,
            "llm_result": llm_result or "LLM 분석 생략됨"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.route("/analyze_text", methods=["POST"])
def analyze_text():
    data = request.get_json()
    text = data.get("text")
    if not text:
        return jsonify({"error": "text 필드가 없습니다."}), 400

    try:
        score = analyzer.predict(text)
        result = "보이스피싱 의심됨" if score > THRESHOLD else "정상 대화"

        llm_result = None
        if score > THRESHOLD:
            llm_result = llm.analyze(text)
            if llm_result not in ["보이스피싱입니다", "정상 대화입니다"]:
                llm_result = "LLM 분석 오류 또는 판단 불가"
        else:
            llm_result = "LLM 분석 생략됨"

        return jsonify({
            "recognized_text": text,
            "risk_score": score,
            "model_result": result,
            "llm_result": llm_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------- 서버 실행 ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
