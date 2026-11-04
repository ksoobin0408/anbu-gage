"""
안부가게 — 상인용 동네 돌봄 거점 앱 (프로토타입)
2026 서울시립대 통계학과 데이터분석경진대회

실행:  streamlit run app.py
데이터: 같은 폴더에 step3_비공식돌봄지수.csv 를 두거나, 사이드바에서 업로드.
        없으면 '예시 데이터'로 화면만 보여줌.
"""

import base64
import json
import os
import re
from uuid import uuid4
from html import escape
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v2 as components

st.set_page_config(page_title="안부가게", page_icon="🏪", layout="wide", initial_sidebar_state="collapsed")


# One font family for native widgets, custom components and all entry screens.
st.markdown("""<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css");
:root {--anbu-font:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.stApp,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6,
.stApp p,.stApp button,.stApp input,.stApp textarea,.stApp select,.stApp label,.stApp summary,
[role="dialog"],[role="dialog"] h2,[role="dialog"] h3,[role="dialog"] p,
[data-baseweb="select"],[role="listbox"],[role="option"] {
  font-family:var(--anbu-font)!important;
}
/* Streamlit heading permalinks are decorative and take up space on small screens. */
[data-testid="stHeaderActionElements"],a[aria-label="Link to heading"] {display:none!important;}
</style>""", unsafe_allow_html=True)

# Review this responsive app using the browser's mobile viewport, without a second CSS phone frame.


PAGES = ["동 찾기", "우리 동네 한눈에", "더 알아보기", "도움 안내"]


def begin_app():
    if st.session_state.get("shop_profile"):
        apply_shop(st.session_state["shop_profile"])
        return
    st.session_state["app_started"] = True
    st.session_state["entry_pending"] = True
    st.session_state["active_page"] = PAGES[0]
    st.session_state["scroll_revision"] = 0
    for key in ("quick_dong", "gu_sel", "dong_sel"):
        st.session_state[key] = None
    for key in ("sel", "loc_msg", "loc_candidate"):
        st.session_state.pop(key, None)


def show_intro():
    st.session_state["intro_index"] = False
    st.session_state["app_started"] = False
    # A fresh button instance prevents an earlier click from starting the app again.
    st.session_state["intro_revision"] = st.session_state.get("intro_revision", 0) + 1


@st.cache_resource
def intro_button():
    return components.component(
        "anbu_intro_start",
        html='''<button type="button" class="intro-start">
          <span class="intro-start-label">안부가게 시작하기</span>
          <span class="intro-start-arrow" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" focusable="false">
              <path d="M6 16h20M18 7l9 9-9 9" stroke="currentColor" stroke-width="2.8"
                stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
        </button>''',
        css="""
        .intro-start { box-sizing:border-box; display:flex; align-items:center; justify-content:space-between; gap:16px;
          width:100%; min-height:74px; padding:12px 13px 12px 24px; border:1px solid #FFF; border-radius:23px;
          background:#FFF; color:#0878CF; cursor:pointer; font:700 18px/1.5 "Pretendard Variable",Pretendard,system-ui,sans-serif;
          box-shadow:0 10px 24px #005AA525; transition:background .2s, transform .2s; }
        .intro-start:hover:not(:disabled) { background:#F0F9FF; transform:translateY(-2px); }
        .intro-start:focus-visible { outline:3px solid #FFF; outline-offset:5px; }
        .intro-start:disabled { cursor:wait; opacity:.8; }
        .intro-start-label { flex:1; min-width:0; text-align:center; word-break:keep-all; letter-spacing:-.025em; }
        .intro-start-arrow { display:flex; align-items:center; justify-content:center; flex:0 0 48px;
          box-sizing:border-box;width:48px; height:48px; border:1px solid #CFE8FA;border-radius:50%; background:#FFF; color:#0878CF; }
        .intro-start-arrow svg { display:block; transition:transform .2s; }
        .intro-start:hover:not(:disabled) .intro-start-arrow svg { transform:translateX(2px); }
        @media(prefers-reduced-motion:reduce) { .intro-start,.intro-start-arrow svg { transition:none; } }
        """,
        js="""
        export default function({parentElement, setStateValue}) {
          const button=parentElement.querySelector('button');
          let timer, active=true;
          const frame=requestAnimationFrame(()=>{
            document.querySelector('[data-testid="stMain"]')?.scrollTo({top:0,left:0,behavior:'instant'});
          });
          button.onclick=()=>{
            button.disabled=true;
            document.querySelector('.intro-copy')?.classList.add('intro-leaving');
            const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            timer=setTimeout(()=>{if(active) setStateValue('started',true);},reduced?0:360);
          };
          return ()=>{active=false;clearTimeout(timer);cancelAnimationFrame(frame);button.onclick=null;
            document.querySelector('.intro-copy')?.classList.remove('intro-leaving');};
        }
        """,
    )


@st.cache_resource
def location_button():
    """전체 버튼을 눌러 위치를 요청. 클릭 전에는 위치를 읽지 않는다."""
    return components.component(
        "anbu_location_button",
        html='''
        <button type="button" class="loc-button">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" width="26" height="26">
            <circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="1.8"/>
            <circle cx="12" cy="12" r="2.5" fill="currentColor"/>
            <path d="M12 2v3m0 14v3M2 12h3m14 0h3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <span class="loc-label">내 위치로 우리 동 찾기</span>
          <span aria-hidden="true" class="loc-arrow">→</span>
        </button>
        <p class="loc-status" role="status" aria-live="polite"></p>
        ''',
        css='''
        .loc-button { box-sizing: border-box; width: 100%; min-height: 62px;
          display: flex; align-items: center; justify-content: center; gap: 10px;
          padding: 16px 20px; border: 0; border-radius: 16px; background: #0878CF;
          color: white; cursor: pointer; font: 700 18px/1.4 "Pretendard Variable", Pretendard, system-ui, sans-serif;
          box-shadow: 0 6px 12px #243C5818; word-break: keep-all; }
        .loc-button:hover { background: #086BB7; }
        .loc-button:focus-visible { outline: 3px solid #8CA5C9; outline-offset: 3px; }
        .loc-button:disabled { cursor: wait; opacity: .75; }
        .loc-button svg { flex-shrink: 0; }
        .loc-arrow { margin-left: auto; font-size: 24px; }
        .loc-label { flex: 1; text-align: left; }
        .loc-status { color: #4C6370; font: 14px/1.5 "Pretendard Variable", Pretendard, system-ui, sans-serif;
          margin: 8px 0 0; word-break: keep-all; }
        .loc-status:empty { display: none; }
        @media(max-width: 360px) { .loc-button { font-size: 16px; padding: 15px 12px; gap: 8px; } }
        ''',
        js='''
        export default function(component) {
          const { parentElement, setStateValue } = component;
          const button = parentElement.querySelector('button');
          const label = parentElement.querySelector('.loc-label');
          const status = parentElement.querySelector('.loc-status');
          let active = true, watchdog, sequence = 0;
          const restore = () => {
            button.disabled = false;
            button.removeAttribute('aria-busy');
            label.textContent = '내 위치로 우리 동 찾기';
          };
          const fail = (code, request) => {
            if (!active || request !== sequence) return;
            clearTimeout(watchdog);
            sequence++;
            restore();
            status.textContent = '';
            setStateValue('location', {error: code, request_id: Date.now(), source: 'browser'});
          };
          button.onclick = () => {
            const request = ++sequence;
            if (!navigator.geolocation || !window.isSecureContext) {
              fail('unavailable', request); return;
            }
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            label.textContent = '현재 위치를 찾고 있어요…';
            status.textContent = '위치 사용 안내가 뜨면 허용해주세요. 잠시만 기다려주세요.';
            const success = (position) => {
              if (!active || request !== sequence) return;
              clearTimeout(watchdog);
              sequence++;
              restore();
              status.textContent = '';
              setStateValue('location', {
                latitude: position.coords.latitude, longitude: position.coords.longitude,
                accuracy: position.coords.accuracy, error: null, request_id: Date.now(), source: 'browser'
              });
            };
            // 데스크톱에서 정밀 위치만 기다리다 끝나는 문제를 줄인다.
            // 네트워크/최근 위치를 먼저 요청하고, 실패한 경우 새 정밀 위치로 한 번 재시도한다.
            watchdog = setTimeout(() => fail(3, request), 22000);
            navigator.geolocation.getCurrentPosition(success, (error) => {
              if (!active || request !== sequence) return;
              if (error.code === 1) { fail(1, request); return; }
              status.textContent = '다른 방법으로 위치를 다시 확인하고 있어요…';
              navigator.geolocation.getCurrentPosition(success, (retryError) => fail(retryError.code, request), {
                enableHighAccuracy: true, timeout: 10000, maximumAge: 0
              });
            }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
          };
          return () => { active = false; clearTimeout(watchdog); button.onclick = null; };
        }
        ''',
    )


CSV_NAME = "step3_비공식돌봄지수.csv"
# github.com/vuski/admdongkor ver20260701 에서 서울(시도코드 11)만 뽑은 행정동 경계
GEOJSON_NAME = "seoul_hangjeongdong.geojson"
HOSP_NAME = "서울시 병의원 위치 정보.csv"  # 공모전 제공 데이터 (cp949)
HOSP_COLS = ["기관명", "병원분류명", "주소", "대표전화1", "병원경도", "병원위도"]
# 가까운 병원에 보여줄 종류 (치과·한의원·요양병원·조산원 등 제외, 보건소는 포함)
HOSP_TYPES = ["의원", "병원", "종합병원", "보건소"]
CENTER_NAME = "행정안전부_읍면동 하부행정기관 현황_20251231.csv"

# Microsoft Fluent Emoji (MIT) Color 스타일 — github.com/microsoft/fluentui-emoji
ICON_DIR = "icons"
ICON_FILES = {
    "store": "convenience_store_color.svg",
    "older": "older_person_color_default.svg",
    "handshake": "handshake_color.svg",
    "office": "office_building_color.svg",
    "ambulance": "ambulance_color.svg",
    "speech": "speech_balloon_color.svg",
    "hospital": "hospital_color.svg",
}

# 화면 표시용 동 이름 (데이터 값은 그대로)
DONG_LABEL = {
    "용신동": "용신동 (용두동·신설동)",
    "상일동": "상일동 (상일1·2동)",
}

# 경계 파일의 동 이름 → CSV의 동 이름
BOUNDARY_TO_CSV = {
    "용두동": "용신동", "신설동": "용신동",
    "상일제1동": "상일동", "상일제2동": "상일동",
    "개포3동": "일원2동",  # 2023년 일원2동 → 개포3동 명칭 변경, CSV는 옛 이름
}


# 주민센터 파일의 동 이름(정리 후) → CSV의 동 이름
CENTER_TO_CSV = {
    "용두동": "용신동", "신설동": "용신동",
    "상일1동": "상일동", "상일2동": "상일동",
    "개포3동": "일원2동",
}


@st.cache_data
def _icon_b64(fname: str) -> str:
    with open(os.path.join(ICON_DIR, fname), "rb") as f:
        return base64.b64encode(f.read()).decode()


def icon(key: str, size: int = 22) -> str:
    """글자 옆에 넣는 아이콘 <img> (unsafe_allow_html=True 필요). 파일이 없으면 빈 문자열"""
    try:
        b64 = _icon_b64(ICON_FILES[key])
    except OSError:
        return ""
    return (f'<img src="data:image/svg+xml;base64,{b64}" width="{size}" height="{size}" '
            f'style="vertical-align:-0.25em;margin-right:0.3em" alt="">')


def dong_label(dong: str) -> str:
    return DONG_LABEL.get(dong, dong)


def norm_dong(name: str) -> str:
    """'홍제제1동' → '홍제1동', '상일제1동' → '상일1동', '금호2-3가동' → '금호2·3가동'
    (주민센터 파일·경계 원래 이름 정리용. 이름 자체에 '제'가 붙은 '홍제1동' 같은 원본엔 쓰지 말 것)"""
    return re.sub(r"(\D)제(\d+동)$", r"\1\2", name).replace("-", "·")
REQUIRED = ["구", "동", "독거노인", "관계형점포수", "접근", "이용", "지속", "비공식지수", "비공식_HL"]

# 유형 라벨 (근후 님께 제안한 수정안 기준)
QUADRANT = {
    ("HIGH", "HIGH"): ("①", "공식·비공식 돌봄 모두 높은 동"),
    ("HIGH", "LOW"): ("②", "공식 돌봄 기관은 많으나, 관계형 가게의 접근·이용이 낮은 동"),
    ("LOW", "HIGH"): ("③", "공식 돌봄 기관은 적으나, 관계형 가게의 접근·이용이 높은 동"),
    ("LOW", "LOW"): ("④", "공식·비공식 돌봄 모두 낮은 동"),
}


# ---------------------------------------------------------------- 데이터
def sample_data() -> pd.DataFrame:
    """실제 CSV가 없을 때 화면 확인용. 동 이름·숫자 모두 가짜."""
    rng = np.random.default_rng(0)
    n = 12
    df = pd.DataFrame({
        "행정동_코드": [f"999{i:05d}" for i in range(n)],
        "구": [f"예시구{i % 3 + 1}" for i in range(n)],
        "동": [f"예시동{i + 1}" for i in range(n)],
        "독거노인": rng.integers(200, 1500, n),
        "관계형점포수": rng.integers(50, 1500, n),
        "이용": rng.uniform(0.05, 0.35, n).round(3),
        "지속": rng.uniform(0.85, 0.98, n).round(3),
    })
    df["접근"] = (df["관계형점포수"] / df["독거노인"] * 1000).round(1)
    r = df[["접근", "이용", "지속"]].rank(pct=True)
    df["비공식지수"] = (r.prod(axis=1) ** (1 / 3) * 100).round(1)
    df["비공식_HL"] = np.where(df["비공식지수"] >= df["비공식지수"].median(), "HIGH", "LOW")
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["독거노인", "관계형점포수", "접근", "이용", "지속", "비공식지수"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")  # '산출불가' → NaN
    df = df.dropna(subset=["비공식지수"])
    # 원자료 값 → 동 안에서의 백분위(0~100). 쉬운 말 설명용
    for c in ["접근", "이용", "지속"]:
        df[c + "_pct"] = (df[c].rank(pct=True) * 100).round(0)
    return df.reset_index(drop=True)


@st.cache_data
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file, encoding="utf-8-sig")


@st.cache_data
def load_boundaries(path: str) -> list:
    """[(구, CSV 동 이름, 경계 원래 동 이름, bbox, [폴리곤의 링 목록, ...]), ...]"""
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for feat in gj["features"]:
        p, geom = feat["properties"], feat["geometry"]
        raw = p["adm_nm"].split()[-1]
        dong = BOUNDARY_TO_CSV.get(raw, raw)
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        xs = [pt[0] for poly in polys for pt in poly[0]]
        ys = [pt[1] for poly in polys for pt in poly[0]]
        out.append((p["sggnm"], dong, raw, (min(xs), min(ys), max(xs), max(ys)), polys))
    return out


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def find_dong(lat: float, lon: float, boundaries: list):
    """좌표가 속한 (구, CSV 동, 경계 원래 동). 서울 밖이면 None"""
    for gu, dong, raw, (x0, y0, x1, y1), polys in boundaries:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in polys:
            if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
                return gu, dong, raw
    return None


