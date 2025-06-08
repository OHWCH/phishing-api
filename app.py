from flask import Flask, request, jsonify
import os
import stat
import pickle
import numpy as np
import requests
import uuid
from pydub import AudioSegment
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
import speech_recognition as sr

# ✅ [1] ffmpeg 실행 권한 자동 부여
ffmpeg_path = "bin/ffmpeg"
if os.path.exists(ffmpeg_path):
    st = os.stat(ffmpeg_path)
    if not bool(st.st_mode & stat.S_IXUSR):  # 사용자 실행권한 없으면
        os.chmod(ffmpeg_path, st.st_mode | stat.S_IXUSR)

# ✅ [2] ffmpeg 경로 설정
AudioSegment.converter = "./bin/ffmpeg"

# ---------------------- 설정 ----------------------
MODEL_PATH = "phishing_model.h5"
TOKENIZER_PATH = "tokenizer.pkl"
UPLOAD_PATH = "temp.wav"
MAX_LEN = 100
THRESHOLD = 0.5
LLM_API_KEY = os.environ.get("LLM_API_KEY")

# ---------------------- Flask 서버 초기화 ----------------------
app = Flask(__name__)

# ---------------------- 클래스: 모델 로더 ----------------------
class ModelLoader:
    def __init__(self, model_path, tokenizer_path):
        print("🔁 모델과 토크나이저 로딩 중...")
        self.model = load_model(model_path)
        with open(tokenizer_path, "rb") as f:
            self.tokenizer = pickle.load(f)
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
        self.model = model_loader.model
        self.tokenizer = model_loader.tokenizer

    def predict(self, text):
        seq = self.tokenizer.texts_to_sequences([text])
        padded = pad_sequences(seq, maxlen=MAX_LEN)
        score = float(self.model.predict(padded)[0][0])
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
                        "당신은 보이스피싱 탐지 전문가입니다."
                        "아래 문장이 보이스피싱인지 판단해 주세요."
                        "보이스피싱의 기준은 다음과 같습니다\n"
                        "- 금전 요구(송금, 입금, 대출, 투자 권유 등)\n"
                        "- 긴박한 상황 조성(자녀 사고, 검찰·경찰 사칭, 계좌 정지, 개인정보 노출 등)\n"
                        "- 전화나 문자 등으로 개인정보, 금융정보를 요구하거나 조작된 링크 클릭을 유도\n"
                        "- 말투나 단어에서 불안, 협박, 회유, 급박함이 느껴질 경우\n"
                        "- 감정적으로 압박하며 죄책감을 유도하는 경우\n"
                        "- 금전을 빌려달라는 요구를 통해 상대방을 공범으로 만들려는 경우가 있는경우\n"
                        "해당 문장이 위 **기준에 부합하면 “보이스피싱입니다”**, **그렇지 않으면 “정상 대화입니다”** 라고 **딱 한 문장만 출력**하십시오."
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
model_loader = ModelLoader(MODEL_PATH, TOKENIZER_PATH)
stt = STTProcessor()
analyzer = RiskAnalyzer(model_loader)
llm = LLMAnalyzer(LLM_API_KEY)

# ---------------------- API 라우터 ----------------------
@app.route("/analyze", methods=["POST"])
def analyze_audio():
    if "audio" not in request.files:
        return jsonify({"error": "audio 파일이 필요합니다."}), 400

    # 🔧 1. 임시 파일 경로 설정
    temp_id = uuid.uuid4().hex
    temp_3gp_path = f"{temp_id}.3gp"
    temp_wav_path = f"{temp_id}.wav"

    # 🔧 2. 3gp 파일 저장
    audio = request.files["audio"]
    audio.save(temp_3gp_path)

    try:
        # 🔧 3. 3gp → wav 변환
        audio_segment = AudioSegment.from_file(temp_3gp_path, format="3gp")
        audio_segment.export(temp_wav_path, format="wav")
        
        # 4. STT 처리
        text = stt.transcribe(temp_wav_path)
        if text is None:
            return jsonify({"error": "음성을 인식하지 못했습니다."}), 400

        # 5. 모델 예측
        score = analyzer.predict(text)
        result = "보이스피싱 의심됨" if score > THRESHOLD else "정상 대화"

        # 6. LLM 분석
        llm_result = None
        if score > THRESHOLD:
            llm_result = llm.analyze(text)

            # 결과 검증
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
        # 🔧 7. 임시 파일 삭제
        for f in [temp_3gp_path, temp_wav_path]:
            if os.path.exists(f):
                os.remove(f)

# ---------------------- 서버 실행 ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
