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
    width, height = img.size 
    st.image(img, caption="解析・保存中...")

    # 2. AI解析（タイトル生成）
    ai_title = "名称未設定"
    with st.spinner("AIが解析しています..."):
        try:
            # モデル取得ロジックの安定化
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # flash 1.5 を優先、なければ最初に見つかったものを使用
            target_model = next((m for m in models if 'gemini-1.5-flash' in m), models[0])
            
            model = genai.GenerativeModel(target_model)
            prompt = "この写真の内容を分析し、短い日本語タイトル（15文字以内）を1つだけ出力してください。解説は不要です。"
            response = model.generate_content([prompt, img])
            
            if response and response.text:
                ai_title = response.text.strip().replace("\n", "").replace("\r", "").replace('"', '').replace("'", "").replace("/", "-")
        except Exception as e:
            # エラー内容を画面に表示（デバッグ用：運用時は削除可）
            st.warning(f"AI解析に失敗しました（タイトルなしで進行します）: {e}")

    # 3. 画像のBase64変換（最高画質）
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

                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    const img = new Image();
                    
                    img.onload = function() {{
                        canvas.width = originalWidth;
                        canvas.height = originalHeight;
                        ctx.drawImage(img, 0, 0, originalWidth, originalHeight);
                        
                        // 文字サイズとスタイル（画面比率に応じる）
                        const fontSize = Math.floor(originalHeight / 30); 
                        ctx.font = "bold " + fontSize + "px sans-serif";
                        ctx.textBaseline = "top";
                        
                        const padding = fontSize / 2;
                        const textMetrics = ctx.measureText(displayText);
                        
                        // 背景ボックス
                        ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
                        ctx.fillRect(20, 20, textMetrics.width + (padding * 2), fontSize + (padding * 2));
                        
                        // テキスト
                        ctx.fillStyle = "white";
                        ctx.fillText(displayText, 20 + padding, 20 + padding);
                        
                        // 保存処理
                        const link = document.createElement('a');
                        link.download = fileName;
                        link.href = canvas.toDataURL('image/jpeg', 1.0);
                        link.click();
                        
                        status.innerText = "✅ 保存完了: " + fileName;
                    }};
                    img.src = imgBase64;

                }} catch (err) {{ 
                    status.innerText = "位置情報取得エラーのためタイトルのみで保存します";
                    const link = document.createElement('a');
                    link.download = aiTitle + ".jpg";
                    link.href = imgBase64;
                    link.click();
                }}
            }},
            (err) => {{ 
                status.innerText = "位置情報が許可されなかったためタイトルのみで保存します";
                const link = document.createElement('a');
                link.download = aiTitle + ".jpg";
                link.href = imgBase64;
                link.click();
            }},
            {{ enableHighAccuracy: true, timeout: 5000 }}
        );
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=100)
