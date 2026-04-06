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

def get_working_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_models = [m for m in models if "gemini-1.5-flash" in m]
        if flash_models:
            return flash_models[0]
        return models[0]
    except Exception:
        return "gemini-1.5-flash"

st.set_page_config(page_title="自動写真保存", layout="centered")
st.title("📸 写真の中身")

img_file = st.camera_input("写真を撮る", key="fixed_camera_id")

if img_file:
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存プロセスを開始します...")

    ai_title = "名称未設定"
    target_model = get_working_model()
    
    with st.spinner("AI解析中..."):
        try:
            model = genai.GenerativeModel(target_model)
            response = model.generate_content(["この写真に10文字以内の日本語タイトルを1つ付けて。回答はタイトルのみ。", img])
            ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            st.warning(f"タイトル生成スキップ: {e}")

    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # JavaScriptの修正：エラーハンドリングを強化
    full_process_script = f"""
    <div id="save-status" style="padding:10px; background:#f0f2f6; border-radius:5px; color:#1f77b4; font-weight:bold;">
        📍 位置情報を確認中... (許可ダイアログが出たら承認してください)
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const statusDiv = document.getElementById('save-status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";
        const {{ jsPDF }} = window.jspdf;

        const savePDF = (addr = "住所不明", station = "駅不明") => {{
            const doc = new jsPDF();
            const oW = {width};
            const oH = {height};
            const maxW = 190;
            const maxH = 260;
            let pW = maxW;
            let pH = (oH * maxW) / oW;
            if (pH > maxH) {{
                pH = maxH;
                pW = (oW * maxH) / oH;
            }}
            doc.addImage(imgData, 'JPEG', 10, 20, pW, pH, undefined, 'NONE');
            const fileName = aiTitle + "_" + addr.replace(/[/\\\\?%*:|"<>]/g, '-') + "_" + station + ".pdf";
            doc.save(fileName);
            statusDiv.style.color = "green";
            statusDiv.innerText = "✅ 保存完了: " + fileName;
        }};

        navigator.geolocation.getCurrentPosition(async (pos) => {{
            try {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                // 住所特定
                const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&accept-language=ja`);
                const addrData = await addrRes.json();
                const a = addrData.address;
                const finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                
                // 駅検索
                let stationName = "駅不明";
                try {{
                    const query = `[out:json];node(around:1000,${{lat}},${{lon}})[railway=station];out;`;
                    const sRes = await fetch("https://overpass-api.de/api/interpreter?data=" + encodeURIComponent(query));
                    const sData = await sRes.json();
                    if (sData.elements.length > 0) stationName = sData.elements[0].tags.name || "駅名なし";
                }} catch(e) {{}}

                savePDF(finalAddr || "住所不明", stationName);
            }} catch (err) {{
                savePDF("住所取得エラー", "駅不明");
            }}
        }}, (err) => {{
            // 位置情報が拒否された場合でも保存だけは実行する
            savePDF("位置情報なし", "不明");
            statusDiv.style.color = "orange";
            statusDiv.innerText = "⚠️ 位置情報なしで保存しました（ブラウザ設定で許可すると住所が入ります）";
        }}, {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }});
    }})();
    </script>
    """
    st.components.v1.html(full_process_script, height=120)
