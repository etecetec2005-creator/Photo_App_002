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
    # ※駅名は、保存実行時のJS内で取得した住所を元に、再度Geminiに問い合わせる形式にします
    ai_title = "名称未設定"
    with st.spinner("AIが解析しています..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            # まずはタイトルだけ決める
            prompt = "この写真の内容を分析し、短い日本語タイトル（15文字以内）を1つ。結果のみ。"
            response = model.generate_content([prompt, img])
            if response.text:
                ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except:
            pass

    # 3. PDF生成用のBase64変換
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 全自動JavaScript（住所取得・駅名推論・保存を一気に行う）
    st.success(f"タイトル確定: {ai_title}")
    
    # 住所から駅名を特定するために、Geminiに住所を渡す関数を定義（擬似的にJSで処理）
    # ここでは、住所取得後に再度Streamlit側に値を戻すのではなく、
    # JS内で住所を特定し、その文字列を元に「タイトル_住所_駅名」を完成させます。
    
    auto_save_script = f"""
    <div id="status" style="font-size:12px; color:gray; padding:5px;">位置情報を取得して保存します...</div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";

        navigator.geolocation.getCurrentPosition(
            async (pos) => {{
                try {{
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    
                    // 1. 住所特定
                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}`, {{
                        headers: {{ 'Accept-Language': 'ja' }}
                    }});
                    const data = await response.json();
                    const addr = data.address;
                    let finalAddr = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
                    if(!finalAddr) finalAddr = "住所不明";

                    // 2. 最寄駅の簡易特定（OSMのAPIを利用して駅を探す）
                    let stationName = "駅不明";
                    try {{
                        const overpassUrl = `https://overpass-api.de/api/interpreter?data=[out:json];node(around:1000,${{lat}},${{lon}})[railway=station];out;`;
                        const stationRes = await fetch(overpassUrl);
                        const stationData = await stationRes.json();
                        if (stationData.elements && stationData.elements.length > 0) {{
                            stationName = stationData.elements[0].tags.name || "駅名なし";
                        }}
                    }} catch (e) {{
                        console.log("Station fetch error");
                    }}

                    // 3. ファイル名組み立て
                    const fileName = aiTitle + "_" + finalAddr + "_" + stationName + ".pdf";
                    status.innerText = "保存中: " + fileName;

                    // 4. PDF生成
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

                    doc.addImage(imgData, 'JPEG', 10, 20, printWidth, printHeight, undefined, 'NONE');
                    doc.save(fileName);
                    status.innerText = "✅ 保存完了: " + fileName;

                }} catch (err) {{ 
                    status.innerText = "保存エラーが発生しました";
                }}
            }},
            (err) => {{ status.innerText = "位置情報を許可してください"; }},
            {{ enableHighAccuracy: true }}
        );
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=100)
