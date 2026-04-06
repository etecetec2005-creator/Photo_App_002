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

genai.configure(api_key=api_key)import streamlit as st
import google.generativeai as genai
from PIL import Image
import ioimport streamlit as st
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

# --- 利用可能なモデルを特定する関数 ---
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

# カメラ入力 (keyを固定して重複エラーを防止)
img_file = st.camera_input("写真を撮る", key="fixed_camera_id")

if img_file:
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存プロセスを開始します...")

    # 1. AIタイトル生成 (Python側)
    ai_title = "名称未設定"
    target_model = get_working_model()
    
    with st.spinner(f"AI解析中..."):
        try:
            model = genai.GenerativeModel(target_model)
            response = model.generate_content(["この写真に10文字以内の日本語タイトルを1つ付けて。回答はタイトルのみ。", img])
            ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            st.warning(f"タイトル生成スキップ: {e}")

    # 2. 画像のBase64化 (高画質設定: PIL保存クオリティ反映)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 3. JavaScriptによる住所・駅名取得とPDF保存
    # 全ての波括弧を二重 {{ }} にしてPythonのf-stringエラーを回避
    full_process_script = f"""
    <div id="save-status" style="padding:10px; background:#f0f2f6; border-radius:5px; color:#1f77b4; font-weight:bold;">
        📍 現在地を確認してPDFを作成しています...
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const statusDiv = document.getElementById('save-status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";

        navigator.geolocation.getCurrentPosition(async (pos) => {{
            try {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                // 1. 住所特定 (Nominatim API)
                const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&accept-language=ja`);
                const addrData = await addrRes.json();
                const a = addrData.address;
                const finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                
                // 2. 最寄駅検索 (Overpass API)
                let stationName = "駅不明";
                try {{
                    const query = `[out:json];node(around:1000,${{lat}},${{lon}})[railway=station];out;`;
                    const sRes = await fetch("https://overpass-api.de/api/interpreter?data=" + encodeURIComponent(query));
                    const sData = await sRes.json();
                    if (sData.elements.length > 0) {{
                        stationName = sData.elements[0].tags.name || "駅名なし";
                    }}
                }} catch(e) {{
                    console.log("Station fetch error");
                }}

                // 3. PDF生成
                const {{ jsPDF }} = window.jspdf;
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
                
                // ファイル名：タイトル_住所_駅名
                const safeAddr = (finalAddr || "住所不明").replace(/[/\\\\?%*:|"<>]/g, '-');
                const fileName = aiTitle + "_" + safeAddr + "_" + stationName + ".pdf";
                
                doc.save(fileName);
                statusDiv.style.color = "green";
                statusDiv.innerText = "✅ 保存完了: " + fileName;

            }} catch (err) {{
                statusDiv.style.color = "red";
                statusDiv.innerText = "❌ エラー: 位置情報または保存に失敗しました。";
            }}
        }}, (err) => {{
            statusDiv.style.color = "orange";
            statusDiv.innerText = "📍 位置情報を許可して、再度撮影してください。";
        }}, {{ enableHighAccuracy: true }});
    }})();
    </script>
    """
    st.components.v1.html(full_process_script, height=120)
import os
import base64

# --- セキュリティ設定 ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

# --- 利用可能なモデルを特定する関数 ---
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

# カメラ入力 (keyを固定して重複エラーを防止)
img_file = st.camera_input("写真を撮る", key="fixed_camera_id")

if img_file:
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存プロセスを開始します...")

    # 1. AIタイトル生成 (Python側)
    ai_title = "名称未設定"
    target_model = get_working_model()
    
    with st.spinner(f"AI解析中..."):
        try:
            model = genai.GenerativeModel(target_model)
            response = model.generate_content(["この写真に10文字以内の日本語タイトルを1つ付けて。回答はタイトルのみ。", img])
            ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            st.warning(f"タイトル生成スキップ: {e}")

    # 2. 画像のBase64化 (高画質設定)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 3. JavaScriptによる住所・駅名取得とPDF保存
    # 全ての波括弧を二重 {{ }} にしてPythonのf-stringエラーを回避
    full_process_script = f"""
    <div id="save-status" style="padding:10px; background:#f0f2f6; border-radius:5px; color:#1f77b4; font-weight:bold;">
        📍 現在地を確認してPDFを作成しています...
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const statusDiv = document.getElementById('save-status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";

        navigator.geolocation.getCurrentPosition(async (pos) => {{
            try {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                // 1. 住所特定 (Nominatim API)
                const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&accept-language=ja`);
                const addrData = await addrRes.json();
                const a = addrData.address;
                const finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                
                // 2. 最寄駅検索 (Overpass API)
                let stationName = "駅不明";
                try {{
                    const query = `[out:json];node(around:1000,${{lat}},${{lon}})[railway=station];out;`;
                    const sRes = await fetch("https://overpass-api.de/api/interpreter?data=" + encodeURIComponent(query));
                    const sData = await sRes.json();
                    if (sData.elements.length > 0) {{
                        stationName = sData.elements[0].tags.name || "駅名なし";
                    }}
                }} catch(e) {{
                    console.log("Station fetch error");
                }}

                // 3. PDF生成
                const {{ jsPDF }} = window.jspdf;
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
                
                // ファイル名：タイトル_住所_駅名
                const safeAddr = (finalAddr || "住所不明").replace(/[/\\\\?%*:|"<>]/g, '-');
                const fileName = aiTitle + "_" + safeAddr + "_" + stationName + ".pdf";
                
                doc.save(fileName);
                statusDiv.style.color = "green";
                statusDiv.innerText = "✅ 保存完了: " + fileName;

            }} catch (err) {{
                statusDiv.style.color = "red";
                statusDiv.innerText = "❌ エラー: 位置情報または保存に失敗しました。";
            }}
        }}, (err) => {{
            statusDiv.style.color = "orange";
            statusDiv.innerText = "📍 位置情報を許可して、再度撮影してください。";
        }}, {{ enableHighAccuracy: true }});
    }})();
    </script>
    """
    st.components.v1.html(full_process_script, height=120)

