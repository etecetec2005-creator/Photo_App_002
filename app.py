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

# セッション状態で住所を管理
if "address" not in st.session_state:
    st.session_state.address = None

# --- 1. 住所取得セクション ---
# 撮影前・撮影中に常にバックグラウンドで住所を取得し続ける
st.components.v1.html("""
<script>
    const getLocation = () => {
        navigator.geolocation.getCurrentPosition(async (pos) => {
            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
                    headers: { 'Accept-Language': 'ja' }
                });
                const data = await res.json();
                const addr = data.address;
                const finalAddr = (addr.province || "") + (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
                
                // Streamlitに住所を送信
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: finalAddr
                }, '*');
            } catch (e) {}
        }, (err) => {}, { enableHighAccuracy: true });
    };
    getLocation();
    setInterval(getLocation, 5000); // 5秒ごとに更新
</script>
""", height=0)

# --- 2. カメラ入力 ---
# keyを指定することでDuplicateElementIdエラーを回避
img_file = st.camera_input("写真を撮る", key="main_camera")

if img_file:
    # 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析中...")

    # --- 3. プロセス開始 ---
    ai_title = "名称未設定"
    near_station = "特定中..."
    
    # 住所が届くのを待つ（または前回の取得分を使用）
    # JSコンポーネントからの値を擬似的に取得するために、一時的に空でも進めるよう配慮
    current_addr = st.session_state.get("address", "住所特定中...")

    with st.spinner("AI解析中 (タイトル・住所・駅名を照合中)..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # ステップ：画像からタイトル ＋ 住所から駅名
            prompt = f"""
            指示:
            1. 以下の写真の内容から、15文字以内の日本語タイトルを付けてください。
            2. 提供された【住所】から判断して、最も近い「駅名」を1つ特定してください。
            
            【住所】: {current_addr}
            
            回答形式:
            タイトル: [タイトル]
            駅名: [駅名]
            """
            response = model.generate_content([prompt, img])
            
            if response.text:
                for line in response.text.split("\n"):
                    if "タイトル:" in line: ai_title = line.split(":")[1].strip().replace("/", "-")
                    if "駅名:" in line: near_station = line.split(":")[1].strip().replace("/", "-")
        except Exception as e:
            st.error(f"AI解析エラー: {e}")

    # --- 4. PDF生成と自動保存 ---
    if ai_title != "名称未設定":
        # 最高画質でBase64変換
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=100, subsampling=0)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        st.success(f"確定: {ai_title} / {current_addr} / {near_station}")
        
        save_script = f"""
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
        st.components.v1.html(save_script, height=0)

# JSからの住所入力をセッションに反映させるためのフック
# (Streamlitの再描画に合わせて最新の住所を保持する)
if "address" not in st.session_state or st.session_state.address == "住所特定中...":
    # コンポーネントの戻り値を監視（Streamlit Cloud環境での安定性のための記述）
    pass
