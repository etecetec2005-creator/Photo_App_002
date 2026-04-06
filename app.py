import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import base64
import json

# --- セキュリティ設定 ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

st.set_page_config(page_title="自動写真保存", layout="centered")
st.title("📸 写真の中身")

# --- 1. 住所取得用のコンポーネント ---
# 撮影前、または撮影直後にブラウザ側で住所を特定するための仕組み
def get_address_via_js():
    # JavaScriptからStreamlitにデータを戻すためのカスタムコンポーネント的な記述
    components_code = """
    <script>
    async function getLocation() {
        navigator.geolocation.getCurrentPosition(async (pos) => {
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
                headers: { 'Accept-Language': 'ja' }
            });
            const data = await res.json();
            const addr = data.address;
            const finalAddr = (addr.province || "") + (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
            
            // Streamlit側にデータを送信
            const result = {
                address: finalAddr || "住所不明",
                lat: pos.coords.latitude,
                lon: pos.coords.longitude
            };
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                value: result
            }, '*');
        }, (err) => {
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                value: {address: "位置情報拒否", error: true}
            }, '*');
        }, { enableHighAccuracy: true });
    }
    getLocation();
    </script>
    """
    # 戻り値を監視
    return st.components.v1.html(components_code, height=0)

# 住所取得コンポーネントを配置し、値を取得
address_data = st.query_params.get("addr_info") # 補助的な取得用（もしあれば）

# --- メイン UI ---
img_file = st.camera_input("写真を撮る")

# 住所を一時保存する隠しフック
# st.camera_inputの下に配置することで、撮影後に確実に住所を取りに行く
address_receiver = st.components.v1.html("""
<script>
    window.addEventListener('message', function(event) {
        if (event.data.type === 'streamlit:setComponentValue') {
            const val = event.data.value;
            if (val && val.address) {
                const url = new URL(window.location.href);
                url.searchParams.set("addr", val.address);
                window.history.replaceState({}, "", url);
            }
        }
    });
    navigator.geolocation.getCurrentPosition(async (pos) => {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {headers: {'Accept-Language': 'ja'}});
        const data = await res.json();
        const addr = data.address;
        const f = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: f}, '*');
    });
</script>
""", height=0)

# URLパラメータから住所を読み取る（Streamlitの再読み込み特性を利用）
current_addr = st.query_params.get("addr", "住所取得中...")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption=f"場所: {current_addr}")

    # 2. AI解析（住所を元にタイトルと駅名を決定）
    ai_title = "名称未設定"
    near_station = "駅不明"

    with st.spinner("AIが最寄駅とタイトルを特定中..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            # 確定した住所をプロンプトに埋め込む
            prompt = f"""
            指示:
            1. 提供された【住所情報】に基づいて、その場所から最も近い「駅名」を特定してください。
            2. 写真の内容を分析し、15文字以内の短い「タイトル」を付けてください。
            
            【住所情報】: {current_addr}
            
            回答は必ず以下の形式のみで出力してください。余計な説明は不要です。
            タイトル: [タイトル内容]
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
        except Exception as e:
            st.error(f"AI解析エラー: {e}")

    # 3. PDF生成用Base64（最高画質）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動保存
    st.success(f"確定: {ai_title} / 最寄駅: {near_station}")
    
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
