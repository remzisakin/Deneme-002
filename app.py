"""Streamlit tabanlı veri keşif ve otomatik analiz uygulaması."""

# requirements.txt önerisi
# streamlit
# pandas
# numpy
# plotly
# openai
# scikit-learn
# kaleido

# .env
# OPENAI_API_KEY={{senin_api_anahtarın}}

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openai import OpenAI


st.set_page_config(
    page_title="Akıllı Veri Analizcisi",
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass
class SchemaInfo:
    numeric_cols: List[str]
    categorical_cols: List[str]
    datetime_cols: List[str]
    text_cols: List[str]
    high_missing_cols: List[Tuple[str, float]]
    missing_ratio: pd.Series
    cardinality: Dict[str, int]


MODEL_OPTIONS = [
    "gpt-4o-mini",
    "gpt-4o",
    "o3-mini",
]

DEFAULT_MODEL = "gpt-4o-mini"
MAX_ROWS = 100_000


@st.cache_data(show_spinner=False)
def load_data(uploaded_file: Any) -> pd.DataFrame:
    """Read uploaded file into pandas DataFrame with basic safeguards."""

    if uploaded_file is None:
        raise ValueError("Lütfen bir dosya yükleyin.")

    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            try:
                df = pd.read_csv(uploaded_file, sep=None, engine="python")
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
        elif name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        elif name.endswith('.json'):
            uploaded_file.seek(0)
            df = pd.read_json(uploaded_file)
        else:
            raise ValueError("Desteklenmeyen dosya formatı. Lütfen CSV, Excel veya JSON yükleyin.")
    except Exception as exc:
        raise ValueError(f"Dosya okunamadı: {exc}") from exc

    if df.empty:
        raise ValueError("Dosya boş görünüyor.")

    if len(df) > MAX_ROWS:
        st.warning(
            f"Veri {len(df)} satır içeriyor. Performans için ilk {MAX_ROWS} satır kullanılıyor."
        )
        df = df.head(MAX_ROWS)

    return df


def _try_parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=["object", "string"]).columns:
        sample = df[col].dropna().head(20)
        if sample.empty:
            continue
        try:
            parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True, dayfirst=True)
        except Exception:
            continue
        if parsed.notna().mean() > 0.6:
            df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True, dayfirst=True)
    return df


def infer_schema(df: pd.DataFrame) -> SchemaInfo:
    df = _try_parse_dates(df.copy())

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["category", "object", "string"]).columns.tolist()
    text_cols = [col for col in categorical_cols if df[col].nunique(dropna=True) > 100]

    missing_ratio = df.isna().mean().sort_values(ascending=False)
    high_missing_cols = [(col, ratio) for col, ratio in missing_ratio.items() if ratio > 0.4]
    cardinality = {col: df[col].nunique(dropna=True) for col in df.columns}

    return SchemaInfo(
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        datetime_cols=datetime_cols,
        text_cols=text_cols,
        high_missing_cols=high_missing_cols,
        missing_ratio=missing_ratio,
        cardinality=cardinality,
    )