def dong_center(gu: str, dong: str, boundaries: list):
    """동 경계(합친 동은 여러 조각)의 면적가중 중심점 (lat, lon). 없으면 None"""
    a_sum = cx_sum = cy_sum = 0.0
    for g, d, _, _, polys in boundaries:
        if (g, d) != (gu, dong):
            continue
        for poly in polys:
            ring = poly[0]
            for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
                cross = x0 * y1 - x1 * y0
                a_sum += cross
                cx_sum += (x0 + x1) * cross
                cy_sum += (y0 + y1) * cross
    if a_sum == 0:
        return None
    return cy_sum / (3 * a_sum), cx_sum / (3 * a_sum)


@st.cache_data
def load_hospitals(path: str) -> pd.DataFrame:
    h = pd.read_csv(path, encoding="cp949", usecols=HOSP_COLS)
    # 면목보건분소처럼 '기타'로 분류된 보건지소·분소도 보건소로 묶음
    public = (h["병원분류명"] == "기타") & h["기관명"].str.contains("보건지소|보건분소")
    h.loc[public, "병원분류명"] = "보건소"
    return h[h["병원분류명"].isin(HOSP_TYPES)].reset_index(drop=True)


@st.cache_data
def load_centers(path: str) -> pd.DataFrame:
    """서울 주민센터: 구, 동(CSV 기준), 원래동(합치기 전), 이름, 주소"""
    c = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    c = c[c["시도"] == "서울"]
    raw = c["읍면동"].str.replace(r"\s*주민센터$", "", regex=True).str.strip().map(norm_dong)
    return pd.DataFrame({
        "구": c["시군구"], "동": raw.map(lambda d: CENTER_TO_CSV.get(d, d)),
        # 이름은 앱 표기(홍제1동, 금호2·3가동)에 맞춤. 원자료: '홍제제1동 주민센터'
        "원래동": raw, "이름": raw + " 주민센터", "주소": c["주소"],
    }).reset_index(drop=True)


def nearest(hosp: pd.DataFrame, lat: float, lon: float, k: int = 3) -> pd.DataFrame:
    """직선(대권) 거리 기준 가까운 k곳"""
    la1, lo1 = np.radians(lat), np.radians(lon)
    la2, lo2 = np.radians(hosp["병원위도"].to_numpy()), np.radians(hosp["병원경도"].to_numpy())
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    out = hosp.assign(거리_km=6371.0 * 2 * np.arcsin(np.sqrt(h)))
    return out.nsmallest(k, "거리_km")


nav_slot = st.sidebar.container()
with st.sidebar:
    with st.expander("분석자료 설정"):
        up = st.file_uploader(f"{CSV_NAME} 업로드", type="csv")

try:
    raw = load_csv(up) if up is not None else load_csv(CSV_NAME)
    is_sample = False
except FileNotFoundError:
    raw = sample_data()
    is_sample = True

missing = [c for c in REQUIRED if c not in raw.columns]
if missing:
    st.error(f"CSV에 필요한 컬럼이 없어요: {', '.join(missing)}")
    st.stop()

df = prepare(raw)
# 공식 자료의 HIGH/LOW는 공간 반영 지수의 중앙값 기준이다.
formal_file = "step1_공식돌봄지수.csv"
if up is None and not is_sample and os.path.exists(formal_file):
    formal = pd.read_csv(formal_file, encoding="utf-8-sig", dtype={"구": str, "동": str})
    required_formal = ["구", "동", "공식_HL", "공식지수_공간", "공식지수_순수"]
    if all(col in formal.columns for col in required_formal):
        formal = formal[required_formal].copy()
        formal["동"] = formal["동"].replace({"종로1234가동": "종로1·2·3·4가동", "종로56가동": "종로5·6가동"})
        if not formal.duplicated(["구", "동"]).any():
            df = df.drop(columns=[c for c in required_formal[2:] if c in df.columns])
            df = df.merge(formal, on=["구", "동"], how="left", validate="one_to_one")
# 최종 매트릭스와 별도 공간분석 대상의 우선순위 결과를 연결한다.
if up is None and not is_sample and os.path.exists("step4_최종_돌봄지수_매트릭스_결과.csv"):
    matrix = pd.read_csv("step4_최종_돌봄지수_매트릭스_결과.csv", encoding="utf-8-sig")
    matrix["동"] = matrix["동"].replace({"종로1234가동":"종로1·2·3·4가동", "종로56가동":"종로5·6가동"})
    cols = ["구", "동", "공식_HL", "비공식_HL", "공식지수_공간", "비공식지수", "돌봄유형_2x2"]
    if all(c in matrix.columns for c in cols) and not matrix.duplicated(["구", "동"]).any():
        df = df.drop(columns=[c for c in cols[2:] if c in df.columns]).merge(matrix[cols], on=["구", "동"], how="left", validate="one_to_one")
if up is None and not is_sample and os.path.exists("step5_최종_돌봄지수_LISA_통합결과.csv"):
    combined = pd.read_csv("step5_최종_돌봄지수_LISA_통합결과.csv", encoding="utf-8-sig")
    cols = ["구", "동_df", "최종돌봄지수_합성"]
    if all(c in combined.columns for c in cols):
        combined = combined[cols].rename(columns={"동_df": "동"}).dropna(subset=["구", "동"])
        combined["동"] = combined["동"].replace({"종로1234가동": "종로1·2·3·4가동", "종로56가동": "종로5·6가동"})
        if combined.groupby(["구", "동"])["최종돌봄지수_합성"].nunique(dropna=False).le(1).all():
            combined = combined.drop_duplicates(["구", "동"])
            df = df.drop(columns=["최종돌봄지수_합성"], errors="ignore").merge(combined, on=["구", "동"], how="left", validate="one_to_one")
if up is None and not is_sample and os.path.exists("step6_최종_돌봄사각지대_우선순위_전체결과.csv"):
    priority = pd.read_csv("step6_최종_돌봄사각지대_우선순위_전체결과.csv", encoding="utf-8-sig")
    priority.loc[(priority["구"] == "강남구") & (priority["동"] == "개포3동"), "동"] = "일원2동"
    cols = ["구", "동", "최종순위", "우선순위점수"]
    if all(c in priority.columns for c in cols) and not priority.duplicated(["구", "동"]).any():
        df = df.merge(priority[cols], on=["구", "동"], how="left", validate="one_to_one")
has_formal = "공식_HL" in df.columns


# 가게 정보는 브라우저별 localStorage에만 보관한다. 서버 공용 파일/URL에는 쓰지 않는다.
@st.cache_resource
def shop_storage():
    return components.component(
        "anbu_shop_storage",
        js="""
        export default function({data, parentElement, setStateValue}) {
          if (!data?.id || parentElement.__anbuStorageCommand === data.id) return;
          parentElement.__anbuStorageCommand = data.id;
          const key = 'anbu.shop-profile.v1';
          const result = {id:data.id, op:data.op, profile:null, error:null};
          try {
            if (data.op === 'save') {
              const encoded = JSON.stringify(data.profile);
              window.localStorage.setItem(key, encoded);
              if (window.localStorage.getItem(key) !== encoded) throw new Error('storage');
              result.profile = data.profile;
            } else if (data.op === 'clear') {
              window.localStorage.removeItem(key);
            } else {
              const saved = window.localStorage.getItem(key);
              if (saved !== null) {
                try { result.profile = JSON.parse(saved); }
                catch (_) { result.error = 'invalid'; }
              }
            }
          } catch (_) { result.error = 'unavailable'; }
          setStateValue('snapshot', result);
        }
        """,
    )


def validated_shop(value, available_dongs, require_owner=False):
    if not isinstance(value, dict) or value.get("version") != 1:
        return None
    name, gu, dong = (value.get(k) for k in ("shop_name", "gu", "dong"))
    if not all(isinstance(v, str) for v in (name, gu, dong)):
        return None
    name = name.strip()
    if not name or len(name) > 40 or any(ord(c) < 32 for c in name):
        return None
    owner_name = value.get("owner_name", "")
    if not isinstance(owner_name, str):
        return None
    owner_name = owner_name.strip()
    if (require_owner and not owner_name) or len(owner_name) > 30 or any(ord(c) < 32 for c in owner_name):
        return None
    if (gu, dong) not in available_dongs:
        return None
    return {"version": 1, "shop_name": name, "owner_name": owner_name, "gu": gu, "dong": dong}


def apply_shop(profile):
    position = st.session_state.pop("setup_my_loc", None)
    st.session_state["shop_profile"] = profile
    st.session_state["app_started"] = True
    st.session_state["editing_shop"] = False
    st.session_state["entry_pending"] = True
    st.session_state["sel"] = (profile["gu"], profile["dong"])
    st.session_state["active_page"] = PAGES[1]
    st.session_state["scroll_revision"] = st.session_state.get("scroll_revision", 0) + 1
    for key in ("quick_dong", "gu_sel", "dong_sel"):
        st.session_state[key] = None
    for key in ("loc_msg", "loc_candidate", "my_loc", "loc_done", "pending_page"):
        st.session_state.pop(key, None)
    if position and tuple(position[2:4]) == (profile["gu"], profile["dong"]):
        st.session_state["my_loc"] = position


def edit_shop():
    profile = st.session_state.get("shop_profile") or {}
    st.session_state["shop_name_input"] = profile.get("shop_name", "")
    st.session_state["owner_name_input"] = profile.get("owner_name", "")
    st.session_state["shop_dong_input"] = ((profile["gu"], profile["dong"]) if profile else None)
    st.session_state["editing_shop"] = True
    st.session_state["profile_save_error"] = False
    st.session_state["setup_location_revision"] = st.session_state.get("setup_location_revision", 0) + 1
    for key in ("setup_location_done", "setup_location_candidate", "setup_location_message"):
        st.session_state.pop(key, None)
    position = st.session_state.get("my_loc")
    if position and tuple(position[2:4]) == (profile.get("gu"), profile.get("dong")):
        st.session_state["setup_my_loc"] = position
    else:
        st.session_state.pop("setup_my_loc", None)


def queue_shop_save(profile=None, op="save"):
    st.session_state["shop_command"] = {"id": str(uuid4()), "op": op, "profile": profile}
    st.session_state["profile_save_error"] = False



def forget_setup_position():
    for key in ("setup_my_loc", "setup_location_candidate", "setup_location_message"):
        st.session_state.pop(key, None)


def accept_setup_dong(candidate, precise=False):
    st.session_state["shop_dong_input"] = tuple(candidate[2:4])
    st.session_state.pop("setup_location_candidate", None)
    st.session_state["setup_location_message"] = ("success", f"{candidate[2]} {dong_label(candidate[3])}으로 골랐어요.")
    if precise:
        st.session_state["setup_my_loc"] = candidate
    else:
        st.session_state.pop("setup_my_loc", None)


def shop_location_picker(scope, expected_dong=None):
    """Click-only GPS. A coarse fix can choose a dong but cannot rank nearby hospitals."""
    if not os.path.exists(GEOJSON_NAME):
        st.caption("위치 경계 자료가 없어 동 이름으로 직접 선택해주세요.")
        return False
    revision = st.session_state.get("setup_location_revision", 0)
    result = location_button()(key=f"anbu_{scope}_location_{revision}", on_location_change=lambda: None)
    loc = result.location or {} if result else {}
    st.caption("가게에서 눌러주세요. 위치는 이 앱을 이용하는 동안 병원·보건소 거리 안내에 사용해요.")
    done_key = f"{scope}_location_done"
    message_key = f"{scope}_location_message"
    candidate_key = f"{scope}_location_candidate"
    if scope == "help" and st.session_state.get("help_location_context") != expected_dong:
        st.session_state["help_location_context"] = expected_dong
        st.session_state.pop(message_key, None)
    request = loc.get("request_id") or str(loc)
    changed = False
    if loc and st.session_state.get(done_key) != request:
        st.session_state[done_key] = request
        st.session_state.pop(candidate_key, None)
        if loc.get("error"):
            message = {1: "위치 권한이 꺼져 있어요. 브라우저에서 허용하거나 동 이름으로 선택해주세요.",
                       2: "기기에서 위치를 받지 못했어요. 동 이름으로 선택하거나 다시 시도해주세요.",
                       3: "위치 찾기에 시간이 걸리고 있어요. 동 이름으로 선택하거나 다시 시도해주세요."}
            st.session_state[message_key] = ("warning", message.get(loc["error"], "위치를 받지 못했어요. 다시 시도해주세요."))
        else:
            lat, lon, accuracy = loc.get("latitude"), loc.get("longitude"), loc.get("accuracy")
            valid = (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                     and np.isfinite(lat) and np.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180)
            hit = find_dong(lat, lon, load_boundaries(GEOJSON_NAME)) if valid else None
            if not hit or (hit[0], hit[1]) not in available_dongs:
                st.session_state[message_key] = ("warning", "현재 위치에 맞는 서울 행정동을 찾지 못했어요. 동 이름으로 선택해주세요.")
            elif expected_dong and tuple(hit[:2]) != tuple(expected_dong):
                st.session_state[message_key] = ("warning", f"현재 위치는 {hit[0]} {dong_label(hit[1])}이에요. 등록한 가게 동네와 달라 거리 기준에 반영하지 않았어요. 가게에서 다시 누르거나 가게 정보를 바꿔주세요.")
            else:
                candidate = (lat, lon, *hit)
                precise = (isinstance(accuracy, (int, float)) and np.isfinite(accuracy) and 0 <= accuracy <= 1000)
                if precise:
                    if scope == "setup":
                        accept_setup_dong(candidate, precise=True)
                    else:
                        st.session_state["my_loc"] = candidate
                        changed = True
                    st.session_state["location_accuracy"] = accuracy
                    st.session_state[message_key] = ("success", f"{hit[0]} {dong_label(hit[1])}의 가게 위치를 확인했어요. 병원·보건소도 이 위치에서 찾아요.")
                elif scope == "setup":
                    st.session_state[candidate_key] = candidate
                    st.session_state[message_key] = ("warning", "위치가 대략적으로 잡혔어요. 동네가 맞는지 확인해주세요. 가까운 병원 거리는 더 정확한 위치를 받은 뒤 안내해요.")
                else:
                    st.session_state[message_key] = ("warning", "위치 오차가 커서 가까운 병원을 정하기 어려워요. 가게에서 위치를 다시 확인해주세요.")
    kind, message = st.session_state.get(message_key, (None, None))
    if kind:
        getattr(st, kind)(message)
    candidate = st.session_state.get(candidate_key)
    if candidate and scope == "setup":
        st.button(f"{candidate[2]} {dong_label(candidate[3])}으로 선택", key="accept_setup_dong",
                  on_click=accept_setup_dong, args=(candidate,), width="stretch")
    return changed


