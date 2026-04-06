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

# JavaScriptから住所を受け取るための空枠
if "js_address" not in st.session_state:
    st.session_state.js_address = None

# 1. 住所を先に特定するための隠しJS
# ページ読み込み時および撮影時に住所を特定し、Streamlitのクエリパラメータ経由で値を戻す
addr_js = """
<script>
navigator.geolocation.getCurrentPosition(async (pos) => {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
        headers: { 'Accept-Language': 'ja' }
    });
    const data = await res.json();
    const addr = data.address;
    const finalAddr = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
    const url = new URL(window.location.href);
    url.searchParams.set("address", finalAddr);
    window.history.replaceState({}, "", url);
}, (err) => {}, { enableHighAccuracy: true });
</script>
"""
st.components.v1.html(addr_js, height=0)

# URLパラメータから住所を取得
current_addr = st.query_params.get("address", "住所取得中...")

img_file = st.camera_input("写真を撮る")

if img_file:
    # 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存中...")

    # 2. 確定した住所をAIに渡して「駅名」と「タイトル」を生成
    ai_title = "名称未設定"
    near_station = "駅不明"
    
    with st.spinner(f"住所「{current_addr}」から最寄駅を特定中..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            # 住所を明示的に渡し、その住所に基づいた最寄駅を回答させる
            prompt = f"""
            以下の住所と写真に基づいて回答してください。
            【対象住所】: {current_addr}
            
            指示:
            1. この住所の「最寄り駅名」を1つ特定してください。
            2. 写真の内容に短い日本語タイトル（15文字以内）を付けてください。
            
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

    # 4. 全自動保存JavaScript（タイトル_住所_駅名）
    st.success(f"確定: {ai_title} / {near_station}")
    
    auto_save_script = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (function() {{
        const aiTitle = "{ai_title}";
        const addr = "{current_addr}";
        const station = "{near_station}";
        const imgData = "data:image/jpeg;base64,{img_str}";
        const originalWidth = {width};
        const originalHeight = {height};

        const fileName = aiTitle + "_" + addr + "_" + station + ".pdf";

        const {{ jsPDF }} = window.jspdf;
        const doc = new jsPDF();
        
        const maxWidth = 190;
        const maxHeight = 260;
        let printWidth = maxWidth;
        let printHeight = (originalHeight * maxWidth) / originalWidth;

        if (printHeight > maxHeight) {{
            printHeight = maxHeight;
            printWidth = (originalWidth * maxHeight) / originalHeight;
        }}

        doc.addImage(imgData, 'JPEG', 10, 20, printWidth, printHeight, undefined, 'NONE');
        doc.save(fileName);
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=0)
