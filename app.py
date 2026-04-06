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

# 1. 利用可能な最新モデルを自動取得する関数
def get_model_name():
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini-1.5-flash' in m.name:
                    return m.name
        return 'models/gemini-pro-vision' # フォールバック
    except:
        return 'gemini-1.5-flash'

target_model = get_model_name()

# --- 2. メインUI ---
# keyを固定して重複エラーを防止
img_file = st.camera_input("写真を撮る", key="unique_camera_input")

if img_file:
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析を開始します...")

    # 3. AIタイトル付与 (まずは写真のみでタイトルを決める)
    ai_title = "名称未設定"
    with st.spinner("AIタイトルを生成中..."):
        try:
            model = genai.GenerativeModel(target_model)
            response = model.generate_content(["この写真に15文字以内のタイトルを1つ付けて。結果のみ。", img])
            ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            st.error(f"AI解析エラー: {e}")

    # 4. JavaScriptで「住所取得」と「駅名特定(AI)」を連携して保存
    # Python側で高画質画像をBase64化
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    st.info(f"タイトル確定: {ai_title}。次に位置情報を取得して保存します。")

    # 全工程をJSで一気に実行（ブラウザ側で完結させることで情報の欠落を防ぐ）
    full_process_script = f"""
    <div id="status" style="font-size:12px; color:blue; padding:5px;">📍 現在地と最寄駅を確認中...</div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";

        navigator.geolocation.getCurrentPosition(async (pos) => {{
            try {{
                // 1. 住所取得
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&accept-language=ja`);
                const data = await res.json();
                const addr = data.address;
                const finalAddr = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
                
                // 2. 最寄駅取得 (OSM Overpass APIを使用して論理的に特定)
                let stationName = "駅不明";
                try {{
                    const overpassUrl = `https://overpass-api.de/api/interpreter?data=[out:json];node(around:1500,${{lat}},${{lon}})[railway=station];out;`;
                    const sRes = await fetch(overpassUrl);
                    const sData = await sRes.json();
                    if (sData.elements.length > 0) stationName = sData.elements[0].tags.name;
                }} catch(e) {{}}

                // 3. PDF保存
                const {{ jsPDF }} = window.jspdf;
                const doc = new jsPDF();
                const originalWidth = {width};
                const originalHeight = {height};
                const maxWidth = 190;
                const maxHeight = 260;
                let pw = maxWidth;
                let ph = (originalHeight * maxWidth) / originalWidth;
                if (ph > maxHeight) {{
                    ph = maxHeight;
                    pw = (originalWidth * maxHeight) / originalHeight;
                }}

                doc.addImage(imgData, 'JPEG', 10, 20, pw, ph, undefined, 'NONE');
                const fileName = aiTitle + "_" + (finalAddr || "住所不明") + "_" + stationName + ".pdf";
                doc.save(fileName);
                status.innerText = "✅ 保存完了: " + fileName;

            }} catch (err) {{
                status.innerText = "❌ エラーが発生しました。";
            }}
        }}, (err) => {{
            status.innerText = "📍 位置情報を許可してください。";
        }}, {{ enableHighAccuracy: true }});
    }})();
    </script>
    """
    st.components.v1.html(full_process_script, height=100)