available_dongs = sorted(set(zip(df["구"], df["동"])))
command = st.session_state.setdefault("shop_command", {"id": "load", "op": "load"})
storage = shop_storage()(key="anbu_shop_profile", data=command, on_snapshot_change=lambda: None)
snapshot = storage.snapshot if storage else None
if snapshot and snapshot.get("id") == command["id"] and st.session_state.get("shop_ack") != command["id"]:
    st.session_state["shop_ack"] = command["id"]
    error = snapshot.get("error")
    st.session_state["shop_storage_error"] = error
    if command["op"] == "load":
        st.session_state["shop_hydrated"] = True
        saved = validated_shop(snapshot.get("profile"), available_dongs)
        if saved:
            apply_shop(saved)
        elif snapshot.get("profile") is not None:
            st.session_state["shop_storage_error"] = "invalid"
    elif command["op"] == "save":
        saved = validated_shop(snapshot.get("profile"), available_dongs)
        if not error and saved:
            apply_shop(saved)
        else:
            st.session_state["profile_save_error"] = True
    elif command["op"] == "clear":
        if not error:
            st.session_state.pop("shop_profile", None)
            st.session_state["shop_name_input"] = ""
            st.session_state["owner_name_input"] = ""
            st.session_state["shop_dong_input"] = None
            st.session_state["editing_shop"] = True
            st.session_state.pop("sel", None)
            for key in ("my_loc", "setup_my_loc", "location_accuracy", "setup_location_candidate",
                        "setup_location_message", "setup_location_done", "help_location_message", "help_location_done"):
                st.session_state.pop(key, None)
        else:
            st.session_state["profile_save_error"] = True

if not st.session_state.get("shop_hydrated") or st.session_state.get("shop_ack") != command["id"]:
    st.markdown('<style>[data-testid="stSidebar"]{display:none}</style>', unsafe_allow_html=True)
    st.caption("가게 정보를 불러오고 있어요…" if command["op"] == "load" else "가게 정보를 저장하고 있어요…")
    st.stop()

def render_about_overview():
    """동네 등록 전후에 같은 소개를 보여준다."""
    st.markdown("""<style>
    .about-app {box-sizing:border-box;word-break:keep-all;text-align:center;scroll-margin-top:85px!important;}
    .about-heading {margin:0;padding:0;}
    .st-key-about-informal-card,.st-key-about-neighborhood-card,.st-key-about-formal-card {
      box-sizing:border-box;background:#FFF;border:1px solid #D6E6F2;border-radius:20px;
      padding:22px;margin-top:16px;word-break:keep-all;text-align:left;}
    .st-key-about-informal-card p,.st-key-about-neighborhood-card p,
    .st-key-about-formal-card p {text-align:left!important;}
    .st-key-about-informal-card h2,.st-key-about-informal-card h3,
    .st-key-about-neighborhood-card h2,.st-key-about-neighborhood-card h3,
    .st-key-about-formal-card h2,.st-key-about-formal-card h3,
    .st-key-about-informal-card .intro-index-title,
    .st-key-about-informal-card .intro-index-factor strong {text-align:left!important;}
    .st-key-about-informal-card h2.find-title,
    .st-key-about-informal-card .intro-index-title {font-size:1.5rem!important;line-height:1.5;}
    .st-key-about-informal-card h3,.st-key-about-neighborhood-card h3,
    .st-key-about-formal-card h3 {font-size:1.12rem!important;}
    .st-key-about-informal-card .factor-head {justify-content:flex-start;text-align:left;}
    @media(max-width:400px) {
      .st-key-about-informal-card,.st-key-about-neighborhood-card,.st-key-about-formal-card {padding:20px;}
    }
    .about-kicker {color:#6A80AB;font-size:.8rem;font-weight:750;letter-spacing:.04em;margin-bottom:12px;}
    .about-title {color:#1C2E43;font-size:1.9rem;line-height:1.45;font-weight:800;margin:0;letter-spacing:-.025em;}
    .about-title-accent {background:linear-gradient(transparent 76%,#CFEFFF 76%);
      box-decoration-break:clone;-webkit-box-decoration-break:clone;}
    .about-app .about-lead {color:#526782;font-size:1rem;line-height:1.85;margin:18px 0 0!important;}
    .about-points {display:grid;grid-template-columns:minmax(0,1fr);gap:12px;margin:22px 0 28px;}
    .about-point {display:flex;align-items:center;justify-content:flex-start;text-align:left;gap:14px;min-width:0;box-sizing:border-box;
      background:#FFF;border:1px solid #DCE8F2;border-radius:18px;padding:16px;color:#526782;
      font-size:.9rem;line-height:1.7;}
    .about-point-icon {display:flex;align-items:center;justify-content:center;flex:0 0 44px;
      width:44px;height:44px;border-radius:14px;background:#E9F6FF;color:#0878CF;}
    .about-point-icon svg {width:23px;height:23px;display:block;}
    .about-point-copy {min-width:0;}
    .about-point strong {display:block;color:#203B58;font-size:1rem;line-height:1.6;margin-bottom:3px;}
    .about-point-detail {display:block;}
    @media(min-width:680px) {.about-points {grid-template-columns:1fr 1fr;}}
    </style>""", unsafe_allow_html=True)
    st.markdown("""<section id="index-start" class="about-app" tabindex="-1">
      <div class="about-heading"><div class="about-kicker">사장님과 동네를 잇는 안부</div>
      <div class="about-title" role="heading" aria-level="1"><span class="about-title-accent">안부가게</span>가 뭐예요?</div></div>
      <p class="about-lead">안부가게는 사장님이 <strong>우리 동네의 상황을 살펴보고</strong>,
      걱정되는 어르신을 <strong>도움받을 곳에 연결할 수 있도록</strong> 돕는 앱이에요.</p>
      <div class="about-points">
        <div class="about-point"><span class="about-point-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg></span>
          <div class="about-point-copy"><strong>우리 동네 보기</strong><span class="about-point-detail">가게에서 만날 기회와 어르신 수를 살펴봐요.</span></div></div>
        <div class="about-point"><span class="about-point-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 8.8c0 4.1-4.1 7.7-8.5 10.2C7.6 16.5 3.5 12.9 3.5 8.8a4.3 4.3 0 0 1 8.5-1 4.3 4.3 0 0 1 8.5 1Z"/></svg></span>
          <div class="about-point-copy"><strong>도움받을 곳 찾기</strong><span class="about-point-detail">걱정될 때 주민센터와 상담할 곳을 찾아요.</span></div></div>
      </div>
    </section>""", unsafe_allow_html=True)


def render_informal_definition():
    st.markdown('''<div class="index-definition index-intro"><strong>동네 가게를 통해 어르신을 만나고,
        안부를 살필 수 있는 여건</strong>을 비교하기 위해 저희 팀이 만든 점수예요.<br><br>
        가게가 얼마나 가까이 있는지, 어르신이 얼마나 이용하는지,
        가게가 얼마나 유지되는지, <strong>세 가지를 함께</strong> 살펴봐요.</div>''', unsafe_allow_html=True)


def render_index_method():
    with st.expander("산출 기준과 사용 데이터 보기"):
        st.write("접근·이용·지속을 각각 서울 행정동 간 백분위 순위로 바꾸고, 세 값의 기하평균에 "
                 "100을 곱했어요. 지수 중앙값 이상을 HIGH(높음), 미만을 LOW(낮음)로 나눴어요.")
        if not is_sample and up is None:
            st.write("관계형 가게는 34개 업종으로 선정했어요. 접근·이용은 2025년 4분기, "
                     "지속은 2025년 1~4분기 서울시 상권분석서비스 자료를 사용했어요.")
            st.write("독거노인 수는 서울특별시 기본통계의 2025년 독거노인 현황(연령별/동별)을 사용했어요.")
        else:
            st.write("현재 선택한 업로드·예시 데이터의 기준 시점은 해당 원자료를 확인해주세요.")


def render_formal_explainer():
    with st.container(key="about-formal-card"):
        st.markdown('<h3 class="section-title">기관이 제공하는 돌봄도 함께 살펴봐요</h3>', unsafe_allow_html=True)
        if "row" in globals() and row is not None and formal_for(row) and pd.notna(row.get("공식지수_공간")):
            st.markdown(f'<div class="index-score selected-score">{escape(place)}의 공식 돌봄 지수 (공간 반영)<br><strong>{float(row["공식지수_공간"]):.1f}</strong> / 100점</div>', unsafe_allow_html=True)
        st.write("공식 돌봄 지수는 보건·복지기관을 통한 돌봄 기반을 비교하기 위해 우리 팀이 만든 점수예요. "
                 "가게 기반을 보는 비공식 지수와 함께 우리 동을 살펴보는 데 사용해요.")
        for domain, detail in [
            ("보건의료", "재택의료·정신건강·치매관리"),
            ("건강관리", "방문건강·건강생활 지원"),
            ("장기요양", "방문요양·목욕·간호, 주야간보호"),
            ("일상돌봄", "노인맞춤돌봄·특화·응급안전 서비스"),
        ]:
            st.markdown(f'<div class="formal-domain"><strong>{domain}</strong><span>{detail}</span></div>', unsafe_allow_html=True)
        with st.expander("공식 지수의 산출 자료와 현재 반영 범위"):
            st.write("공유된 산출 설명에서는 독거노인 1,000명당 기관 수를 구하고, "
                     "각 부문을 백분위 점수로 바꿔요. 장기요양은 중복 서비스를 제거한 고유 기관 수를 사용해요.")
            st.write("기관 수는 보건의료 88개, 건강관리 63개, 장기요양 2,621개, 일상돌봄 70개로 제시되어 있어요. "
                     "이는 팀이 분석에 사용한 집계이며, 현재 운영 중인 기관의 실시간 수가 아니에요.")
            st.write("공유 결과의 분석 대상은 425개 동, 공간을 반영하기 전 순수 지수 중앙값은 약 46.69점이에요. "
                     "부문별 최종 가중치·종합 산식과 원자료 기준연도는 공유 이미지에서 확인되지 않아 기재하지 않았어요.")
            st.caption("동별 결과표: 팀 제공 step1_공식돌봄지수.csv. 순수 지수 중앙값은 약 46.69점이며, "
                       "현재 유형 분류에는 공간 반영 지수와 해당 파일의 높음·낮음 구분을 사용해요. "
                       "공간 반영 지수의 중앙값은 약 41.34점이에요.")


def open_intro_index():
    profile = st.session_state.get("shop_profile")
    if profile:
        st.session_state["app_started"] = True
        st.session_state["editing_shop"] = False
        st.session_state["sel"] = (profile["gu"], profile["dong"])
        st.session_state["active_page"] = PAGES[2]
        st.session_state["scroll_revision"] = st.session_state.get("scroll_revision", 0) + 1
    else:
        st.session_state["intro_index"] = True


def close_intro_index():
    st.session_state["intro_index"] = False


if st.session_state.get("intro_index") and not st.session_state.get("shop_profile"):
    st.markdown("""<style>
      .stApp,[data-testid="stAppViewContainer"] {background:#F4FAFF;color:#1C2E43;}
      [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
      [data-testid="stAppDeployButton"] {display:none!important;}
      [data-testid="stMainBlockContainer"] {max-width:720px;padding:1.25rem 20px 3rem;}
      .intro-index-label {font-size:.8rem;font-weight:750;color:#6A80AB;margin-bottom:14px;}
      .intro-index-title {font-size:1.85rem;line-height:1.5;font-weight:800;color:#1C2E43;margin:0;}
      .index-definition {color:#526782;line-height:1.9;margin:22px 0;word-break:keep-all;}
      .intro-index-factor {background:#FFF;border:1px solid #D6EAF7;border-radius:16px;
        padding:18px;margin:12px 0;color:#304A68;line-height:1.7;word-break:keep-all;}
      .intro-index-factor strong {display:block;margin-bottom:5px;}
      .formal-domain {display:flex;flex-direction:column;gap:4px;padding:14px 3px;
        border-bottom:1px solid #D6EAF7;line-height:1.7;color:#4E698A;word-break:keep-all;}
      .section-title {font-size:1.25rem;color:#385574;line-height:1.6;}
      [data-testid="stButton"] button[kind="primary"] {background:#0878CF;border-color:#0878CF;min-height:54px;}
    </style>""", unsafe_allow_html=True)
    render_about_overview()
    with st.container(key="about-informal-card"):
        st.markdown('<div class="intro-index-title" role="heading" aria-level="2">비공식 돌봄 지수</div>',
                    unsafe_allow_html=True)
        render_informal_definition()
        st.info("가게와 동네를 등록하면 우리 동의 점수와 자료도 볼 수 있어요.")
        st.subheader("이 세 가지로 계산했어요")
        for title, detail in [
            ("가까이 있는 가게", "독거노인 1,000명당 관계형 가게 수"),
            ("어르신 이용 비중", "관계형 가게 결제 건수 중 60대 이상 비중"),
            ("가게가 유지되는 정도", "연간 폐업률을 바탕으로 계산한 값"),
        ]:
            st.markdown(f'<div class="intro-index-factor"><strong>{title}</strong>{detail}</div>',
                        unsafe_allow_html=True)
        render_index_method()
    with st.container(key="about-neighborhood-card"):
        st.subheader("우리 동네를 어떻게 나눴나요?")
        st.write("기관 돌봄과 가게 돌봄 기반의 높고 낮음을 함께 살펴 네 가지 경우로 나눠요.")
        st.caption("이 구분은 동네 여건을 비교한 것으로, 개별 어르신의 위험도를 판정하지 않아요.")
    render_formal_explainer()
    st.button("소개 화면으로 돌아가기", key="intro_index_back", type="primary", width="stretch",
              on_click=close_intro_index)
    st.stop()


