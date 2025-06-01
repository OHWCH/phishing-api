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

### 🔗 엔드포인트

- **URL**: https://phishing-api-yp4n.onrender.com
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **요청 필드**: `audio` (.wav 음성 파일)

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
```
---

## 안드로이드 연동

### 1. 라이브러리 추가 (build.gradle)
```gradle
implementation 'com.squareup.retrofit2:retrofit:2.9.0'
implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
implementation 'com.squareup.okhttp3:okhttp:4.9.3'
```

### 2. 인터페이스 정의
```java
@Multipart
@POST("/analyze")
Call<ResponseBody> analyzeAudio(@Part MultipartBody.Part audio);
```

### 3. Retrofit 설정
```java
Retrofit retrofit = new Retrofit.Builder()
    .baseUrl("https://phishing-api-yp4n.onrender.com")
    .addConverterFactory(GsonConverterFactory.create())
    .build();

ApiService apiService = retrofit.create(ApiService.class);
```

### 4. 오디오 파일 전송
```java
File audioFile = new File(audioPath);  // .wav 파일 경로
RequestBody requestFile = RequestBody.create(MediaType.parse("audio/wav"), audioFile);
MultipartBody.Part body = MultipartBody.Part.createFormData("audio", audioFile.getName(), requestFile);

Call<ResponseBody> call = apiService.analyzeAudio(body);
call.enqueue(new Callback<ResponseBody>() {
    @Override
    public void onResponse(Call<ResponseBody> call, Response<ResponseBody> response) {
        if (response.isSuccessful()) {
            try {
                String result = response.body().string();
                Log.d("PhishingAPI", result);
                // TODO: JSON 파싱 후 UI 처리
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    @Override
    public void onFailure(Call<ResponseBody> call, Throwable t) {
        Log.e("PhishingAPI", "서버 연결 실패", t);
    }
});
```

## ⚠️ 유의사항
- audio 키는 반드시 **파일 형식(form-data)**으로 전송해야 합니다.
- 음성 파일은 .wav (PCM) 포맷만 지원됩니다.
- 응답의 risk_score가 0.5 초과일 경우 보이스피싱 의심으로 판단합니다.
- llm_result는 "보이스피싱입니다" 또는 "정상 대화입니다" 중 한 문장으로 반환됩니다.
- 서버가 유휴 상태였다면 첫 요청에 약간의 지연이 발생할 수 있습니다. 첫 요청 전에는 항상 서버가 유휴상태일 겁니다.
- 서버 오류 또는 예외 발생 시, 응답 내에 "error" 필드가 포함될 수 있습니다.
