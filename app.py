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

# セッション状態で進捗を管理
if "step" not in st.session_state:
    st.session_state.step = "input"
if "title" not in st.session_state:
    st.session_state.title = ""
if "address" not in st.session_state:
    st.session_state.address = ""

# 1. 写真撮影
img_file = st.camera_input("写真を撮る", key="camera", on_change=lambda: st.session_state.update({"step": "analyze_title"}))

if img_file and st.session_state.step == "analyze_title":
    # 2. AIタイトル付与（まず写真だけ見て決める）
    img = Image.open(img_file)
    with st.spinner("AIタイトルを生成中..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(["この写真に15文字以内のタイトルを1つ付けて。結果のみ。", img])
            st.session_state.title = response.text.strip().replace("/", "-")
            st.session_state.step = "get_address"
            st.rerun()
        except:
            st.session_state.title = "名称未設定"
            st.session_state.step = "get_address"
            st.rerun()

if st.session_state.step == "get_address":
    # 3. 住所特定（JavaScriptを実行して住所を取得し、URLパラメータにセットして戻る）
    st.write(f"🏷️ タイトル確定: **{st.session_state.title}**")
    st.write("📍 現在地を確認しています...")
    
    get_addr_js = """
    <script>
    navigator.geolocation.getCurrentPosition(async (pos) => {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
            headers: { 'Accept-Language': 'ja' }
        });
        const data = await res.json();
        const addr = data.address;
        const f = (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
        const url = new URL(window.location.href);
        url.searchParams.set("found_addr", f);
        window.location.href = url.href; // 住所を持って強制リロード
    }, (err) => { alert("位置情報を許可してください"); });
    </script>
    """
    st.components.v1.html(get_addr_js, height=0)
    
    # URLから住所が戻ってきたかチェック
    query_addr = st.query_params.get("found_addr")
    if query_addr:
        st.session_state.address = query_addr
        st.session_state.step = "analyze_station"
        st.rerun()

if st.session_state.step == "analyze_station":
    # 4. 改めてAIで駅名特定
    img = Image.open(img_file)
    st.write(f"🏷️ タイトル: {st.session_state.title}")
    st.write(f"📍 住所: {st.session_state.address}")
    
    with st.spinner("最寄駅を特定中..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"以下の住所から判断して、最も近い「駅名」を1つだけ答えてください。余計な説明は不要です。\n住所：{st.session_state.address}"
            response = model.generate_content(prompt)
            station = response.text.strip().replace("/", "-")
        except:
            station = "不明"

        # 5. PDF生成・保存（すべての情報が揃った）
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=100, subsampling=0)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        width, height = img.size

        st.success(f"保存準備完了: {st.session_state.title} / {station}")
        
        save_js = f"""
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
        <script>
        (function() {{
            const fileName = "{st.session_state.title}_{st.session_state.address}_{station}.pdf";
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
        st.components.v1.html(save_js, height=0)
        
        # 処理が終わったらリセット準備
        if st.button("完了（次の撮影へ）"):
            st.session_state.step = "input"
            st.query_params.clear()
            st.rerun()