if not st.session_state.get("app_started"):
    st.markdown("""<style>
    .stApp,[data-testid="stAppViewContainer"] {background:#0785E8;}
    [data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
    [data-testid="stAppDeployButton"] {display:none!important;}
    [data-testid="stMain"] {overflow-x:clip!important;}
    [data-testid="stMainBlockContainer"] {padding:0 24px!important;}
    .st-key-landing-shell {position:relative;isolation:isolate;box-sizing:border-box;width:100%;min-width:0;
      min-height:calc(100svh - 68px);display:flex;flex-direction:column;align-items:center;justify-content:flex-start;
      padding:24px 0 24px;gap:16px;}
    .st-key-landing-shell > [data-testid="stLayoutWrapper"]:has(> .st-key-intro-core) {
      display:flex;flex:1 1 auto;width:100%;min-width:0;}
    .st-key-intro-core {display:flex;flex-direction:column;align-items:center;justify-content:center;
      box-sizing:border-box;width:100%;min-width:0;flex:1 1 auto;gap:16px;padding-top:25px;}
    .st-key-intro-core > [data-testid="stElementContainer"] {width:100%;min-width:0;}
    .st-key-landing-shell > [data-testid="stElementContainer"] {width:100%;min-width:0;}
    .st-key-landing-shell > [data-testid="stElementContainer"]:last-child {margin-top:auto;padding-top:26px;}
    .intro-orb {display:none;}
    .intro-copy {position:relative;isolation:isolate;display:flex;flex-direction:column;align-items:center;
      box-sizing:border-box;width:min(100%,380px);min-width:0;padding:82px 8px 24px;text-align:center;word-break:keep-all;
      transition:filter .36s,opacity .36s,transform .36s;}
    .intro-copy.intro-leaving {filter:blur(13px);opacity:0;transform:scale(1.025);}
    .intro-title {position:relative;isolation:isolate;display:block;width:max-content;max-width:100%;
      font-size:4rem;line-height:1.25;letter-spacing:.025em;
      font-weight:800;color:#FFF;margin:0 auto;padding:0;text-align:center;white-space:nowrap;}
    .intro-copy::before {content:"";position:absolute;z-index:-1;pointer-events:none;inset:0;
      background:center / 100% 100% no-repeat url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 360 300' preserveAspectRatio='none'%3E%3Cpath fill='%23fff' fill-opacity='.16' d='M8 76 168 8Q180 2 192 8L352 76Q357 79 354 84Q352 88 345 88H340V283Q340 296 327 296H33Q20 296 20 283V88H15Q8 88 6 84Q3 79 8 76Z'/%3E%3C/svg%3E");}
    .intro-lead {width:100%;font-family:"Pretendard Variable",Pretendard,sans-serif;font-size:clamp(.85rem,4.6vw,1.2rem);line-height:1.75;color:#FFF;font-weight:400;
      margin:24px 0 0;text-align:center;}
    .intro-line {display:block;width:100%;text-align:center;white-space:nowrap;}
    .st-key-intro-cta {width:100%!important;min-width:0;max-width:300px;align-self:center;
      margin:32px auto 0!important;position:relative;z-index:1;}
    .st-key-intro-about {width:100%!important;max-width:300px;align-self:center;}
    .st-key-intro-about button {box-sizing:border-box;display:flex;align-items:center;
      justify-content:space-between;gap:16px;width:100%;min-height:74px;padding:12px 13px 12px 24px;
      border:1px solid #FFFFFF;border-radius:23px;background:#FFF;color:#0878CF;
      box-shadow:0 10px 24px #005AA525;transition:background .2s,transform .2s;}
    .st-key-intro-about button p {font:700 18px/1.5 "Pretendard Variable",Pretendard,system-ui,sans-serif;letter-spacing:-.025em;
      text-align:center;word-break:keep-all;}
    .st-key-intro-about button [data-testid="stMarkdownContainer"] {flex:1;min-width:0;}
    .st-key-intro-about button::after {content:"";display:block;box-sizing:border-box;flex:0 0 48px;width:48px;height:48px;
      border:1px solid #CFE8FA;border-radius:50%;background-color:#FFF;background-repeat:no-repeat;background-position:center;
      background-size:32px 32px;
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Cpath d='M6 16h20M18 7l9 9-9 9' stroke='%230878CF' stroke-width='2.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");}
    .st-key-intro-about button:hover {background:#F0F9FF;border-color:#FFF;color:#0878CF;transform:translateY(-2px);}
    .st-key-intro-about button:focus-visible {outline:3px solid #FFF;outline-offset:5px;}
    .intro-foot {width:100%;text-align:center;color:#FFF;font-size:.82rem;line-height:1.7;
      margin:0;letter-spacing:.04em;}
    .intro-credit {display:block;margin-top:8px;color:#E3F3FF;font-size:.74rem;letter-spacing:.02em;}
    @media(max-width:340px) {.intro-title {font-size:3.2rem;}}
    @media(max-height:740px) {.st-key-intro-core {padding-top:32px;}
      .st-key-intro-cta {margin-top:30px!important;}}
    @media(prefers-reduced-motion:reduce) {.intro-copy,.st-key-intro-about button {transition:none;}}
    </style>""", unsafe_allow_html=True)
    with st.container(key="landing-shell"):
        with st.container(key="intro-core"):
            st.markdown(f'''<div class="intro-orb one"></div><div class="intro-orb two"></div>
            <section class="intro-copy" aria-label="안부가게 소개">
            <div class="intro-title" role="heading" aria-level="1">안부가게</div>
            <div class="intro-lead"><span class="intro-line">매일 열리는 사장님의 가게가,</span>
            <span class="intro-line">누군가의 안부가 됩니다.</span></div>
            </section>''', unsafe_allow_html=True)
            with st.container(key="intro-cta"):
                started = intro_button()(key=f"anbu_intro_{st.session_state.get('intro_revision', 0)}", on_started_change=lambda: None)
                if started and started.started:
                    begin_app()
                    st.rerun()
            with st.container(key="intro-about"):
                st.button("안부가게 알아보기", key="intro_about", width="stretch", on_click=open_intro_index)
        st.markdown('<footer class="intro-foot">작은 관심이 이어지는 동네'
                    '<small class="intro-credit">© 2026 소시오패스 · 안부가게</small></footer>', unsafe_allow_html=True)
    st.stop()




if not st.session_state.get("shop_profile") or st.session_state.get("editing_shop"):
    st.markdown("""<style>
    .stApp,[data-testid="stAppViewContainer"] {background:#F4FAFF;color:#1C2E43;}
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
    [data-testid="stAppDeployButton"] {display:none!important;}
    [data-testid="stMainBlockContainer"] {max-width:720px;padding:8vh 24px 60px;}
    .st-key-shop-setup {background:#FFF;border:1px solid #E1E7F0;border-radius:28px;
      padding:clamp(24px,5vw,44px);box-shadow:0 18px 65px #24395708;}
    .shop-eyebrow {color:#657B96;font-size:.85rem;font-weight:700;letter-spacing:.08em;margin-bottom:18px;}
    .shop-title {font-size:clamp(2rem,5vw,2.8rem)!important;line-height:1.4!important;
      letter-spacing:-.025em;color:#1C2E43;padding:0!important;margin:0 0 18px!important;word-break:keep-all;text-wrap:balance;}
    .shop-lead {color:#65758B;line-height:1.85;margin:0 0 20px;word-break:keep-all;}
    .st-key-shop-setup [data-testid="stForm"] {border:0;padding:0;}
    .st-key-shop-setup label {font-size:1rem;font-weight:650;color:#243C58;}
    .st-key-shop-setup input {font-size:17px;}
    .st-key-shop-setup [data-testid="stBaseButton-primary"] {background:#0878CF;border-color:#0878CF;min-height:54px;}
    .st-key-shop-setup [data-testid="stBaseButton-primary"] p {font-size:1.125rem;font-weight:700;}
    .st-key-shop-setup button {min-height:46px;}
    .setup-location-label {margin:18px 0 12px;color:#243C58;font-size:1rem;font-weight:650;}
    @media(min-width:0px) {
      [data-testid="stMainBlockContainer"] {padding:5rem 18px 2rem;}
      .st-key-shop-setup {padding:24px 20px;border-radius:22px;}
      .shop-title {font-size:1.85rem!important;line-height:1.5!important;}
      .shop-lead {font-size:1rem;line-height:1.8;text-wrap:pretty;}
      .st-key-shop-setup button p {line-height:1.6;word-break:keep-all;}
    }
    </style>""", unsafe_allow_html=True)
    existing = st.session_state.get("shop_profile")
    with st.container(key="shop-setup"):
        title = "우리 가게 정보를 바꿀 수 있어요." if existing else "우리 가게의 안부를 시작해볼까요?"
        st.markdown('<div class="shop-eyebrow">안부가게 · 가게 설정</div>'
                    f'<h1 class="shop-title">{title}</h1>'
                    '<p class="shop-lead">사장님 이름과 가게 이름, 가게가 있는 동네를 알려주세요. '
                    '다음에 오셔도 이 브라우저에서 기억해둘게요.</p>', unsafe_allow_html=True)
        if st.session_state.get("shop_storage_error") == "invalid":
            st.info("이전에 저장한 가게 정보를 확인할 수 없어요. 아래에서 다시 입력해주세요.")
        elif st.session_state.get("shop_storage_error") == "unavailable":
            st.warning("이 브라우저에서는 정보를 기억하기 어려워요. 저장을 다시 시도하거나 이번에만 이용할 수 있어요.")
        owner_name = st.text_input("사장님 이름", key="owner_name_input", max_chars=30, placeholder="예: 홍길동")
        name = st.text_input("우리 가게 이름", key="shop_name_input", max_chars=40, placeholder="예: 정다운 슈퍼")
        st.caption("로그인 없이 이용해요. 사장님 이름과 가게 정보는 이 브라우저에만 기억해요.")
        st.markdown('<div class="setup-location-label">가게 위치</div>', unsafe_allow_html=True)
        shop_location_picker("setup")
        if st.session_state.get("shop_dong_input") not in available_dongs:
            st.session_state["shop_dong_input"] = None
        dong = st.selectbox("동 이름으로 직접 선택하기", available_dongs, index=None, key="shop_dong_input",
                            placeholder="동 이름이나 구 이름으로 검색해주세요",
                            format_func=lambda item: f"{item[0]} {dong_label(item[1])}",
                            on_change=forget_setup_position)
        st.button("← 안부가게 소개로 돌아가기", key="setup_to_intro", type="tertiary", on_click=show_intro, width="stretch")
        submitted = st.button("변경 내용 저장" if existing else "우리 가게로 시작하기 →", key="save_shop",
                              type="primary", width="stretch")
        if submitted:
            draft = validated_shop({"version": 1, "shop_name": name, "owner_name": owner_name,
                                    "gu": dong[0] if dong else None, "dong": dong[1] if dong else None},
                                   available_dongs, require_owner=True)
            if not draft:
                st.error("사장님 이름과 가게 이름, 동네를 모두 입력해주세요. 이름은 공백만으로 입력할 수 없어요.")
            else:
                queue_shop_save(draft)
                st.rerun()
        if st.session_state.get("profile_save_error"):
            st.error("브라우저에 저장하지 못했어요. 입력 내용을 확인하고 다시 저장해주세요.")
            if command.get("op") == "save" and st.button("이번에는 저장 없이 이용하기"):
                apply_shop(command["profile"])
                st.rerun()
        if existing:
            if st.button("취소하고 돌아가기", width="stretch"):
                st.session_state["editing_shop"] = False
                st.rerun()
            with st.expander("이 브라우저에서 가게 정보 지우기"):
                st.caption("기억해둔 사장님 이름과 가게 이름, 동네를 지워요. 다음에는 다시 입력할 수 있어요.")
                st.button("가게 정보 기억 해제", on_click=queue_shop_save, kwargs={"op": "clear"}, width="stretch")
    st.stop()




# ---------------------------------------------------------------- 도우미
def level(p: float) -> str:
    if p >= 75:
        return "서울에서 상위권"
    if p >= 50:
        return "서울에서 중상위권"
    if p >= 25:
        return "서울에서 중하위권"
    return "서울에서 하위권"


ELEMENTS = {
    "접근": ("store", "가까이 있는 가게",
             "독거노인 1,000명당 관계형 가게 수", lambda v: f"{v:,.0f}개"),
    "이용": ("older", "어르신 이용 비중",
             "관계형 가게 결제 건수 중 60대 이상 비중", lambda v: f"{v * 100:.1f}%"),
    "지속": ("handshake", "가게가 유지되는 정도",
             "연간 폐업률을 바탕으로 계산한 값", lambda v: f"{v * 100:.1f}%"),
}



CARE_TYPES = {
    ("HIGH", "HIGH"): ("together", "함께 돌봄형", "기관과 가게의 돌봄 기반이 모두 높은 편이에요."),
    ("HIGH", "LOW"): ("shops", "가게 보완형", "기관 기반에 비해 가게를 통한 만남의 기반을 보완할 여지가 있어요."),
    ("LOW", "HIGH"): ("connect", "기관 연결형", "가게의 일상적인 만남을 공공 돌봄과 연결하는 역할이 중요해요."),
    ("LOW", "LOW"): ("priority", "우선 보완형", "기관과 가게 양쪽의 돌봄 기반을 함께 살필 필요가 있어요."),
}


def formal_for(record):
    value = str(record.get("공식_HL", "")).strip().upper()
    return value if value in {"HIGH", "LOW"} else None


def merchant_guidance(record):
    """동 단위의 분석 결과를 상인이 실천할 수 있는 제안과 연결한다."""
    informal = str(record["비공식_HL"]).strip().upper()
    formal = formal_for(record)
    actions = {
        ("HIGH", "HIGH"): "단골의 평소 모습을 살피고, 달라지면 상담을 연결해주세요.",
        ("HIGH", "LOW"): "단골에게 먼저 안부를 묻고, 필요한 돌봄을 연결해주세요.",
        ("LOW", "HIGH"): "단골과의 만남을 이어가고, 필요할 때 돌봄 상담을 안내해주세요.",
        ("LOW", "LOW"): "먼저 안부를 묻고, 걱정된다면 돌봄 상담을 요청해주세요.",
    }
    if formal:
        tone, title, _ = CARE_TYPES[(formal, informal)]
        contexts = {
            ("HIGH", "HIGH"): "어르신이 도움받을 기관과 안부를 나눌 가게가 모두 잘 갖춰진 편이에요.",
            ("HIGH", "LOW"): "도움받을 기관은 갖춰져 있지만, 가게에서 안부를 나눌 기회는 더 필요해요.",
            ("LOW", "HIGH"): "가게에서 안부를 나눌 기회는 많지만, 기관의 도움도 더 필요한 동네예요.",
            ("LOW", "LOW"): "어르신을 도울 기관과 가게에서 안부를 나눌 기회가 모두 더 필요한 동네예요.",
        }
        context = contexts[(formal, informal)]
        return tone, title, context, actions[(formal, informal)]
    if informal == "LOW":
        return ("shops", "가게 기반 낮음", "서울의 다른 동네보다, 가게에서 어르신과 안부를 나눌 기회가 적은 편이에요.",
                "오시는 어르신께 먼저 안부를 건네주세요.")
    return ("together", "가게 기반 높음", "서울의 다른 동네보다, 가게에서 어르신과 안부를 나눌 기회가 많은 편이에요.",
            "단골 어르신이 오시면, 안부 한마디 건네주세요.")


NEIGHBORHOOD_CASES = {
    ("HIGH", "HIGH"): ("기관과 가게의 돌봄 기반이 모두 높은 편이에요", "익숙한 만남을 꾸준한 안부로 이어가요."),
    ("HIGH", "LOW"): ("기관 기반은 높고, 가게 기반은 낮은 편이에요", "가게에 오신 어르신께 먼저 안부를 건네주세요."),
    ("LOW", "HIGH"): ("가게 기반은 높고, 기관 기반은 낮은 편이에요", "가게에서의 만남을 필요한 돌봄과 연결해요."),
    ("LOW", "LOW"): ("기관과 가게의 돌봄 기반이 모두 낮은 편이에요", "작은 안부를 건네고 필요할 때 도움을 연결해요."),
}


def neighborhood_case(record, population_median):
    formal = formal_for(record)
    informal = str(record.get("비공식_HL", "")).strip().upper()
    return (formal, informal) if formal and informal in {"HIGH", "LOW"} else None


def neighborhood_cases_chart(record, population_median, is_own=True):
    selected = neighborhood_case(record, population_median)
    area_name = f"{record['구']} {dong_label(str(record['동']))}"
    badge_label = "우리 동은 여기" if is_own else area_name
    section_title = "우리 동은 어떤 경우일까요?" if is_own else f"{area_name}은 어떤 경우일까요?"
    tiles = []
    for groups, (title, tip) in NEIGHBORHOOD_CASES.items():
        current = groups == selected
        badge = (f'<div class="case-highlight"><span class="case-current {"" if is_own else "case-area-name"}">{escape(badge_label)}</span>'
                 f'<span class="case-population">혼자 사는 어르신<strong>{int(record["독거노인"]):,}<small>명</small></strong></span></div>'
                 if current else '<span class="case-other">다른 동네의 경우</span>')
        tiles.append(f'<article class="neighborhood-case {"is-current" if current else ""}" '
                     f'data-case="{groups[0]}_{groups[1]}" aria-label="{escape(title + (f" · {badge_label}" if current else ""))}">'
                     f'{badge}<h4>{title}</h4><p>{tip}</p></article>')
    return (f'<section class="neighborhood-case-section"><h3>{escape(section_title)}</h3>'
            '<p class="case-intro">기관 돌봄과 가게 돌봄의 기반을 함께 봤어요.</p>'
            f'<div class="neighborhood-cases">{"".join(tiles)}</div></section>')


