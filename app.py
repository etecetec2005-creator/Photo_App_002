import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import base64

# --- セキュリティ設定 ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

st.set_page_config(page_title="自動写真保存", layout="centered")
st.title("📸 写真の中身")

# --- 住所取得用スクリプト (撮影前に住所を確定) ---
# window.parent.postMessage を使い、Streamlitのコンポーネント経由でPythonに住所を戻す
st.components.v1.html("""
<script>
    const sendToStreamlit = (data) => {
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: data
        }, '*');
    };

    navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
                headers: { 'Accept-Language': 'ja' }
            });
            const data = await res.json();
            const addr = data.address;
            const finalAddr = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
            sendToStreamlit(finalAddr || "住所不明");
        } catch (e) {
            sendToStreamlit("住所取得失敗");
        }
    }, (err) => {
        sendToStreamlit("位置情報許可なし");
    }, { enableHighAccuracy: true });
</script>
""", height=0)

# JSからの戻り値を st.query_params などではなくコンポーネントの値として受け取る
# ※以下の camera_input より上に配置することで撮影時に住所が確定している確率を高めます
current_addr = st.session_state.get("last_addr", "住所取得中...")

img_file = st.camera_input("写真を撮る")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存中...")

    # 2. AI解析（タイトル生成 ＋ 住所からの最寄駅特定）
    ai_title = "名称未設定"
    near_station = "駅名特定中"
    
    with st.spinner("AIがタイトルと最寄駅を特定しています..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            # AIに「この住所の最寄駅」と「タイトル」を同時に答えさせる
            prompt = f"""
            以下の情報に基づいて回答してください。
            【現在の住所】: {current_addr}

            指示:
            1. 提供された【現在の住所】から判断して、最も近い「駅名」を1つ答えてください（例: 新大阪駅）。
            2. 写真の内容を分析し、15文字以内の短い「タイトル」を付けてください。

            回答形式（これ以外出力しないでください）:
            タイトル: [タイトル]
            駅名: [駅名]
            """
            response = model.generate_content([prompt, img])
            if response.text:
                lines = response.text.split("\n")
                for line in lines:
                    if "タイトル:" in line:
                        ai_title = line.replace("タイトル:", "").strip().replace("/", "-")
                    if "駅名:" in line:
                        near_station = line.replace("駅名:", "").strip().replace("/", "-")
        except:
            pass

    # 3. PDF生成用のBase64変換（最高画質）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動保存JavaScript
    st.success(f"確定: {ai_title} / {current_addr} / {near_station}")
    
    save_pdf_script = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (function() {{
        const fileName = "{ai_title}_{current_addr}_{near_station}.pdf";
        const {{ jsPDF }} = window.jspdf;
        const doc = new jsPDF();
        
        const originalWidth = {width};
        const originalHeight = {height};
        const maxWidth = 190;
        const maxHeight = 260;
        let printWidth = maxWidth;
        let printHeight = (originalHeight * maxWidth) / originalWidth;

        if (printHeight > maxHeight) {{
            printHeight = maxHeight;
            printWidth = (originalWidth * maxHeight) / originalHeight;
        }}

        doc.addImage("data:image/jpeg;base64,{img_str}", 'JPEG', 10, 20, printWidth, printHeight, undefined, 'NONE');
        doc.save(fileName);
    }})();
    </script>
    """
    st.components.v1.html(save_pdf_script, height=0)
