import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import base64

# --- セキュリティ設定 ---
# StreamlitのSecretsまたは環境変数からAPIキーを取得
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。StreamlitのSecretsに登録してください。")
    st.stop()

genai.configure(api_key=api_key)

# --- 基本設定 ---
st.set_page_config(page_title="自動写真保存 v2.5", layout="centered")
st.title("📸 写真内容解析 & 保存")

# カメラ入力 (Duplicate IDエラー防止のためkeyを固定)
img_file = st.camera_input("写真を撮る", key="camera_v25")

if img_file:
    # 1. 画像の読み込みとリサイズ準備
    img = Image.open(img_file)
    width, height = img.size 
    st.image(img, caption="解析・保存プロセスを実行中...")

    # 2. AI解析（Gemini 2.5 Flash-Lite）
    ai_title = "名称未設定"
    with st.spinner("Gemini 2.5 Flash-Lite が解析中..."):
        try:
            # 指定されたモデル名を使用
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
            prompt = "この写真の内容を分析し、10文字以内の日本語タイトルを1つだけ出力してください。余計な説明は不要です。"
            response = model.generate_content([prompt, img])
            
            if response and response.text:
                # ファイル名禁止文字を置換
                ai_title = response.text.strip().replace("\n", "").replace("/", "-").replace(" ", "")
        except Exception as e:
            # クォータ制限(429)やモデル未対応時のハンドリング
            if "429" in str(e):
                st.warning("⚠️ Gemini APIの利用制限に達しました。タイトルなしで進行します。")
            else:
                st.warning(f"⚠️ AI解析をスキップしました: {e}")

    # 3. 画像のBase64変換（最高画質 JPEG）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動JavaScript（住所取得 ＋ 文字埋め込み ＋ JPG保存）
    st.success(f"タイトル確定: {ai_title}")
    
    auto_save_script = f"""
    <div id="status" style="font-size:12px; color:gray; padding:10px; background:#f9f9f9; border-radius:5px;">
        📍 位置情報を取得して、画像に「タイトル_住所」を書き込みます...
    </div>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const aiTitle = "{ai_title}";
        const imgBase64 = "data:image/jpeg;base64,{img_str}";
        const oW = {width};
        const oH = {height};

        // 位置情報の取得（タイムアウト5秒設定）
        navigator.geolocation.getCurrentPosition(
            async (pos) => {{
                let finalAddr = "住所不明";
                try {{
                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{pos.coords.latitude}}&lon=${{pos.coords.longitude}}&accept-language=ja`);
                    const data = await response.json();
                    const a = data.address;
                    // 市区町村〜町名までの住所を組み立て
                    finalAddr = (a.city || a.town || a.village || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                }} catch (e) {{
                    console.error("Address fetch error", e);
                }}
                processAndSave(finalAddr);
            }},
            (err) => {{
                console.warn("Geolocation error", err);
                processAndSave("位置情報なし");
            }},
            {{ enableHighAccuracy: true, timeout: 5000 }}
        );

        // 画像加工と保存の実行
        function processAndSave(addr) {{
            const displayText = aiTitle + " _ " + addr;
            // ファイル名から禁止文字を削除
            const safeAddr = addr.replace(/[/\\\\?%*:|"<>]/g, '-');
            const fileName = aiTitle + "_" + safeAddr + ".jpg";

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = function() {{
                canvas.width = oW;
                canvas.height = oH;
                
                // 1. 元画像を描画
                ctx.drawImage(img, 0, 0, oW, oH);
                
                // 2. 文字サイズを画像高さの1/30に設定
                const fontSize = Math.floor(oH / 30); 
                ctx.font = "bold " + fontSize + "px sans-serif";
                ctx.textBaseline = "top";
                
                const padding = fontSize / 2;
                const textWidth = ctx.measureText(displayText).width;
                
                // 3. テキスト背景ボックス（半透明の黒）
                ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
                ctx.fillRect(20, 20, textWidth + (padding * 2), fontSize + (padding * 2));
                
                // 4. テキスト描画（白）
                ctx.fillStyle = "white";
                ctx.fillText(displayText, 20 + padding, 20 + padding);
                
                // 5. 保存実行
                const link = document.createElement('a');
                link.download = fileName;
                link.href = canvas.toDataURL('image/jpeg', 1.0); // クオリティ最高
                link.click();
                
                status.style.color = "green";
                status.innerText = "✅ 保存完了: " + fileName;
            }};
            img.src = imgBase64;
        }}
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=120)