def quadrant_chart(record):
    informal = str(record["비공식_HL"]).strip().upper()
    formal = formal_for(record)
    name = escape(dong_label(str(record["동"])))
    cells = []
    for formal_group, informal_group in [("HIGH", "LOW"), ("HIGH", "HIGH"), ("LOW", "LOW"), ("LOW", "HIGH")]:
        tone, title, _ = CARE_TYPES[(formal_group, informal_group)]
        selected = formal == formal_group and informal == informal_group
        marker = f'<div class="q-point" aria-label="우리 동 위치"><i></i><span>{name}</span></div>' if selected else ''
        cells.append(f'<div class="q-cell {tone} {"selected" if selected else ""}" '
                     f'data-quadrant="{formal_group}_{informal_group}">'
                     f'<strong>{title}</strong><span>기관 {"높음" if formal_group == "HIGH" else "낮음"}<br>'
                     f'가게 {"높음" if informal_group == "HIGH" else "낮음"}</span>{marker}</div>')
    if formal:
        status = f'{dong_label(str(record["동"]))}: {CARE_TYPES[(formal, informal)][1]}'
        pending = ''
    else:
        status = f'{dong_label(str(record["동"]))}: 비공식 {"높음" if informal == "HIGH" else "낮음"}, 공식 돌봄 확인 전'
        side = 'right' if informal == 'HIGH' else 'left'
        pending = (f'<div class="q-pending"><div class="q-pending-marker {side}"><i></i>'
                   f'<span>{name} · 가게 {"높음" if informal == "HIGH" else "낮음"}</span></div></div>'
                   '<p class="q-note">점은 가게 기반만 표시해요. 공식 지수가 없어 사분면 유형은 미정이에요.</p>')
    return (f'<div class="quadrant-chart" role="img" aria-label="{escape(status)}" '
            f'data-formal="{formal or "unavailable"}"><div class="q-y-title">↑ 공식 돌봄 · 보건·복지기관 기반</div>'
            '<div class="q-layout"><div class="q-y-labels"><span>높음</span><span>낮음</span></div>'
            f'<div class="q-grid {"pending" if not formal else ""}">{"".join(cells)}</div></div>'
            f'<div class="q-x-labels"><span>낮음</span><span>높음</span></div>{pending}'
            '<div class="q-x-title">비공식 돌봄 · 동네 가게 기반 →</div></div>')


@st.cache_data
def population_reference():
    with open(os.path.join("data", "sources.json"), encoding="utf-8") as file:
        metadata = json.load(file)["population"]
    reference = pd.read_csv(os.path.join("data", metadata["reference_file"]), encoding="utf-8-sig")
    return metadata, reference.set_index(["구", "동"])["독거노인"].to_dict()