# --- 利用可能なモデルを特定する関数 ---
def get_working_model():
    try:
        # サポートされている最新モデルを探す
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # gemini-1.5-flash を優先的に探す
        flash_models = [m for m in models if "gemini-1.5-flash" in m]
        if flash_models:
            return flash_models[0]
        return models[0] # 見つからなければ最初のモデル
    except Exception:
        return "gemini-1.5-flash" # 最終フォールバック

st.set_page_config(page_title="自動写真保存", layout="centered")
st.title("📸 写真の中身")

# カメラ入力 (keyを固定して重複エラーを防止)
img_file = st.camera_input("写真を撮る", key="fixed_camera_id")

if img_file:
    img = Image.open(img_file)
    width, height = img.size
    st.image(img, caption="解析・保存プロセスを開始します...")

    # 1. AIタイトル生成 (Python側)
    ai_title = "名称未設定"
    target_model = get_working_model()
    
    with st.spinner(f"AI解析中... (使用モデル: {target_model})"):
        try:
            model = genai.GenerativeModel(target_model)
            # モデル名エラー対策として、もっともシンプルなプロンプトに
            response = model.generate_content(["この写真に10文字以内の日本語タイトルを1つ付けて。回答はタイトルのみ。", img])
            ai_title = response.text.strip().replace("\n", "").replace("/", "-")
        except Exception as e:
            st.error(f"AI解析でエラーが発生しました。タイトルをデフォルトにします。: {e}")

    # 2. 画像のBase64化 (高画質設定)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=100, subsampling=0)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 3. JavaScriptによる住所・駅名取得とPDF保存
    # ステップ：住所取得 -> 駅名検索(OSM) -> PDF生成
    full_process_script = f"""
    <div id="save-status" style="padding:10px; background:#f0f2f6; border-radius:5px; color:#1f77b4; font-weight:bold;">
        📍 現在地を確認してPDFを作成しています...
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script>
    (async function() {{
        const statusDiv = document.getElementById('save-status');
        const aiTitle = "{ai_title}";
        const imgData = "data:image/jpeg;base64,{img_str}";

        navigator.geolocation.getCurrentPosition(async (pos) => {{
            try {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                // 1. 住所特定 (Nominatim API)
                const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&accept-language=ja`);
                const addrData = await addrRes.json();
                const a = addrData.address;
                const finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.city_district || "") + (a.neighbourhood || "");
                
                // 2. 最寄駅検索 (Overpass API - 1km圏内の駅)
                let stationName = "駅不明";
                try {{
                    const query = `[out:json];node(around:1000,${{lat}},${{lon}})[railway=station];out;`;
                    const sRes = await fetch("https://overpass-api.de/api/interpreter?data=" + encodeURIComponent(query));
                    const sData = await sRes.json();
                    if (sData.elements.length > 0) {{
                        stationName = sData.elements[0].tags.name || "駅名なし";
                    }}
                } catch(e) {{}}

                // 3. PDF生成
                const {{ jsPDF }} = window.jspdf;
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
                
                // ファイル名：タイトル_住所_駅名
                const safeAddr = (finalAddr || "住所不明").replace(/[/\\?%*:|"<>]/g, '-');
                const fileName = aiTitle + "_" + safeAddr + "_" + stationName + ".pdf";
                
                doc.save(fileName);
                statusDiv.style.color = "green";
                statusDiv.innerText = "✅ 保存完了: " + fileName;

            }} catch (err) {{
                statusDiv.style.color = "red";
                statusDiv.innerText = "❌ エラー: 位置情報または保存に失敗しました。";
            }}
        }}, (err) => {{
            statusDiv.style.color = "orange";
            statusDiv.innerText = "📍 位置情報を許可して、再度撮影してください。";
        }}, {{ enableHighAccuracy: true }});
    }})();
    </script>
    """
    st.components.v1.html(full_process_script, height=120)
