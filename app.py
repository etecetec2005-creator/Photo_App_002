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

img_file = st.camera_input("写真を撮る")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size # 画像の元サイズを取得
    st.image(img, caption="解析・保存中...")

    # 2. AI解析（タイトル生成）
    ai_title = "名称未設定"
    with st.spinner("AIが解析しています..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            prompt = "この写真の内容を分析し、短い日本語タイトル（15文字以内）を1つ。結果のみ。"
            response = model.generate_content([prompt, img])
            if response.text:
                # ファイル名に使えない文字を置換
                ai_title = response.text.strip().replace("\n", "").replace("\r", "").replace('"', '').replace("'", "").replace("/", "-")
        except:
            pass

    # 3. 画像のBase64変換（最高画質設定）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動JavaScript（画像加工・JPG保存）
    st.success(f"タイトル確定: {ai_title}")
    
    auto_save_script = f"""
    <div id="status" style="font-size:12px; color:gray; padding:5px;">位置情報を取得して画像に文字を埋め込み保存します...</div>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const aiTitle = "{ai_title}";
        const imgBase64 = "data:image/jpeg;base64,{img_str}";
        const originalWidth = {width};
        const originalHeight = {height};

        navigator.geolocation.getCurrentPosition(
            async (pos) => {{
                try {{
                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{pos.coords.latitude}}&lon=${{pos.coords.longitude}}`, {{
                        headers: {{ 'Accept-Language': 'ja' }}
                    }});
                    const data = await response.json();
                    const addr = data.address;
                    let finalAddr = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
                    if(!finalAddr) finalAddr = "住所不明";
                    
                    const displayText = aiTitle + " _ " + finalAddr;
                    const fileName = aiTitle + "_" + finalAddr + ".jpg";

                    // Canvasを使用して画像を加工
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    const img = new Image();
                    
                    img.onload = function() {{
                        canvas.width = originalWidth;
                        canvas.height = originalHeight;
                        
                        // 元画像を描画
                        ctx.drawImage(img, 0, 0, originalWidth, originalHeight);
                        
                        // 文字のスタイル設定（画像サイズに合わせて調整）
                        const fontSize = Math.floor(originalHeight / 25); 
                        ctx.font = "bold " + fontSize + "px sans-serif";
                        ctx.textBaseline = "top";
                        
                        // テキストの背景（可読性向上のため）
                        const textMetrics = ctx.measureText(displayText);
                        const padding = fontSize / 2;
                        ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
                        ctx.fillRect(10, 10, textMetrics.width + (padding * 2), fontSize + (padding * 2));
                        
                        // テキストを描画
                        ctx.fillStyle = "white";
                        ctx.fillText(displayText, 10 + padding, 10 + padding);
                        
                        // 加工後の画像をダウンロード
                        const link = document.createElement('a');
                        link.download = fileName;
                        link.href = canvas.toDataURL('image/jpeg', 1.0); // 最高画質
                        link.click();
                        
                        status.innerText = "✅ 画像内に文字を埋め込み保存しました: " + fileName;
                    }};
                    img.src = imgBase64;

                }} catch (err) {{ 
                    status.innerText = "エラーのため加工なしで保存します";
                    const link = document.createElement('a');
                    link.download = aiTitle + ".jpg";
                    link.href = imgBase64;
                    link.click();
                }}
            }},
            (err) => {{ status.innerText = "位置情報を許可してください"; }},
            {{ enableHighAccuracy: true }}
        );
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=100)