def population_credit(record):
    if is_sample:
        return '<strong>화면 확인용 예시 데이터</strong><br>실제 인구 통계가 아니에요.'
    if up is not None:
        return '업로드한 분석자료의 독거노인 수<br>출처·기준 연도는 업로드 자료에서 확인해주세요.'
    try:
        metadata, reference = population_reference()
        count = reference.get((record["구"], record["동"]))
        if count is None or int(count) != int(record["독거노인"]):
            return '분석자료의 독거노인 수 · 원본 출처 대조 필요'
        return (f'<strong>{metadata["year"]}년 기준 · {escape(metadata["age"])}</strong><br>'
                f'{escape(metadata["publisher"])} 기본통계<br>'
                f'<a href="{escape(metadata["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'「{escape(metadata["title"])}」 원자료 ↗</a>')
    except (OSError, ValueError, KeyError):
        return '분석자료의 독거노인 수 · 원본 출처 대조 필요'


def go_to_page(page: str):
    st.session_state["active_page"] = page
    st.session_state["scroll_revision"] = st.session_state.get("scroll_revision", 0) + 1


def return_to_shop():
    profile = st.session_state["shop_profile"]
    st.session_state["sel"] = (profile["gu"], profile["dong"])
    go_to_page(PAGES[1])


def select_quick_dong():
    selected = st.session_state.get("quick_dong")
    if selected:
        # 빠른 검색은 별도 입력 경로다. 접힌 구·동 위젯의 변경 이벤트와 섞이지 않게 한다.
        st.session_state["sel"] = selected
        st.session_state.pop("loc_candidate", None)
        st.session_state.pop("loc_msg", None)
        go_to_page(PAGES[1])


@st.cache_resource
def focus_page():
    return components.component(
        "anbu_page_focus",
        js='''
        export default function({ data }) {
          if (!data || !data.revision) return;
          let frame, attempts = 0;
          const show = () => {
            const target = document.getElementById(data.target);
            if (target && target.getClientRects().length) {
              if (target.dataset.scrollRevision !== String(data.revision)) {
                target.dataset.scrollRevision = String(data.revision);
                target.focus({preventScroll: true});
                target.scrollIntoView({block: 'start', behavior: 'instant'});
              }
            } else if (++attempts < 60) {
              frame = requestAnimationFrame(show);
            }
          };
          frame = requestAnimationFrame(show);
          return () => cancelAnimationFrame(frame);
        }
        ''',
    )


# ---------------------------------------------------------------- 화면

# 화면 이동은 왼쪽 메뉴와 카드 안의 버튼이 같은 상태를 사용한다.
if st.session_state.get("pending_page"):
    go_to_page(st.session_state.pop("pending_page"))
legacy_pages = {"돌봄 카드": PAGES[1], "① 동 찾기": PAGES[0], "② 돌봄 카드": PAGES[1], "지수 알아보기": PAGES[2],
                "③ 지수 설명": PAGES[2], "③ 도움 안내": PAGES[3], "④ 도움 안내": PAGES[3]}
if st.session_state.get("active_page") in legacy_pages:
    st.session_state["active_page"] = legacy_pages[st.session_state["active_page"]]
with nav_slot:
    st.markdown('<div class="side-brand">안부가게</div>'
                '<p class="side-tagline"><span>사장님의 가게에서 이어지는</span><br>동네의 안부</p>', unsafe_allow_html=True)
    profile = st.session_state["shop_profile"]
    st.button("우리 동네", key="nav_1", width="stretch",
              type="primary" if st.session_state.get("active_page") != PAGES[3] else "secondary",
              on_click=return_to_shop)
    st.button("도움받기", key="nav_3", width="stretch",
              type="primary" if st.session_state.get("active_page") == PAGES[3] else "secondary",
              on_click=go_to_page, args=(PAGES[3],))
    st.markdown(f'<p class="side-shop"><strong>{escape(profile["shop_name"])}</strong><br>'
                f'{escape(profile["gu"])} {escape(dong_label(profile["dong"]))}</p>', unsafe_allow_html=True)
    st.button("가게 이름·위치 바꾸기", key="edit_shop", type="tertiary", width="stretch", on_click=edit_shop)
    st.button("다른 동네 둘러보기", key="change_dong", type="tertiary", width="stretch",
              on_click=go_to_page, args=(PAGES[0],))
    st.button("소개 화면 보기", key="show_intro", type="tertiary", width="stretch", on_click=show_intro)

st.markdown("""<style>
:root {--ink:#1C2E43;--muted:#758396;--accent:#0878CF;--line:#D6EAF7;}
.stApp,[data-testid="stAppViewContainer"] {background:#F4FAFF;color:var(--ink);}
[data-testid="stHeader"] {background:#F4FAFFEE;}
[data-testid="stAppDeployButton"] {display:none;}
[data-testid="stMainBlockContainer"] {max-width:1090px;padding:2.7rem 48px 4rem;}
[data-testid="stMain"] {overflow-x:hidden;}
[data-testid="stSidebar"] {background:#FFF;border-right:1px solid var(--line);width:min(260px,85vw)!important;}
[data-testid="stSidebarUserContent"] {padding:35px 14px;}
.side-brand {display:block;width:100%;box-sizing:border-box;margin:0;padding:0;text-align:center;
  font-size:1.5rem;line-height:1.5;font-weight:850;letter-spacing:.015em;color:var(--ink);}
.side-tagline {width:100%;box-sizing:border-box;padding:0;color:#61748C;font-size:.84rem;line-height:1.9;
  text-align:center;word-break:keep-all;margin:12px 0 30px;}
[data-testid="stSidebar"] p.side-tagline {font-size:.84rem!important;}
.side-tagline span {white-space:nowrap;letter-spacing:-.035em;}
[data-testid="stSidebar"] [data-testid="stButton"] button {min-height:50px;border:0;border-radius:12px;padding:12px 8px;justify-content:flex-start;background:transparent;color:#61748C;}
[data-testid="stSidebar"] [data-testid="stButton"] button p {font-size:.97rem;font-weight:650;text-align:left;word-break:keep-all;overflow-wrap:normal;}
[data-testid="stSidebar"] [data-testid="stButton"] button [data-testid="stMarkdownContainer"] {width:100%;text-align:left;}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {background:#E6F5FF;color:#0878CF;}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] p {color:#0878CF;}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {background:#F0F4FA;color:#304E75;}
.side-shop {padding:17px 0 4px;color:#6B7D94;font-size:.85rem;line-height:1.8;overflow-wrap:anywhere;}
.side-shop strong {color:#243C58;font-size:1rem;}
.side-note {border-top:1px solid var(--line);padding-top:25px;margin:32px 0 10px;font-size:.78rem;line-height:1.9;color:#61748C;}
[data-testid="stSidebar"] [data-testid="stExpander"] {margin-top:30px;border-color:#EDF0F5;border-radius:12px;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {font-size:.76rem;color:#61748C;}
.workspace-header > span:first-child {min-width:0;overflow-wrap:anywhere;}
.card-heading .step-label {overflow-wrap:anywhere;word-break:normal;}
.workspace-header {display:flex;align-items:center;justify-content:space-between;font-size:.82rem;color:#8592A4;padding-bottom:26px;margin-bottom:24px;border-bottom:1px solid var(--line);}
.workspace-header i {font-style:normal;color:#BBC3CE;margin:0 12px;}
.workspace-header.help-header,.workspace-header.about-header {margin-bottom:-8px;}
[data-testid="stMainBlockContainer"]:has(.workspace-header.about-header) {padding-top:3rem;}
.workspace-tag {font-size:.75rem;color:#9DA7B4;}
.st-key-workspace-pages {background:transparent;}
.st-key-workspace-pages [role="tablist"] {display:none!important;}
.st-key-workspace-pages [role="tabpanel"] {background:transparent;padding:0;border:0;}
.step-label {display:inline-block;color:#6A80AB;font-weight:750;font-size:.78rem;letter-spacing:.06em;margin-bottom:14px;}
.st-key-workspace-pages h2.find-title {font-size:2.6rem;line-height:1.4;letter-spacing:-.065em;font-weight:800;color:var(--ink);padding:0;margin:0;word-break:keep-all;}
.find-intro {font-size:1.02rem;color:#61748C;line-height:1.8;margin:17px 0 30px;word-break:keep-all;}
.st-key-workspace-pages [data-testid="stCaptionContainer"] p {color:#61748C;font-size:.83rem;line-height:1.8;word-break:keep-all;}
.st-key-workspace-pages [data-testid="stMarkdownContainer"] > p {color:#596C82;font-size:1rem;line-height:1.85;word-break:keep-all;}
.st-key-workspace-pages [data-testid="stSelectbox"] label p {font-size:.95rem;font-weight:650;color:#405670;}
.st-key-workspace-pages [data-baseweb="select"] > div {background:#FFF;border:1px solid #DDE4EF;min-height:57px;border-radius:15px;}
.st-key-workspace-pages [data-baseweb="select"] input {font-size:1rem;}
.manual-label {display:flex;align-items:center;gap:15px;color:#61748C;font-size:.82rem;margin:23px 0 12px;}
.manual-label:before,.manual-label:after {content:'';flex:1;height:1px;background:var(--line);}
.st-key-workspace-pages [data-testid="stExpander"] {background:#FFF;border:1px solid var(--line);border-radius:15px;margin-top:14px;}
.st-key-workspace-pages [data-testid="stExpander"] summary {padding:12px 15px;}
.st-key-workspace-pages [data-testid="stExpander"] summary p {font-size:.9rem;color:#6F8196;}
.st-key-workspace-pages [data-testid="stButton"] button {background:#FFF;color:#3D5775;min-height:57px;border:1px solid #DCE4EE;border-radius:15px;}
.st-key-workspace-pages [data-testid="stButton"] button p {font-size:.98rem;font-weight:700;}
.st-key-workspace-pages [data-testid="stButton"] button[kind="primary"] {background:#0878CF;border-color:#0878CF;color:#FFF;}
.st-key-workspace-pages [data-testid="stButton"] button[kind="primary"] p {color:#FFF;}
.st-key-workspace-pages [data-testid="stButton"] button[kind="primary"]:hover {background:#086BB7;}
.location-notice {padding:17px;border:1px solid #F0DFD3;background:#FFFAF5;border-radius:14px;color:#94694C;line-height:1.8;}
.action-summary {scroll-margin-top:75px;word-break:keep-all;}
.merchant-summary {word-break:keep-all;}
.card-heading {margin-bottom:24px;}
.card-heading .step-label {display:block;margin-bottom:7px;}
.st-key-workspace-pages .card-heading h1 {display:inline;color:#1D324C;letter-spacing:-.065em;font-size:2.1rem;line-height:1.55;padding:0;margin:0;}
.card-heading > span {font-size:.88rem;color:#61748C;margin-left:15px;}
.st-key-workspace-pages .card-heading h1.browse-place {display:block;font-size:clamp(1.5rem,7vw,2rem);font-weight:800;white-space:normal;word-break:keep-all;letter-spacing:-.035em;}
.shop-context {margin:18px 0 0!important;color:#526782!important;font-size:.97rem!important;line-height:1.8!important;}
.card-heading.shop-heading {padding:28px 30px;border:1px solid #CFE8FA;border-radius:22px;
  background:#FFF;}
.shop-heading .shop-welcome {display:block;font-size:.85rem;font-weight:700;color:#657B99;margin-bottom:12px;}
.st-key-workspace-pages .card-heading.shop-heading .shop-summary-title {display:block;font-size:clamp(1.9rem,3.8vw,2.8rem);
  font-weight:800;line-height:1.45;letter-spacing:-.035em;color:#1C2E43;word-break:keep-all;overflow-wrap:anywhere;}
.shop-heading .shop-name {background:linear-gradient(transparent 68%,#A9DFFF 68%);box-decoration-break:clone;
  -webkit-box-decoration-break:clone;}
.shop-heading .shop-address {display:inline-flex;align-items:center;gap:8px;margin-top:17px;padding:7px 12px;
  border:1px solid #DCE4EF;border-radius:10px;background:#FFFFFFC9;color:#526782;font-size:.92rem;line-height:1.6;}
.shop-address svg {flex-shrink:0;color:#617CA3;}
@media(min-width:0px) {.card-heading.shop-heading {padding:24px 20px;}.shop-heading .shop-address {font-size:.85rem;}}
.comparison-note {display:flex;align-items:flex-start;gap:12px;border:1px solid #E4EAF3;background:#FFF;padding:19px 21px;border-radius:16px;margin:0 0 22px;}
.comparison-dot {width:8px;height:8px;border-radius:50%;background:#7890BD;margin-top:10px;flex-shrink:0;}
.comparison-note p {color:#64778F;font-size:.97rem;line-height:1.85;margin:0;}
.merchant-hero {position:relative;overflow:hidden;border:2px solid #168BDA;border-radius:24px;background:#FFF;color:#203B58;padding:34px;margin-bottom:22px;}
.merchant-banner {background:#FFF;margin:-34px -34px 0;padding:28px 34px 0;}
.merchant-eyebrow {color:#61748C;font-size:.81rem;letter-spacing:.06em;font-weight:650;margin-bottom:18px;}
.st-key-workspace-pages .merchant-hero h2 {color:#203B58;font-size:clamp(1.7rem,3vw,2.45rem);letter-spacing:-.06em;line-height:1.48;font-weight:750;margin:0;padding:0;max-width:560px;}
.merchant-hero h2 em {font-style:normal;color:#203B58;
  background:linear-gradient(transparent 72%,#CFEFFF 72%);box-decoration-break:clone;-webkit-box-decoration-break:clone;}
.merchant-hero > p {color:#526782;font-size:.94rem;line-height:1.9;margin:23px 0 0;max-width:82%;}
.merchant-seal {position:absolute;right:28px;top:35px;border:1px solid #667F9A;border-radius:50%;width:102px;height:102px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-size:.72rem;line-height:1.7;color:#A9BDD2;transform:rotate(10deg);}
.merchant-seal b {color:#D2DEEB;font-weight:600;}
.care-step-grid {display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 23px;}
.care-step {background:#FFF;border:1px solid var(--line);border-radius:18px;padding:23px;}
.care-step-label {display:block;color:#61748C;font-weight:700;font-size:.79rem;margin-bottom:12px;}
.care-step strong {display:block;color:#304A68;line-height:1.8;font-size:1.02rem;font-weight:750;}
.care-step p {font-size:.88rem;line-height:1.9;color:#61748C;margin:12px 0 0;}
.type-badge {display:inline-block;padding:7px 12px;margin:12px 0;border-radius:25px;font-size:.85rem;background:#EDF1F8;color:#496586;font-weight:700;}
.quadrant-chart {background:#FAFBFD;border:1px solid #E6EBF2;padding:18px 14px;border-radius:18px;}
.q-y-title,.q-x-title {font-size:.8rem;font-weight:700;color:#63758B;line-height:1.7;}
.q-y-title {padding-left:30px;margin-bottom:12px;}
.q-layout {display:grid;grid-template-columns:28px 1fr;gap:3px;}
.q-y-labels {display:grid;grid-template-rows:1fr 1fr;align-items:center;font-size:.72rem;color:#91A0AD;}
.q-grid {display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:6px;min-height:240px;}
.q-cell {position:relative;border-radius:12px;padding:13px 11px;min-width:0;border:2px solid transparent;}
.q-cell strong {display:block;font-size:.85rem;line-height:1.7;}
.q-cell > span {display:block;font-size:.73rem;line-height:1.8;margin-top:5px;}
.q-cell.together {background:#E1EEE5;color:#46725B;}.q-cell.shops {background:#FCF0D4;color:#8D7136;}
.q-cell.connect {background:#F9E4D7;color:#996341;}.q-cell.priority {background:#F7E0DF;color:#A35653;}
.q-cell.selected {border-color:currentColor;min-height:150px;}
.q-point {position:absolute;bottom:10px;left:10px;display:flex;align-items:center;gap:6px;font-size:.73rem;font-weight:750;}
.q-point i,.q-pending-marker i {display:inline-block;width:13px;height:13px;border:3px solid white;border-radius:50%;box-shadow:0 0 0 1px #334F70;background:#334F70;flex-shrink:0;}
.q-x-labels {display:flex;justify-content:space-between;font-size:.72rem;color:#91A0AD;margin:7px 0 0 30px;}
.q-x-title {text-align:center;margin-top:12px;}
.q-pending {height:44px;position:relative;background:#FFF;border:1px dashed #B8C4D3;border-radius:10px;margin:10px 0 0 30px;}
.q-pending-marker {display:flex;align-items:center;gap:7px;position:absolute;height:100%;font-size:.75rem;color:#637F9D;font-weight:700;}
.q-pending-marker.left {left:10px;}.q-pending-marker.right {right:10px;}
.q-note {font-size:.78rem;color:#91A0AD;line-height:1.8;margin:11px 0 0 30px;}
.population-wrap {border:1px solid var(--line);border-radius:16px;overflow:hidden;margin:18px 0;}
.population {display:flex;align-items:center;justify-content:space-between;gap:12px;padding:23px;background:#FFF;}
.population .label {font-size:.93rem;color:#71849C;line-height:1.8;}
.population .number {color:#304E70;font-size:2rem;font-weight:800;white-space:nowrap;letter-spacing:-.04em;}
.population .number span {font-size:.9rem;margin-left:5px;}
.population-source {padding:14px 20px;background:#F4FAFF;border-top:1px solid var(--line);font-size:.78rem;line-height:1.9;color:#8F9CAD;}
.population-source a {color:#5A7AA5;}
.index-definition {color:#6B7E94;line-height:1.95;font-size:1rem;margin:22px 0;}
.selected-score {padding:25px;border-radius:18px;background:#E9F6FF;margin:20px 0;color:#6F84A2;font-size:.95rem;}
.selected-score strong {color:#355883;font-size:2.8rem;line-height:1.7;letter-spacing:-.05em;}
.selected-score span {display:block;line-height:1.9;font-size:.88rem;}
.st-key-workspace-pages .section-title {font-size:1.22rem;color:#385574;line-height:1.8;margin:18px 0 10px;padding:0;}
.st-key-workspace-pages [data-testid="stVerticalBlockBorderWrapper"]>div {border-color:var(--line);border-radius:18px;background:#FFF;}
.factor-head {display:flex;align-items:center;gap:12px;}.factor-number {background:#EDF2FB;color:#7088AE;font-weight:700;padding:8px 11px;border-radius:10px;font-size:.83rem;}
.factor-heading {color:#4E6683;font-size:1.05rem;font-weight:700;}.factor-value {font-size:1.7rem;font-weight:800;color:#365780;margin:15px 0 7px;}
.factor-desc,.factor-level {color:#61748C;font-size:.9rem;line-height:1.9;}.factor-level {font-size:.82rem;color:#6986AF;}
.st-key-workspace-pages [role="progressbar"] {height:6px;}.st-key-workspace-pages [role="progressbar"]>div {background:#7293C2;}
.formal-domain {display:flex;align-items:baseline;gap:16px;padding:16px 3px;border-bottom:1px solid var(--line);line-height:1.85;word-break:keep-all;}
.formal-domain strong {min-width:67px;color:#4E698A;font-size:.97rem;}.formal-domain span {font-size:.9rem;color:#61748C;}
.st-key-workspace-pages [data-testid="stRadio"] [role="radiogroup"] {gap:10px;width:100%;}
.st-key-workspace-pages [data-testid="stRadio"] [role="radiogroup"]>div {width:100%;}
.st-key-workspace-pages [data-testid="stRadioOption"] {min-height:57px;width:100%;padding:15px 18px;background:#FFF;border:1px solid var(--line);border-radius:15px;box-sizing:border-box;}
.st-key-workspace-pages [data-testid="stRadioOption"]:has(input:checked) {background:#EDF2FC;border-color:#7590BC;}
.st-key-workspace-pages [data-testid="stRadioOption"] p {color:#526C8B;font-size:.95rem;font-weight:650;}
.help-panel {background:#E9F6FF;border-radius:20px;padding:25px;margin:18px 0;word-break:keep-all;}
.help-panel.emergency {background:#FFF0EA;}.help-kicker {color:#7088AA;font-size:.8rem;font-weight:750;}
.st-key-workspace-pages .help-panel h3 {font-size:1.35rem;line-height:1.65;color:#355478;margin:10px 0 15px;padding:0;}
.help-panel.emergency h3 {color:#A94D3C;}.help-panel p {color:#7186A0;font-size:.98rem;line-height:1.9;margin:0 0 20px;}
.contact-button {display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:57px;padding:16px 18px;box-sizing:border-box;background:#2D4B70;border-radius:13px;color:#FFF!important;text-decoration:none!important;font-size:.95rem;font-weight:750;}
.contact-button strong {font-size:1.12rem;white-space:nowrap;}.contact-button:hover {background:#41638D;}
.contact-button:focus-visible {outline:3px solid #658CE2;outline-offset:4px;}.emergency .contact-button {background:#B75D48;}
.contact-hours {font-size:.8rem;color:#61748C;line-height:1.9;margin-top:13px;}
.phone-script {background:#F3F6FC;border-left:3px solid #9AAED1;border-radius:0 12px 12px 0;padding:18px;color:#647C9B;line-height:1.9;font-size:.97rem;}
.help-source {font-size:.76rem;line-height:1.9;color:#9AA6B5;padding:15px 0;}.help-source a {color:#7891B4;}
[id="find-dong"],[id="help-start"],[id="index-start"] {scroll-margin-top:75px;}
#help-start {margin-top:-24px;padding-bottom:18px;}
.st-key-page-2 #index-start {margin-top:-24px;}
[tabindex="-1"]:focus {outline:none;}
.st-key-workspace-pages h1,.st-key-workspace-pages h2,.st-key-workspace-pages h3,.st-key-workspace-pages p {word-break:keep-all;overflow-wrap:break-word;}
.merchant-hero .care-step-grid {margin:24px 0 0;}
.merchant-hero .care-step {background:#E9F6FF;border:1px solid #CFDAE8;}
.merchant-hero .care-step strong {color:#304A68;}
.merchant-hero .care-step p {color:#61748C;}
.merchant-hero .care-step-label {color:#4F6683;}
@media(max-width:1100px) {.merchant-seal {display:none;}.merchant-hero>p {max-width:100%;}}
@media(min-width:0px) {
 [data-testid="stMainBlockContainer"] {padding:3.2rem 20px 3rem;}.workspace-tag {display:none;}
 .workspace-header > span:first-child {min-width:0;overflow-wrap:anywhere;}
.card-heading .step-label {overflow-wrap:anywhere;word-break:normal;}
.workspace-header {margin-bottom:22px;padding-bottom:20px;}.st-key-workspace-pages h2.find-title {font-size:2rem;}
 .merchant-hero {padding:27px 24px;border-radius:20px;}.st-key-workspace-pages .merchant-hero h2 {font-size:1.95rem;}
 .care-step-grid {grid-template-columns:1fr;gap:12px;}.care-step {padding:21px;}
 .comparison-note {padding:17px;}.comparison-note p {font-size:.93rem;}.card-heading>span {display:block;margin:5px 0 0;}
 .st-key-workspace-pages .card-heading h1 {font-size:1.9rem;}.contact-button {padding:15px 12px;font-size:.88rem;}.contact-button strong {font-size:1rem;}
 .q-cell {padding:11px 8px;}.q-cell strong {font-size:.78rem;}
}

.score-overview {background:#fff;border:1px solid #d6eaf7;border-radius:20px;padding:20px;margin:18px 0;word-break:keep-all;}
.score-overview h3 {font-size:1.18rem;color:#203b58;margin:0 0 6px;padding:0;}
.score-overview .score-explain {font-size:.86rem;color:#61748c;line-height:1.7;margin:0 0 12px;}
.score-row {display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 0;border-top:1px solid #e2edf5;}
.score-row-label {font-size:.96rem;font-weight:750;color:#304e70;line-height:1.5;}
.score-row-label small {display:block;font-size:.75rem;font-weight:500;color:#71849c;}
.score-row-value {text-align:right;white-space:nowrap;color:#203b58;font-weight:800;font-size:1.14rem;}
.score-row-value small {display:block;font-weight:700;font-size:.8rem;color:#0878cf;}
.score-row.total .score-row-value {color:#0878cf;font-size:1.35rem;}
.neighborhood-case-section {margin:27px 0;word-break:keep-all;}
.st-key-workspace-pages .neighborhood-case-section h3 {font-size:1.23rem;line-height:1.7;margin:0 0 6px;padding:0;color:#304A68;}
.st-key-workspace-pages .case-intro {color:#6E8095;font-size:clamp(.62rem,3vw,.8rem)!important;
  letter-spacing:-.035em;line-height:1.8;margin:0 0 17px;white-space:nowrap!important;text-wrap:nowrap!important;}
.neighborhood-cases {display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.neighborhood-case {position:relative;background:#FFF;border:1px solid #E0E6EF;border-radius:17px;padding:18px;}
.neighborhood-case.is-current {background:#E9F6FF;border:2px solid #168BDA;padding:17px;}
.case-current,.case-other {display:inline-block;font-size:.74rem;line-height:1.8;margin-bottom:10px;}
.case-current {color:#FFF;background:#29435F;border-radius:20px;padding:3px 10px;font-weight:750;}
.case-other {color:#7B899C;padding:3px 0;}
.st-key-workspace-pages .neighborhood-case h4 {font-size:.99rem;line-height:1.75;color:#405B7B;margin:0 0 9px;padding:0;}
.neighborhood-case.is-current h4 {color:#203B58;}
.neighborhood-case p {font-size:.84rem;line-height:1.8;color:#6D8097;margin:0;}
.st-key-resident-center {background:#FFF;border:2px solid #168BDA;border-radius:20px;padding:25px;margin:18px 0 20px;box-shadow:0 8px 22px #233C5808;}
.service-kicker {font-size:.77rem;font-weight:750;color:#7188A7;letter-spacing:.04em;margin-bottom:9px;}
.st-key-workspace-pages .service-heading {font-size:1.5rem;line-height:1.7;color:#2B4766;margin:0 0 10px;padding:0;}
.center-contact {background:#F2F5FA;border-radius:14px;padding:20px;margin:13px 0 0;word-break:keep-all;}
.st-key-workspace-pages .center-contact h4 {font-size:1.3rem;color:#294761;line-height:1.6;margin:0 0 10px;padding:0;}
.center-contact p,.nearby-service p {font-size:.9rem;line-height:1.85;color:#637A94;margin:0 0 15px;}
.service-map-links {display:flex;flex-wrap:wrap;gap:10px 17px;margin-top:13px;}
.service-map-links a {color:#496D99;font-size:.84rem;font-weight:650;text-underline-offset:4px;}
.nearby-heading {border-top:1px solid #E1E7F0;margin-top:20px;padding-top:29px;}
.nearby-service {background:#FFF;border:1px solid #DCE4EE;border-radius:17px;min-height:230px;box-sizing:border-box;padding:22px;margin:4px 0 12px;word-break:keep-all;}
.st-key-workspace-pages .nearby-service h4 {font-size:1.09rem;line-height:1.7;color:#304F73;padding:0;margin:0 0 12px;}
.service-phone {display:inline-block;color:#294A72!important;font-size:1.12rem;font-weight:750;text-decoration:none!important;}
.service-phone:focus-visible {outline:3px solid #6C8FB9;outline-offset:4px;}
@media(min-width:0px) {.neighborhood-cases {gap:9px;}.neighborhood-case {padding:13px;}.neighborhood-case.is-current {padding:12px;}
 .st-key-workspace-pages .neighborhood-case h4 {font-size:.91rem;}.neighborhood-case p {font-size:.79rem;}.st-key-resident-center {padding:21px;}}

.help-jumps {display:flex;flex-wrap:wrap;gap:10px;margin:9px 0 2px;}
.help-jumps a {flex:1;min-width:180px;text-align:center;padding:15px;background:#EAF0F8;border:1px solid #D6E0EE;border-radius:13px;color:#355474;font-size:.94rem;font-weight:750;text-decoration:none;}
.help-jumps a:hover {background:#DFE8F5;}.help-jumps a:focus-visible {outline:3px solid #7B98BC;outline-offset:3px;}
#resident-center-start,#nearby-services-start {scroll-margin-top:78px;}


/* 선택한 동네를 먼저 알아볼 수 있게, 인구 수를 같은 머리줄에 둔다. */
.neighborhood-case.is-current {border:2px solid #168BDA;padding:16px;box-shadow:0 0 0 3px #DEF1FF;}
.case-highlight {display:flex;align-items:center;justify-content:space-between;gap:10px;background:#0878CF;
    margin:-16px -16px 18px;padding:15px 16px;border-radius:13px 13px 0 0;}
.case-highlight .case-current {display:flex;align-items:center;gap:7px;background:none;color:#FFF;
    font-size:.9rem;font-weight:800;line-height:1.7;margin:0;padding:0;white-space:normal;min-width:0;word-break:keep-all;}
.case-check {display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:#FFF;
    color:#0878CF;font-size:.97rem;font-style:normal;flex-shrink:0;}
.case-population {color:#CBD7E5;font-size:.68rem;line-height:1.7;text-align:right;white-space:nowrap;}
.case-population strong {display:block;color:#FFF;font-size:1.55rem;font-weight:800;line-height:1.4;letter-spacing:-.04em;}
.case-population small {font-size:.8rem;margin-left:3px;}
.st-key-workspace-pages .neighborhood-case.is-current h4 {font-size:1.04rem;font-weight:800;}
.st-key-nearby-services {background:#FFF;border:2px solid #168BDA;border-radius:20px;padding:25px;
    margin:18px 0 20px;box-shadow:0 8px 22px #233C5808;}
.st-key-nearby-services .nearby-heading {border:0;margin:0;padding:0;}
.st-key-nearby-services .nearby-service {background:#F8FAFD;}
@media(min-width:0px) {.neighborhood-case.is-current {padding:12px;}
    .case-highlight {margin:-12px -12px 14px;padding:12px;flex-wrap:wrap;gap:9px;}
    .case-highlight .case-current {font-size:.83rem;}.case-population {text-align:left;}
    .case-population strong {font-size:1.35rem;}.st-key-nearby-services {padding:21px;}}

/* Mobile is the default review surface: keep reading width and alignment consistent. */
@media(min-width:0px) {
  [data-testid="stMainBlockContainer"] {padding:4.5rem 18px 2rem;}
  .st-key-workspace-pages {min-width:0;}
  .st-key-workspace-pages h1,.st-key-workspace-pages h2,.st-key-workspace-pages h3,
  .st-key-workspace-pages h4 {word-break:keep-all;overflow-wrap:break-word;text-wrap:balance;}
  .st-key-workspace-pages p {text-wrap:pretty;}
  .card-heading.shop-heading {display:flex;flex-direction:column;align-items:flex-start;gap:12px;padding:24px 22px;}
  .shop-heading .shop-welcome {margin:0;line-height:1.7;}
  .st-key-workspace-pages .card-heading.shop-heading .shop-summary-title {width:100%;margin:0;font-size:1.9rem;line-height:1.45;letter-spacing:-.025em;text-wrap:wrap;}
  .shop-heading .shop-name {display:inline;overflow-wrap:anywhere;}
  .shop-heading .shop-title-suffix {display:block;margin-top:4px;font-size:1.55rem;color:#4F6683;}
  .shop-heading .shop-address {margin:2px 0 0;font-size:.9rem;padding:7px 10px;}
  .shop-heading .shop-context {margin:3px 0 0!important;font-size:1rem!important;}
  .st-key-workspace-pages h2.find-title {font-size:1.85rem;line-height:1.5;letter-spacing:-.025em;}
  .neighborhood-case-section {margin:24px 0;}
  .neighborhood-cases {grid-template-columns:minmax(0,1fr);gap:12px;}
  .neighborhood-case {padding:18px;min-width:0;}
  .neighborhood-case.is-current {order:-1;padding:17px;}
  .st-key-workspace-pages .neighborhood-case h4 {font-size:1.05rem;line-height:1.65;text-wrap:pretty;}
  .neighborhood-case p {font-size:.95rem;line-height:1.8;}
  .case-highlight {margin:-17px -17px 17px;padding:15px 17px;flex-wrap:nowrap;gap:12px;}
  .case-highlight .case-current {font-size:.95rem;}
  .case-highlight .case-current.case-area-name {font-size:1.18rem;line-height:1.4;}
  .case-population {text-align:right;font-size:.74rem;}
  .case-population strong {font-size:1.55rem;}
  .merchant-hero {padding:26px 22px;}
  .merchant-banner {margin:-26px -22px 0;padding:23px 22px 0;}
  .st-key-workspace-pages .merchant-hero h2 {font-size:1.65rem;line-height:1.6;letter-spacing:-.025em;text-wrap:pretty;}
  .merchant-role {white-space:nowrap;}
  .merchant-hero>p {font-size:1rem;line-height:1.85;max-width:100%;}
  .merchant-hero .care-step-grid {margin-top:20px;gap:12px;}
  .care-step {padding:18px;}
  .care-step-label {font-size:.9rem;}
  .care-step strong,.care-step p {font-size:1rem;line-height:1.8;}
  .st-key-workspace-pages [data-testid="stButton"] button {padding:12px 16px;min-height:54px;}
  .st-key-workspace-pages [data-testid="stButton"] button p {line-height:1.6;word-break:keep-all;text-wrap:pretty;}
  .st-key-resident-center,.st-key-nearby-services {padding:20px;border-radius:20px;}
  .center-contact,.nearby-service {padding:18px;min-height:0;}
  .st-key-workspace-pages .service-heading {font-size:1.4rem;line-height:1.6;}
  .center-contact p,.nearby-service p {font-size:1rem;overflow-wrap:anywhere;}
  .help-jumps {display:grid;grid-template-columns:minmax(0,1fr);gap:10px;}
  .help-jumps a {min-width:0;padding:13px 12px;}
  .service-map-links {display:grid;grid-template-columns:minmax(0,1fr);gap:9px;}
  .service-map-links a {display:block;padding:11px 12px;background:#EAF0F8;border-radius:10px;text-align:center;line-height:1.7;}
  .st-key-nearby-services [data-testid="stHorizontalBlock"] {flex-direction:column;gap:0;}
  .st-key-nearby-services [data-testid="stColumn"] {width:100%!important;flex:1 1 auto!important;min-width:0!important;}
  .formal-domain {flex-direction:column;align-items:flex-start;gap:7px;}
  .factor-head {align-items:flex-start;}
}
@media(max-width:360px) {
  .case-highlight {flex-wrap:wrap;}
  .case-population {text-align:left;}
  .merchant-role {white-space:normal;}
  .contact-button {flex-direction:column;align-items:flex-start;gap:7px;}
}
@media(prefers-reduced-motion:reduce) {* {scroll-behavior:auto!important;animation:none!important;transition:none!important;}}

</style>""", unsafe_allow_html=True)
if st.session_state.pop("entry_pending", False):
    st.markdown("""<style>
    @keyframes workspace-arrive { from {opacity:0;filter:blur(10px);transform:translateY(12px);}
      to {opacity:1;filter:blur(0);transform:translateY(0);} }
    [data-testid="stMainBlockContainer"] {animation:workspace-arrive .65s ease-out both;}
    @media(prefers-reduced-motion:reduce) { [data-testid="stMainBlockContainer"] {animation:none;} }
    </style>""", unsafe_allow_html=True)

hero = st.container()  # 동이 정해진 뒤 채움 (제목 + 동 이름)

current_page = st.session_state.get("active_page", PAGES[0])
hidden_pages = [f'.st-key-page-{i}' for i, page in enumerate(PAGES) if page != current_page]
st.markdown('<style>' + ','.join(hidden_pages) + '{display:none!important;}</style>', unsafe_allow_html=True)
with st.container(key="workspace-pages"):
    tab1, tab2, tab3, tab4 = [st.container(key=f"page-{i}") for i in range(4)]

with tab1:
    if current_page == PAGES[0]:
        st.markdown('<div id="find-dong" tabindex="-1"><div class="step-label">다른 동네 둘러보기</div>'
                    '<h2 class="find-title">어느 동네가 궁금하세요?</h2></div>'
                    '<p class="find-intro">다른 동을 살펴봐도 등록한 가게 정보는 그대로예요.</p>',
                    unsafe_allow_html=True)
        if st.session_state.get("quick_dong") not in available_dongs:
            st.session_state.pop("quick_dong", None)
        st.selectbox("바로 검색하기", available_dongs, index=None,
                     placeholder="예: 보라매동, 관악구", key="quick_dong",
                     format_func=lambda item: f"{item[0]} {dong_label(item[1])}",
                     on_change=select_quick_dong)
        st.caption("가게 이름과 위치는 왼쪽의 ‘가게 이름·위치 바꾸기’에서 함께 수정해요.")
        st.button("우리 가게 동네로 돌아가기", key="browse_to_home", on_click=return_to_shop, width="stretch")

selection = st.session_state.get("sel")
matches = df[(df["구"] == selection[0]) & (df["동"] == selection[1])] if selection else df.iloc[:0]
row = matches.iloc[0] if len(matches) else None
place = f"{row['구']} {dong_label(row['동'])}" if row is not None else "가게가 있는 동을 선택해주세요"

current_page = st.session_state.get("active_page", PAGES[0])
profile = st.session_state["shop_profile"]
shop_title = f'{profile["shop_name"]}의 동네 안부'
display_page = {PAGES[0]: "다른 동네 둘러보기", PAGES[1]: "우리 동네", PAGES[2]: "안부가게 알아보기", PAGES[3]: "도움받기"}[current_page]
header_class = "help-header" if current_page == PAGES[3] else ("about-header" if current_page == PAGES[2] else "")
hero.markdown(f'<div class="workspace-header {header_class}"><span>안부가게 <i>/</i> {escape(display_page)}</span>' 
              '<span class="workspace-tag">우리 동네를 살피는 작은 관심</span></div>', unsafe_allow_html=True)

targets = {PAGES[0]: "find-dong", PAGES[1]: "care-summary", PAGES[2]: "index-start", PAGES[3]: "help-start"}
focus_page()(key="anbu_page_focus", data={
    "target": targets.get(st.session_state.get("active_page"), "find-dong"),
    "revision": f"{st.session_state.get('scroll_revision', 0)}-{st.session_state.get('active_page')}"
    if st.session_state.get("scroll_revision") else None,
})

if row is None:
    for page_number, page in enumerate((tab2, tab3, tab4)):
        with page:
            st.info("먼저 가게가 있는 동을 선택해주세요.")
            st.button("우리 동 찾으러 가기", key=f"find_{page_number}",
                      on_click=go_to_page, args=(PAGES[0],), width="stretch")
    st.stop()

formal_level = formal_for(row)
hl = str(row["비공식_HL"]).strip().upper()
population_median = df.loc[df["독거노인"] >= 0, "독거노인"].median()

with tab2:
    tone, type_label, context, action = merchant_guidance(row)
    dong_alias = dong_label(str(row['동']))[len(str(row['동'])):].strip(' ()')
    area_note = str(row['구']) + (f" · {dong_alias}" if dong_alias else "")
    role_reason = ("만날 기회가 적은 동네일수록, 한 번 들렀을 때 나누는 안부가 더 소중해요."
                   if hl == "LOW" else "자주 마주치는 사장님이기에, 평소와 다른 모습을 알아챌 수 있어요.")
    cases_html = neighborhood_cases_chart(row, population_median, selection == (profile["gu"], profile["dong"]))
    if selection == (profile["gu"], profile["dong"]):
        owner = profile.get("owner_name", "")
        owner_label = (owner if owner.endswith("사장님") else f"{owner} 사장님") if owner else "사장님"
        heading_html = (f'<div class="card-heading shop-heading"><span class="shop-welcome">{escape(owner_label)}을 위한 우리 동네 안내</span>'
                        f'<div class="shop-summary-title" role="heading" aria-level="1"><span class="shop-name">{escape(profile["shop_name"])}의</span> <span class="shop-title-suffix">동네 안부</span></div>'
                        '<div class="shop-address"><svg aria-hidden="true" width="16" height="18" viewBox="0 0 24 24" fill="none">'
                        '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" stroke="currentColor" stroke-width="1.7"/>'
                        '<circle cx="12" cy="10" r="2.5" stroke="currentColor" stroke-width="1.7"/></svg>'
                        f'{escape(str(row["구"]))} · {escape(dong_label(str(row["동"])))}</div>'
                        '</div>')
    else:
        heading_html = (f'<div class="card-heading"><div class="step-label">다른 동네 둘러보기</div>'
                        f'<h1 class="browse-place">{escape(str(row["구"]))} {escape(dong_label(str(row["동"])))}</h1>'
                        '</div>')
    def score_text(value):
        try:
            value = float(value)
            return f"{value:.1f}점" if np.isfinite(value) else "자료 없음"
        except (TypeError, ValueError):
            return "자료 없음"
    def level_text(value):
        return {"HIGH": "높은 편", "LOW": "낮은 편"}.get(value, "구분 확인 중")
    scores_html = f'''<section class="score-overview" aria-label="우리 동네 돌봄 지수">
        <h3>우리 동네 돌봄 지수</h3>
        <p class="score-explain">서울의 다른 동네와 비교한 돌봄 기반이에요.</p>
        <div class="score-row"><div class="score-row-label">공식 돌봄 지수<small>병원·복지기관 등</small></div>
            <div class="score-row-value">{score_text(row.get("공식지수_공간"))}<small>{level_text(formal_level)}</small></div></div>
        <div class="score-row"><div class="score-row-label">비공식 돌봄 지수<small>동네 가게를 통한 만남</small></div>
            <div class="score-row-value">{score_text(row.get("비공식지수"))}<small>{level_text(hl)}</small></div></div>
        <div class="score-row total"><div class="score-row-label">합성 돌봄 지수<small>기관과 가게 기반을 함께</small></div>
            <div class="score-row-value">{score_text(row.get("최종돌봄지수_합성"))}</div></div>
        </section>'''
    st.markdown(f'''<section id="care-summary" class="action-summary" tabindex="-1">
        {heading_html}{scores_html}{cases_html}</section>''', unsafe_allow_html=True)
    if pd.notna(row.get("최종순위")):
        st.info(f"공간 분석에서 돌봄 여건이 낮게 모인 47개 동 중 우선순위 {int(row['최종순위'])}위예요.")
        st.caption("우선순위는 47개 분석 대상 안에서의 순위이며, 개별 어르신의 위험도를 뜻하지 않아요.")
    if selection == (profile["gu"], profile["dong"]):
        st.button("안부가게 알아보기 →", key="to_index", type="primary", width="stretch",
                  on_click=go_to_page, args=(PAGES[2],))
    st.markdown(f'''<section class="merchant-summary">
        <div class="merchant-hero"><div class="merchant-banner"><div class="merchant-eyebrow">사장님이 있어 달라질 수 있는 일</div>
        <h2>사장님의 가게는 <span class="merchant-role"><em>안부를 묻는 이웃</em>이</span> 될 수 있어요.</h2></div>
        <p>{role_reason}</p>
        <div class="care-step-grid"><div class="care-step"><span class="care-step-label">가게에 오셨을 때</span>
        <strong>{escape(action)}</strong><p>“식사는 하셨어요?” 익숙한 인사에 오늘의 안부를 더해요.</p></div>
        <div class="care-step"><span class="care-step-label">평소와 달라 걱정될 때</span>
        <strong>그냥 지나치지 말고, 상담할 곳을 찾아주세요.</strong>
        <p>늘 오시던 분이 안 보이거나 도움이 필요해 보일 때 함께 연결해요.</p></div></div></div>
        </section>''', unsafe_allow_html=True)
    st.button("걱정되는 어르신, 도움받을 곳 보기 →", key="to_help", type="primary", width="stretch",
              on_click=go_to_page, args=(PAGES[3],))


with tab3:
    render_about_overview()
    with st.container(key="about-informal-card"):
        st.markdown('<h2 class="find-title">비공식 돌봄 지수</h2>', unsafe_allow_html=True)
        render_informal_definition()
        st.markdown(f'<div class="index-score selected-score">{escape(place)}의 비공식 돌봄 지수<br>'
                    f'<strong>{row["비공식지수"]:.1f}</strong> / 100점<br>'
                    '<span>높을수록 가게를 통한 일상적인 만남의 기반이 상대적으로 좋은 편이에요.</span></div>',
                    unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">이 세 가지로 계산했어요</h3>', unsafe_allow_html=True)
        st.write("어르신이 일상에서 방문하고 상인과 마주칠 수 있는 업종의 가게를 살펴봤어요.")
        for factor_number, (key, (ic, title, desc, fmt)) in enumerate(ELEMENTS.items(), 1):
            percentile = row[key + "_pct"]
            with st.container(border=True):
                st.markdown(f'<div class="factor-head"><span class="factor-number">0{factor_number}</span><div class="factor-heading">{title}</div></div>'
                            f'<div class="factor-value">{fmt(row[key])}</div>'
                            f'<div class="factor-desc">{desc}</div>'
                            f'<div class="factor-level">{level(percentile)}</div>', unsafe_allow_html=True)
                st.progress(int(percentile) / 100)
        render_index_method()
    with st.container(key="about-neighborhood-card"):
        st.markdown('<h3 class="section-title">우리 동네를 어떻게 나눴나요?</h3>', unsafe_allow_html=True)
        st.write("가게가 얼마나 가까이 있는지, 어르신이 얼마나 이용하는지, "
                 "가게가 꾸준히 운영되는지를 함께 살펴봤어요.")
        st.caption("‘안부를 나눌 기회’는 이 자료를 쉽게 풀어쓴 말이에요. "
                   "실제 대화 횟수나 개별 어르신의 상태를 조사한 결과는 아니에요.")
        st.write(f"앞의 네 가지 동네 모습은 분석 가능한 {len(df):,}개 동의 공식 돌봄 지수와 비공식 돌봄 지수를 함께 나눈 결과예요.")
        st.caption("공식은 공간 반영 지수, 비공식은 가게 기반 지수를 사용해요. 두 지수의 높고 낮음은 제공된 최종 결과표의 구분을 따릅니다.")
        st.caption("이는 동네 상황을 이해하기 위한 구분이며, 개별 어르신의 위험도를 판정한 결과는 아니에요. "
                   "어르신 수가 적다는 이유로 안부 확인이 필요 없다는 뜻도 아니에요.")
        st.markdown("**기관과 가게를 함께 보는 연구용 분류**")
        st.markdown(f'<div class="type-badge {tone}">{escape(type_label)}</div>', unsafe_allow_html=True)
        st.markdown(quadrant_chart(row), unsafe_allow_html=True)
        st.caption("가로는 가게 기반, 세로는 보건·복지기관 기반이에요. "
                   "각 지수의 중앙값으로 높음·낮음을 나눈 유형도예요.")
        if not formal_level:
            st.caption("현재 공식 돌봄 지수 자료가 없어 기관 기반과 사분면 유형은 확정하지 않았어요.")
        st.markdown(f'''<section class="population-wrap" aria-label="우리 동 독거노인 수와 출처">
            <div class="population"><div class="label">우리 동의<br>홀로 사는 어르신</div>
            <div class="number">{int(row['독거노인']):,}<span>명</span></div></div>
            <div class="population-source">{population_credit(row)}</div></section>''', unsafe_allow_html=True)
    render_formal_explainer()
    st.button("우리 동네로 돌아가기", key="back_to_card", type="primary", width="stretch",
              on_click=go_to_page, args=(PAGES[1],))

with tab4:
    st.markdown('<div id="help-start" tabindex="-1"><div class="step-label">걱정될 때, 함께 연결해요</div>'
                '<h2 class="find-title">어떤 도움이 필요하세요?</h2></div>', unsafe_allow_html=True)
    help_choices = ["안부 확인·생활 도움이 필요해요", "지금 위급해 보여요"]
    if st.session_state.get("help_situation") in {"단골 어르신이 안 보여요", "식사·외출 도움이 필요해요"}:
        st.session_state["help_situation"] = help_choices[0]
    situation = st.radio("지금 상황을 골라주세요", help_choices, key="help_situation", width="stretch",
                         label_visibility="collapsed")
    if situation != "지금 위급해 보여요":
        st.markdown('<div class="help-jumps"><a href="#resident-center-start">우리 동 주민센터 ↓</a>'
                    '<a href="#nearby-services-start">가까운 병원·보건소 ↓</a></div>', unsafe_allow_html=True)
    my_loc = st.session_state.get("my_loc")
    loc_here = bool(my_loc) and my_loc[2:4] == (row["구"], row["동"])
    if situation != "지금 위급해 보여요":
        with st.container(key="resident-center"):
            st.markdown('<div id="resident-center-start"><div class="service-kicker">먼저 상담할 곳</div>'
                        '<h3 class="service-heading">우리 동 주민센터</h3></div>', unsafe_allow_html=True)
            st.caption("어르신의 주소지가 다른 동이면 담당 센터를 다시 안내받으세요.")
            if os.path.exists(CENTER_NAME):
                centers = load_centers(CENTER_NAME)
                centers = centers[(centers["구"] == row["구"]) & (centers["동"] == row["동"])]
                if len(centers) > 1 and loc_here:
                    mine = centers[centers["원래동"] == norm_dong(my_loc[4])]
                    if len(mine) == 1:
                        centers = mine
                if len(centers) > 1:
                    st.caption("가게 위치에 따라 담당 주민센터가 달라요.")
                if centers.empty:
                    st.caption("센터 정보를 찾지 못했어요. 안심돌봄120에 담당 센터를 문의해주세요.")
                for _, c in centers.iterrows():
                    q = quote(f"{row['구']} {c['이름']}")
                    st.markdown(f'<article class="center-contact"><h4>{escape(str(c["이름"]))}</h4>'
                                f'<p>{escape(str(c["주소"]))}</p><div class="service-map-links">'
                                f'<a href="https://map.kakao.com/?q={q}" target="_blank" rel="noopener noreferrer">카카오맵에서 위치 보기 ↗</a>'
                                f'<a href="https://map.naver.com/p/search/{q}" target="_blank" rel="noopener noreferrer">네이버지도에서 위치 보기 ↗</a>'
                                '</div></article>', unsafe_allow_html=True)
            else:
                st.caption("센터 위치 자료가 없어요. 안심돌봄120에 담당 센터를 문의해주세요.")


    consultation = '<a class="contact-button" href="tel:16680120" aria-label="안심돌봄120, 1668-0120 전화">안심돌봄120 상담 <strong>1668-0120 ↗</strong></a>'
    hours = '<div class="contact-hours">평일 09:00–18:00 · 야간·공휴일 접수는 익일 콜백 안내<br>휴대폰에서는 번호를 눌러 전화 앱을 열 수 있어요.</div>'

    if situation == "지금 위급해 보여요":
        st.markdown('<section class="help-panel emergency"><div class="help-kicker">응급 상황</div>'
                    '<h3>의식이나 호흡에 이상이 있다면,<br>바로 119에 연락하세요.</h3>'
                    '<p>현재 위치와 눈앞의 상태를 알리고, 119 상담원의 지시에 따라주세요.</p>'
                    '<a class="contact-button" href="tel:119" aria-label="119 긴급 신고 전화">119 긴급 신고 <strong>119 ↗</strong></a>'
                    '<div class="contact-hours">전화 버튼은 전화 앱을 열어요. 이 앱이 대신 신고하지는 않아요.</div></section>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<section class="help-panel"><div class="help-kicker">안부 확인·생활 돌봄</div>'
                    '<h3>주민센터에 안부와 생활 도움을 상담해요.</h3>'
                    '<p>평소와 달리 보이지 않거나 식사·외출에 도움이 필요하다면 상담을 요청해요. '
                    '어디에 연락할지 모르겠다면 안심돌봄120에서 안내받을 수 있어요. '
                    '돌봄 서비스의 대상과 비용은 상황·소득에 따라 달라요.</p>' + consultation + hours + '</section>',
                    unsafe_allow_html=True)

    with st.container(key="nearby-services"):
        st.markdown('<section id="nearby-services-start" class="nearby-heading"><div class="service-kicker">가까이에서 도움받을 곳</div>'
                    '<h3 class="service-heading">가까운 병원·보건소</h3></section>', unsafe_allow_html=True)
        st.caption("진료 여부와 운영시간은 방문 전에 확인해주세요. 응급 상황은 119로 연락하세요.")
        if current_page == PAGES[3]:
            if shop_location_picker("help", expected_dong=(row["구"], row["동"])):
                st.rerun()
        position = st.session_state.get("my_loc")
        loc_here = bool(position) and tuple(position[2:4]) == (row["구"], row["동"])
        ref = position[:2] if loc_here else None
        ref_note = "📍 확인한 가게 위치 기준 · 직선거리"
        if loc_here and st.session_state.get("location_accuracy") is not None:
            ref_note += f" · 위치 오차 약 {st.session_state['location_accuracy']:,.0f}m"

        if not os.path.exists(HOSP_NAME):
            st.caption(f"`{HOSP_NAME}` 파일이 있으면 가까운 병원 3곳을 보여드려요.")
        elif ref is None:
            st.info("가게 위치를 확인하면 그곳에서 가까운 병원 3곳과 보건소 1곳을 보여드려요.")
            st.caption("동 이름만으로는 가게에서의 거리를 알 수 없어요. 위의 위치 버튼을 가게에서 눌러주세요.")
            st.button("가게 이름·위치 설정하기", key="help_edit_shop", on_click=edit_shop, width="stretch")
        else:
            st.caption(ref_note)
            def hosp_card(h):
                name = str(h["기관명"])
                kakao = f"https://map.kakao.com/link/map/{quote(name)},{h['병원위도']},{h['병원경도']}"
                naver = f"https://map.naver.com/p/search/{quote(name + ' ' + h['주소'].split(' (')[0].split(',')[0])}"
                tel = str(h["대표전화1"]) if pd.notna(h["대표전화1"]) else "번호 정보 없음"
                number = re.sub(r"[^0-9+]", "", tel)
                valid_phone = re.fullmatch(r"\+?\d[\d -]{6,20}", tel.strip()) and re.fullmatch(r"\+?\d{8,15}", number)
                tel_html = f'<a class="service-phone" href="tel:{number}">{escape(tel)}</a>' if valid_phone else f'<strong class="service-phone">{escape(tel)}</strong>'
                st.markdown(f'<article class="nearby-service"><div class="service-kicker">{escape(str(h["병원분류명"]))} · 직선거리 {h["거리_km"]:.2f}km</div>'
                            f'<h4>{escape(name)}</h4><p>{escape(str(h["주소"]))}</p>{tel_html}'
                            f'<div class="service-map-links"><a href="{kakao}" target="_blank" rel="noopener noreferrer">카카오맵 ↗</a>'
                            f'<a href="{naver}" target="_blank" rel="noopener noreferrer">네이버지도 ↗</a></div></article>', unsafe_allow_html=True)

            hosp = load_hospitals(HOSP_NAME)
            nearby = pd.concat([nearest(hosp[hosp["병원분류명"] != "보건소"], *ref), nearest(hosp[hosp["병원분류명"] == "보건소"], *ref, k=1)])
            places = [h for _, h in nearby.iterrows()]
            for offset in range(0, len(places), 2):
                columns = st.columns(2, gap="small")
                for column, h in zip(columns, places[offset:offset + 2]):
                    with column:
                        hosp_card(h)
            st.caption("※ 거리는 직선거리라서 실제 걸어가거나 차로 가는 거리와 다를 수 있어요.")



    if situation != "지금 위급해 보여요":
        with st.expander("전화할 때 이렇게 말해보세요", expanded=True):
            script = "단골 어르신의 안부나 식사·외출 등 생활 도움이 걱정되어 문의드립니다. 이용할 수 있는 서비스와 상담할 곳을 안내받고 싶어요."
            st.markdown(f'<div class="phone-script">“{script}”</div>', unsafe_allow_html=True)
            st.caption("알고 있는 사실만 설명하고, 담당자의 질문에 따라 필요한 내용을 알려주세요.")


    st.markdown('<div class="help-source">공식 안내 확인: 2026.10.23<br>'
                '<a href="https://wis.seoul.go.kr/wfs/sos/guide.do" target="_blank" rel="noopener noreferrer">서울시 돌봄SOS 사업 안내 ↗</a> · '
                '<a href="https://www.seoul.go.kr/policy/view.do?id=1064&amp;lan=KO" target="_blank" rel="noopener noreferrer">안심돌봄120 운영 안내 ↗</a> · '
                '<a href="https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/cvcdInfo/cprInfoMain.do" target="_blank" rel="noopener noreferrer">질병관리청 응급 대응 안내 ↗</a>'
                '</div>', unsafe_allow_html=True)
    st.button("우리 동네로 돌아가기", key="help_to_card", width="stretch", on_click=go_to_page, args=(PAGES[1],))

# ---------------------------------------------------------------- 출처
st.divider()
st.caption("행정동 경계 출처: 통계청 통계지리정보서비스(SGIS) 행정동 경계(공공누리 제1유형), "
           "[vuski/admdongkor](https://github.com/vuski/admdongkor) 가공본(CC BY 4.0) ver20260701  \n"
           "병의원 위치 출처: 서울시 병의원 위치 정보 (공모전 제공 데이터)  \n"
           "주민센터 출처: 행정안전부 읍면동 하부행정기관 현황 (2025.12.31 기준)  \n"
           "아이콘 출처: [Microsoft Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT License)")


st.markdown('<footer style="text-align:center;color:#8A97A9;font-size:.73rem;line-height:1.8;padding:20px 0 8px;">© 2026 소시오패스 · 안부가게</footer>', unsafe_allow_html=True)
