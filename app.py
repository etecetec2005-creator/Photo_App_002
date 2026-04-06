import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import base64
import requests
import time

# --- セキュリティ設定 ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=api_key)
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

# 1. 最初にブラウザで住所を取得（この値がPython側に渡るまで待つ仕組み）
# Streamlitのコンポーネントを使用して、JSから値を直接受け取る
def get_geo_info():
    js_code = """
    <script>
    navigator.geolocation.getCurrentPosition(async (pos) => {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, {
            headers: { 'Accept-Language': 'ja' }
        });
        const data = await res.json();
        const addr = data.address;
        // 詳細な住所を組み立て
        const finalAddr = (addr.province || "") + (addr.city || "") + (addr.suburb || "") + (addr.city_district || "") + (addr.neighbourhood || "");
        
        // Streamlit側に値を送信
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: finalAddr
        }, '*');
    }, (err) => {
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: "住所取得失敗"}, '*');
    }, { enableHighAccuracy: true });
    </script>
    """
    return st.components.v1.html(js_code, height=0)

# 住所コンポーネントを設置（撮影前でも後でも常に動くように）
addr_component = get_geo_info()

img_file = st.camera_input("写真を撮る")

if img_file:
    # 2. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存中...")

    # 3. AI解析（住所の文字列から駅名とタイトルを特定）
    # 住所がまだ取得できていない場合は、少し待つかデフォルト値を使用
    current_address = st.query_params.get("found_addr", "大阪府大阪市") # デフォルトを少し具体的に

    ai_title = "名称未設定"
    near_station = "駅不明"

    with st.spinner("住所から最寄駅を特定中..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            # 住所に基づいた特定を徹底させるプロンプト
            prompt = f"""
            指示:
            1. 以下の【住所】に最も近い「駅名」を1つ特定してください（例: 新大阪駅）。
            2. 写真の内容に短い日本語タイトル（15文字以内）を付けてください。
            
            【住所】: {current_address}
            
            回答は以下の形式のみで出力してください。
            タイトル: [タイトル]
            駅名: [駅名]
            """
            response = model.generate_content([prompt, img])
            if response.text:
                for line in response.text.split("\n"):
                    if "タイトル:" in line: ai_title = line.split(":")[1].strip().replace("/", "-")
                    if "駅名:" in line: near_station = line.split(":")[1].strip().replace("/", "-")
        except:
            pass

    # 4. PDF生成用のBase64変換（最高画質）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 5. 全自動JavaScript保存（ファイル名：タイトル_住所_駅名）
    st.success(f"確定: {ai_title} / {current_address} / {near_station}")
    
    save_pdf_script = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (function() {{
        const aiTitle = "{ai_title}";
        const address = "{current_address}";
        const station = "{near_station}";
        const fileName = aiTitle + "_" + address + "_" + station + ".pdf";

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
st.set_page_config(page_title="自動写真保存", layout="centered")
st.title("📸 写真の中身")

img_file = st.camera_input("写真を撮る")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存中...")

    # 2. 【改善】Python側でネットワーク経由で住所を特定（JSのラグを回避）
    address_str = "住所不明"
    near_station = "駅不明"
    
    with st.spinner("現在地と駅を特定中..."):
        try:
            # IPアドレスベースで住所をざっくり特定（iPhoneのブラウザでもPython側で動く）
            geo_res = requests.get("https://ipapi.co/json/", timeout=5).json()
            if "city" in geo_res:
                # 逆ジオコーディング（Nominatim）でより詳細な住所へ
                lat, lon = geo_res.get("latitude"), geo_res.get("longitude")
                headers = {"User-Agent": "MyPhotoApp/1.0"}
                addr_res = requests.get(f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&accept-language=ja", headers=headers, timeout=5).json()
                address_str = addr_res.get("display_name", "").split(",")[0] # 短い住所
                if not address_str:
                    address_str = f"{geo_res.get('region', '')}{geo_res.get('city', '')}"
        except:
            address_str = "大阪市付近" # 失敗時のバックアップ

    # 3. AI解析（タイトルと駅名を特定）
    ai_title = "名称未設定"
    with st.spinner("AIがタイトルと駅名を考えています..."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            # 住所を渡して、最寄駅とタイトルを同時に出させる
            prompt = f"""
            指示:
            1. 住所「{address_str}」の最寄り駅名を1つ特定してください。
            2. 写真のタイトルを15文字以内で付けてください。
            
            回答形式:
            タイトル: [タイトル]
            駅名: [駅名]
            """
            response = model.generate_content([prompt, img])
            if response.text:
                for line in response.text.split("\n"):
                    if "タイトル:" in line: ai_title = line.split(":")[1].strip().replace("/", "-")
                    if "駅名:" in line: near_station = line.split(":")[1].strip().replace("/", "-")
        except:
            pass

    # 4. PDF生成用のBase64変換（最高画質）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 5. 全自動保存JavaScript
    st.success(f"確定: {ai_title} / {address_str} / {near_station}")
    
    save_pdf_script = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (function() {{
        const fileName = "{ai_title}_{address_str}_{near_station}.pdf";
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