def _suggest_time_series(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    if not schema.datetime_cols:
        return suggestions
    numeric = schema.numeric_cols
    if not numeric:
        return suggestions
    for time_col in schema.datetime_cols:
        suggestions.append(
            {
                "title": f"Zaman Serisi - {time_col}",
                "chart_type": "line",
                "priority": 1,
                "description": "Tarih sütunu ile sayısal ölçümü zaman içinde takip eder.",
                "default": {
                    "x": time_col,
                    "y": numeric[0],
                    "color": None,
                    "agg": "mean",
                },
            }
        )
    return suggestions


def _suggest_numeric_univariate(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    for col in schema.numeric_cols:
        suggestions.append(
            {
                "title": f"Histogram - {col}",
                "chart_type": "histogram",
                "priority": 3,
                "description": "Sayısal değişken dağılımını gösterir; yoğunluk eğrisi eklenebilir.",
                "default": {
                    "x": col,
                    "y": None,
                    "color": None,
                    "agg": None,
                },
            }
        )
    return suggestions


def _suggest_numeric_categorical(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    for cat in schema.categorical_cols:
        card = schema.cardinality.get(cat, 0)
        if card == 0:
            continue
        if card > 100:
            suggestions.append(
                {
                    "title": f"Kategori Uyarısı - {cat}",
                    "chart_type": "warning",
                    "priority": 6,
                    "description": "Kardinalite yüksek (>100). En sık kategorileri filtreleyin veya örnekleyin.",
                    "default": {},
                }
            )
            continue
        for num in schema.numeric_cols:
            suggestions.extend(
                [
                    {
                        "title": f"Kutu Grafiği - {num} vs {cat}",
                        "chart_type": "box",
                        "priority": 2,
                        "description": "Kategorilere göre sayısal dağılımı gösterir.",
                        "default": {"x": cat, "y": num, "color": cat, "agg": None},
                    },
                    {
                        "title": f"Bar (Ortalama) - {num} vs {cat}",
                        "chart_type": "bar",
                        "priority": 2,
                        "description": "Kategorilere göre sayısal değerin agregasyonunu karşılaştırır.",
                        "default": {"x": cat, "y": num, "color": None, "agg": "mean"},
                    },
                ]
            )
    return suggestions


def _suggest_numeric_numeric(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    nums = schema.numeric_cols
    if len(nums) < 2:
        return suggestions
    for x in nums:
        for y in nums:
            if x >= y:
                continue
            suggestions.append(
                {
                    "title": f"Saçılım - {x} vs {y}",
                    "chart_type": "scatter",
                    "priority": 4,
                    "description": "İki sayısal değişken arasındaki ilişkiyi gösterir (trendline=OLS).",
                    "default": {"x": x, "y": y, "color": None, "agg": None},
                }
            )
    suggestions.append(
        {
            "title": "Korelasyon Matrisi",
            "chart_type": "corr",
            "priority": 1,
            "description": "Sayısal sütunlar arasındaki korelasyon ısı haritası.",
            "default": {},
        }
    )
    return suggestions


def _suggest_categorical_univariate(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    for cat in schema.categorical_cols:
        card = schema.cardinality.get(cat, 0)
        if 0 < card <= 30:
            suggestions.append(
                {
                    "title": f"Bar (Sayımlar) - {cat}",
                    "chart_type": "bar_count",
                    "priority": 5,
                    "description": "Kategorik değişkenin frekans dağılımını gösterir.",
                    "default": {"x": cat, "y": None, "color": None, "agg": None},
                }
            )
    return suggestions


def suggest_charts(df: pd.DataFrame, schema: SchemaInfo) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    suggestions.extend(_suggest_time_series(df, schema))
    suggestions.extend(_suggest_numeric_univariate(df, schema))
    suggestions.extend(_suggest_numeric_categorical(df, schema))
    suggestions.extend(_suggest_numeric_numeric(df, schema))
    suggestions.extend(_suggest_categorical_univariate(df, schema))

    filtered = [s for s in suggestions if s["chart_type"] != "warning"]
    if len(filtered) < 3:
        suggestions.extend(
            [
                {
                    "title": "Genel Histogram",
                    "chart_type": "histogram",
                    "priority": 10,
                    "description": "Temel dağılım grafiği önerisi.",
                    "default": {"x": df.columns[0], "y": None, "color": None, "agg": None},
                }
            ]
        )
    suggestions.sort(key=lambda item: item.get("priority", 5))
    return suggestions[:10]
def render_chart(
    df: pd.DataFrame,
    suggestion: Dict[str, Any],
    x: Optional[str],
    y: Optional[str],
    color: Optional[str],
    agg: Optional[str],
    filter_col: Optional[str],
    filter_values: Optional[List[str]],
) -> Optional[go.Figure]:
    filtered_df = df.copy()
    if filter_col and filter_values:
        filtered_df = filtered_df[filtered_df[filter_col].isin(filter_values)]

    chart_type = suggestion.get("chart_type")

    if chart_type == "warning":
        st.warning(suggestion.get("description", ""))
        return None

    if chart_type == "corr":
        numeric_cols = filtered_df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) < 2:
            st.info("Korelasyon için en az iki sayısal değişken gerekir.")
            return None
        corr_matrix = filtered_df[numeric_cols].corr()
        fig = px.imshow(
            corr_matrix,
            text_auto=True,
            color_continuous_scale="RdBu",
            aspect="auto",
        )
        fig.update_layout(margin=dict(l=40, r=40, t=40, b=40))
        return fig

    if chart_type == "histogram":
        if x is None:
            st.info("Histogram için bir sütun seçin.")
            return None
        fig = px.histogram(filtered_df, x=x, color=color, marginal="rug")
        fig.update_layout(bargap=0.05)
        return fig

    if chart_type == "line":
        if x is None or y is None:
            st.info("Çizgi grafik için x ve y seçin.")
            return None
        if agg:
            group_cols = [x] + ([color] if color else [])
            agg_df = filtered_df.groupby(group_cols).agg({y: agg}).reset_index()
            y_display = f"{y}_{agg}"
            agg_df.rename(columns={y: y_display}, inplace=True)
        else:
            agg_df = filtered_df
            y_display = y
        fig = px.line(agg_df, x=x, y=y_display, color=color if color in agg_df.columns else None)
        return fig

    if chart_type == "box":
        if x is None or y is None:
            st.info("Kutu grafik için kategorik (x) ve sayısal (y) seçin.")
            return None
        fig = px.box(filtered_df, x=x, y=y, color=color, points="suspectedoutliers")
        return fig

    if chart_type == "bar":
        if x is None or y is None:
            st.info("Bar grafik için x ve y seçin.")
            return None
        plot_df = filtered_df
        if agg:
            group_cols = [x] + ([color] if color else [])
            plot_df = filtered_df.groupby(group_cols).agg({y: agg}).reset_index()
            y_display = f"{y}_{agg}"
            plot_df.rename(columns={y: y_display}, inplace=True)
        else:
            y_display = y
        fig = px.bar(plot_df, x=x, y=y_display, color=color if color in plot_df.columns else None, text_auto=True)
        return fig

    if chart_type == "bar_count":
        if x is None:
            st.info("Bar grafik için bir kategorik sütun seçin.")
            return None
        count_df = filtered_df[x].value_counts().reset_index()
        count_df.columns = [x, "Count"]
        fig = px.bar(count_df, x=x, y="Count", color=color or x, text_auto=True)
        return fig

    if chart_type == "scatter":
        if x is None or y is None:
            st.info("Saçılım grafiği için x ve y seçin.")
            return None
        fig = px.scatter(filtered_df, x=x, y=y, color=color, trendline="ols")
        return fig

    st.info("Bu öneri henüz desteklenmiyor.")
    return None


def format_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def build_llm_prompt(
    df: pd.DataFrame,
    schema: SchemaInfo,
    language: str = "Türkçe",
) -> str:
    sample_rows = df.head(5)
    numeric_stats = df.describe(include=[np.number]).T.round(3)
    categorical_summary = {
        col: df[col].value_counts(normalize=True).head(5).round(3).to_dict()
        for col in schema.categorical_cols[:3]
    }

    prompt = f"""
Veri seti özeti:
- Satır sayısı: {len(df)}
- Sütun sayısı: {df.shape[1]}
- Sayısal sütunlar: {schema.numeric_cols}
- Kategorik sütunlar: {schema.categorical_cols}
- Tarihsel sütunlar: {schema.datetime_cols}
- Eksik değer oranları (ilk 5): {schema.missing_ratio.head().round(3).to_dict()}

Örnek satırlar:
{sample_rows.to_dict(orient='records')}

Sayısal özet istatistikler:
{numeric_stats.to_dict(orient='index')}

Kategorik özetler (ilk 3 sütun):
{json.dumps(categorical_summary, ensure_ascii=False)}

Görev:
Veride dikkat çeken desenler, olası aykırılıklar, önemli korelasyonlar, öne çıkan kategoriler, bariz veri kalitesi riskleri ve anlamlı grafik önerileri nelerdir? Maddeler halinde ve kısa paragraflarla yanıtla. Uygunsa basit iş hipotezleri ve sonraki adım önerileri ekle. Yanıt dili: {language}. Hassas kişisel veriler olabileceğini varsayarak maskeleme önerileri yap.
"""
    return prompt.strip()


def run_llm(prompt: str, model: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Kısa ama içgörülü veri analizi raporları yazan yardımcı bir analistsin."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""


def download_button(fig: Optional[go.Figure], llm_report: Optional[str]) -> None:
    col1, col2, col3 = st.columns(3)

    with col1:
        if fig is not None:
            try:
                png_bytes = fig.to_image(format="png")
                st.download_button(
                    "Grafiği PNG indir",
                    data=png_bytes,
                    file_name="grafik.png",
                    mime="image/png",
                )
            except Exception as exc:
                st.warning(f"PNG oluşturulamadı (kaleido gerekli olabilir): {exc}")

    with col2:
        if fig is not None:
            html_bytes = fig.to_html(include_plotlyjs="cdn").encode("utf-8")
            st.download_button(
                "Grafiği HTML indir",
                data=html_bytes,
                file_name="grafik.html",
                mime="text/html",
            )

    with col3:
        if llm_report:
            st.download_button(
                "LLM raporunu indir (.md)",
                data=llm_report.encode("utf-8"),
                file_name="analiz_raporu.md",
                mime="text/markdown",
            )


def render_overview_tab(df: pd.DataFrame, schema: SchemaInfo) -> None:
    st.subheader("Veri Özeti")
    total_rows = len(df)
    total_cols = df.shape[1]
    missing_pct = df.isna().mean().mean() * 100
    int_count = len([col for col in schema.numeric_cols if pd.api.types.is_integer_dtype(df[col])])
    float_count = len(schema.numeric_cols) - int_count
    categorical_count = len(schema.categorical_cols)
    datetime_count = len(schema.datetime_cols)

    metrics = st.columns(5)
    metrics[0].metric("Satır", format_number(total_rows))
    metrics[1].metric("Sütun", format_number(total_cols))
    metrics[2].metric("Eksik %", f"{missing_pct:.1f}")
    metrics[3].metric("Sayısal (int/float)", f"{int_count}/{float_count}")
    metrics[4].metric("Kategorik/Tarih", f"{categorical_count}/{datetime_count}")

    st.markdown("### Eksik Değer Analizi")
    missing_df = schema.missing_ratio.reset_index()
    missing_df.columns = ["Sütun", "Eksik Oranı"]
    st.dataframe(missing_df.style.background_gradient(cmap="Reds"), use_container_width=True)

    if schema.high_missing_cols:
        with st.expander("Yüksek eksik oranlı sütunlar"):
            for col, ratio in schema.high_missing_cols:
                st.warning(f"{col}: {ratio:.1%} eksik")

    st.markdown("### Örnek Veri (ilk 20 satır)")
    st.dataframe(df.head(20), use_container_width=True)


def render_suggestions_tab(suggestions: List[Dict[str, Any]]) -> None:
    st.subheader("Otomatik Grafik Önerileri")
    if not suggestions:
        st.info("Şu an öneri yok. Daha fazla veri yüklemeyi deneyin.")
        return

    for suggestion in suggestions:
        with st.container():
            st.markdown(f"**{suggestion['title']}**")
            st.write(suggestion.get("description", ""))
        st.markdown("---")


def render_chart_tab(
    df: pd.DataFrame,
    schema: SchemaInfo,
    suggestions: List[Dict[str, Any]],
) -> Optional[go.Figure]:
    st.subheader("Grafik Alanı")
    if not suggestions:
        st.info("Grafik oluşturmak için önce veri yükleyin.")
        return None

    options = {s["title"]: s for s in suggestions}
    selected_title = st.selectbox("Öneri seçin", list(options.keys()))
    suggestion = options[selected_title]

    default_params = suggestion.get("default", {})

    with st.expander("Grafik Parametreleri", expanded=True):
        x = st.selectbox("X ekseni", [None] + df.columns.tolist(), index=_index_of(default_params.get("x"), df.columns))
        y = st.selectbox("Y ekseni", [None] + df.columns.tolist(), index=_index_of(default_params.get("y"), df.columns))
        color = st.selectbox("Renk", [None] + df.columns.tolist(), index=_index_of(default_params.get("color"), df.columns))

        agg = None
        if suggestion.get("chart_type") in {"line", "bar"}:
            agg_options = [None, "mean", "median", "sum", "count"]
            agg = st.selectbox(
                "Agregasyon", agg_options, index=agg_options.index(default_params.get("agg")) if default_params.get("agg") in agg_options else 0
            )

        filter_col = None
        filter_values: Optional[List[str]] = None
        if schema.categorical_cols:
            filter_col = st.selectbox("Filtre sütunu", [None] + schema.categorical_cols)
            if filter_col:
                unique_vals = df[filter_col].dropna().astype(str).unique().tolist()
                filter_values = st.multiselect("Filtre değerleri", unique_vals)

    fig = render_chart(df, suggestion, x, y, color, agg, filter_col, filter_values)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
        st.session_state["last_fig"] = fig
    return fig


def _index_of(value: Optional[str], columns: pd.Index) -> int:
    if value is None:
        return 0
    try:
        return list([None] + columns.tolist()).index(value)
    except ValueError:
        return 0


def render_llm_tab(
    df: pd.DataFrame,
    schema: SchemaInfo,
    model: str,
    language: str,
) -> Tuple[Optional[str], Optional[str]]:
    st.subheader("LLM Analizi")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.warning("OPENAI_API_KEY bulunamadı. Lütfen .env dosyasında ayarlayın. Uygulama çalışmaya devam edecek.")
        return None, None

    if "llm_prompt" not in st.session_state:
        st.session_state["llm_prompt"] = ""
    if "llm_report" not in st.session_state:
        st.session_state["llm_report"] = None

    prompt = build_llm_prompt(df, schema, language)
    prompt_text = st.text_area(
        "LLM istem önizlemesi",
        st.session_state.get("llm_prompt") or prompt,
        height=300,
    )
    st.session_state["llm_prompt"] = prompt_text

    st.caption("Hassas bilgiler içeren verileri LLM'e göndermeden önce maskeleyin.")

    if st.button("Analizi Çalıştır", type="primary"):
        with st.spinner("LLM analizi oluşturuluyor..."):
            try:
                llm_report = run_llm(prompt_text, model)
                st.session_state["llm_report"] = llm_report
                st.markdown(llm_report)
            except Exception as exc:
                st.exception(exc)
    else:
        llm_report = st.session_state.get("llm_report")
        if llm_report:
            st.markdown(llm_report)
    return prompt_text, st.session_state.get("llm_report")


def render_download_tab(fig: Optional[go.Figure], llm_report: Optional[str]) -> None:
    st.subheader("Çıktıları İndir")
    figure_to_use = fig or st.session_state.get("last_fig")
    download_button(figure_to_use, llm_report)


def render_sidebar() -> Tuple[Any, str, str]:
    st.sidebar.title("Kontrol Paneli")
    st.sidebar.markdown("Verinizi yükleyin ve ayarları yönetin.")

    theme = st.sidebar.radio("Tema seçimi", ["Varsayılan", "Açık", "Koyu"], index=0)
    if theme == "Açık":
        st.markdown(
            """
            <style>
            body {background-color: #f8f9fa;}
            </style>
            """,
            unsafe_allow_html=True,
        )
    elif theme == "Koyu":
        st.markdown(
            """
            <style>
            body {background-color: #0e1117; color: #fafafa;}
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Örnek Veri")
    example_df = pd.DataFrame(
        {
            "tarih": pd.date_range("2023-01-01", periods=30, freq="D"),
            "kategori": np.random.choice(["A", "B", "C"], 30),
            "satis": np.random.randint(50, 200, 30),
            "musteri": np.random.randint(1, 100, 30),
        }
    )
    csv_bytes = example_df.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("Örnek CSV indir", data=csv_bytes, file_name="ornek_veri.csv", mime="text/csv")

    st.sidebar.markdown("---")
    uploaded_file = st.sidebar.file_uploader("Veri dosyası yükle", type=["csv", "xlsx", "xls", "json"])

    st.sidebar.markdown("---")
    st.sidebar.markdown("### LLM Ayarları")
    model = st.sidebar.selectbox("Model", MODEL_OPTIONS, index=MODEL_OPTIONS.index(DEFAULT_MODEL))
    language = st.sidebar.selectbox("Analiz dili", ["Türkçe", "İngilizce", "Almanca", "Fransızca"])

    return uploaded_file, model, language


def main() -> None:
    st.title("Akıllı Veri Analizcisi")
    st.caption("Verinizi yükleyin, otomatik EDA ve LLM destekli raporlama ile içgörü kazanın.")

    uploaded_file, model, language = render_sidebar()

    tabs = st.tabs(["Özet", "Öneriler", "Grafik", "LLM Raporu", "İndir"])

    if uploaded_file is None:
        with tabs[0]:
            st.info("Analize başlamak için sol menüden bir veri dosyası yükleyin.")
        for tab in tabs[1:]:
            with tab:
                st.empty()
        return

    try:
        df = load_data(uploaded_file)
    except Exception as exc:
        with tabs[0]:
            st.exception(exc)
        return

    schema = infer_schema(df)
    suggestions = suggest_charts(df, schema)

    with tabs[0]:
        render_overview_tab(df, schema)

    with tabs[1]:
        render_suggestions_tab(suggestions)

    with tabs[2]:
        fig = render_chart_tab(df, schema, suggestions)

    llm_prompt: Optional[str] = None
    llm_report: Optional[str] = None
    with tabs[3]:
        llm_prompt, llm_report = render_llm_tab(df, schema, model, language)

    with tabs[4]:
        render_download_tab(fig if 'fig' in locals() else None, llm_report)


if __name__ == "__main__":
    main()

