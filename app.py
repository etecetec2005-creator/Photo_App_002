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

img_file = st.camera_input("写真を撮る", key="my_camera")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size 
    st.image(img, caption="処理を開始します...")

    # 2. AI解析（タイトル生成）
    ai_title = "名称未設定"
    with st.spinner("AI解析中..."):
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in models if 'gemini-1.5-flash' in m), models[0])
            
            model = genai.GenerativeModel(target_model)
            prompt = "この写真の10文字以内の日本語タイトルを1つだけ。回答はタイトルのみ。"
            response = model.generate_content([prompt, img])
            
            if response and response.text:
                ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            # 制限(429)などの場合は警告を出しつつ、タイトルなしで進む
            if "429" in str(e):
                st.warning("⚠️ AIの利用制限に達しました。タイトルなしで保存します。")
            else:
                st.warning(f"AI解析スキップ: {e}")

    # 3. 画像のBase64変換
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動JavaScript（画像加工・JPG保存）
    # AIが失敗していても、JS側で「住所」を補完して保存を実行させます
    auto_save_script = f"""
    <div id="status" style="font-size:12px; color:gray; padding:5px;">位置情報を取得して保存します...</div>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const aiTitle = "{ai_title}";
        const imgBase64 = "data:image/jpeg;base64,{img_str}";
        const oW = {width};
        const oH = {height};

        navigator.geolocation.getCurrentPosition(
            async (pos) => {{
                let finalAddr = "住所不明";
                try {{
                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{pos.coords.latitude}}&lon=${{pos.coords.longitude}}&accept-language=ja`);
                    const data = await response.json();
                    const a = data.address;
                    finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                }} catch (e) {{}}
                
                executeSave(finalAddr);
            }},
            (err) => {{ executeSave("位置情報なし"); }},
            {{ enableHighAccuracy: true, timeout: 5000 }}
        );

        function executeSave(addr) {{
            const displayText = aiTitle + " _ " + addr;
            const fileName = aiTitle + "_" + addr.replace(/[/\\\\?%*:|"<>]/g, '-') + ".jpg";

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = function() {{
                canvas.width = oW;
                canvas.height = oH;
                ctx.drawImage(img, 0, 0, oW, oH);
                
                const fontSize = Math.floor(oH / 30); 
                ctx.font = "bold " + fontSize + "px sans-serif";
                const padding = fontSize / 2;
                const textWidth = ctx.measureText(displayText).width;
                
                ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
                ctx.fillRect(20, 20, textWidth + (padding * 2), fontSize + (padding * 2));
                
                ctx.fillStyle = "white";
                ctx.textBaseline = "top";
                ctx.fillText(displayText, 20 + padding, 20 + padding);
                
                const link = document.createElement('a');
                link.download = fileName;
                link.href = canvas.toDataURL('image/jpeg', 1.0);
                link.click();
                status.innerText = "✅ 保存完了: " + fileName;
            }};
            img.src = imgBase64;
        }}
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=100)
