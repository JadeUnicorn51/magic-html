# -*- coding: utf-8 -*-
"""magic-html 交互式调试页。

启动:
    streamlit run app.py
"""
import json
import time

import requests
import streamlit as st
from lxml import html as lxml_html

from magic_html import GeneralExtractor


def copy_button(text: str, label: str = "复制") -> str:
    payload = json.dumps(text or "", ensure_ascii=False)
    return (
        "<style>"
        ".cp-btn{font:14px sans-serif;padding:6px 14px;border:1px solid #d0d0d0;"
        "border-radius:6px;background:#f7f7f7;cursor:pointer;color:#222}"
        ".cp-btn:hover{background:#eee}"
        ".cp-btn.ok{background:#d4edda;border-color:#b7d8b7;color:#155724}"
        "</style>"
        f"<button class=\"cp-btn\" id=\"cp-{label}\" "
        f"data-text='{payload}'>{label}</button>"
        "<script>"
        "(function(btn){"
        "  btn.addEventListener('click', async function(){"
        "    try {"
        "      await navigator.clipboard.writeText(JSON.parse(btn.getAttribute('data-text')));"
        "    } catch(e) {"
        "      const ta=document.createElement('textarea');"
        "      ta.value=JSON.parse(btn.getAttribute('data-text'));"
        "      document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();"
        "    }"
        "    const orig=btn.textContent;"
        "    btn.textContent='已复制';btn.classList.add('ok');"
        "    setTimeout(()=>{btn.textContent=orig;btn.classList.remove('ok');},1200);"
        "  });"
        "})(document.getElementById('cp-" + label + "'))"
        "</script>"
    )


SAMPLE_HTML = """<!doctype html>
<html>
<head>
    <title>Example Domain</title>
    <meta charset="utf-8" />
</head>
<body>
<div>
    <h1>Example Domain</h1>
    <p>This domain is for use in illustrative examples in documents. You may use this
    domain in literature without prior coordination or asking for permission.</p>
    <p><a href="https://www.iana.org/domains/example">More information...</a></p>
    <p>This second paragraph shows that the extractor keeps multiple paragraphs together when they form a coherent article body.</p>
</div>
<div class="ad">This is an ad block that should be removed by the extractor.</div>
<footer>Footer noise that should be dropped.</footer>
</body>
</html>
"""


def _to_markdown(html_fragment: str) -> str:
    if not html_fragment:
        return ""
    try:
        root = lxml_html.fragment_fromstring(html_fragment, create_parent="div")
    except Exception:
        return html_fragment

    out: list[str] = []

    def walk(node):
        if node.tag == "br":
            out.append("\n")
            return
        if node.tag == "img":
            alt = node.get("alt") or ""
            src = node.get("src") or ""
            if src:
                out.append(f"![{alt}]({src})" if alt else f"![]({src})")
            return
        if node.tag and len(node.tag) == 2 and node.tag[0] == "h" and node.tag[1].isdigit():
            text = (node.text_content() or "").strip()
            if text:
                out.append(f"\n{'#' * int(node.tag[1])} {text}\n")
            for child in node:
                walk(child)
            return
        if node.tag == "li":
            text = (node.text_content() or "").strip()
            if text:
                out.append(f"- {text}\n")
            return
        if node.tag == "p":
            text = (node.text_content() or "").strip()
            if text:
                out.append(f"\n{text}\n")
            return
        if node.tag in ("strong", "b"):
            text = (node.text_content() or "").strip()
            if text:
                out.append(f"**{text}**")
            return
        if node.tag in ("em", "i"):
            text = (node.text_content() or "").strip()
            if text:
                out.append(f"*{text}*")
            return
        if node.tag == "a":
            text = (node.text_content() or "").strip()
            href = node.get("href") or ""
            if text:
                out.append(f"[{text}]({href})" if href else text)
            return
        if node.text:
            out.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                out.append(child.tail)
        if node.tag in ("ul", "ol", "div", "section", "article"):
            out.append("\n")

    walk(root)
    md = "".join(out)
    while "\n\n\n" in md:
        md = md.replace("\n\n\n", "\n\n")
    return md.strip()


@st.cache_resource
def get_extractor():
    return GeneralExtractor()


def do_extract(html: str, base_url: str, html_type: str | None) -> dict:
    extractor = get_extractor()
    kwargs = {"base_url": base_url} if base_url else {}
    if html_type and html_type != "auto":
        kwargs["html_type"] = html_type
    t0 = time.perf_counter()
    result = extractor.extract(html=html, **kwargs)
    result["__cost_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    result["__markdown"] = _to_markdown(result.get("html") or "")
    return result


def fetch_url(url: str) -> tuple[str, str]:
    resp = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; magic-html-tester/1.0)"},
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text, resp.url


st.set_page_config(page_title="magic-html 测试页", page_icon="🧪", layout="wide")
st.title("magic-html 测试页")

with st.sidebar:
    st.header("参数")
    html_type = st.selectbox(
        "html_type",
        options=["auto", "article", "forum", "weixin"],
        index=0,
    )

tab_paste, tab_upload, tab_url = st.tabs(["粘贴 HTML", "上传文件", "输入 URL"])

with tab_paste:
    html_text = st.text_area("HTML 内容", value=SAMPLE_HTML, height=300, label_visibility="collapsed")
    paste_base = st.text_input("base_url（可选）", value="", key="paste_base")
    if st.button("提取", type="primary", key="run_paste"):
        st.session_state["__html"] = html_text
        st.session_state["__base_url"] = paste_base

with tab_upload:
    uploaded = st.file_uploader("选择 HTML 文件", type=["html", "htm", "txt"])
    upload_base = st.text_input("base_url（可选）", value="", key="up_base")
    if st.button("提取", type="primary", key="run_upload"):
        if uploaded is None:
            st.warning("请先选择文件")
        else:
            raw = uploaded.read()
            try:
                st.session_state["__html"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                st.session_state["__html"] = raw.decode("utf-8", errors="replace")
            st.session_state["__base_url"] = upload_base

with tab_url:
    target_url = st.text_input("URL", value="https://example.com/")
    if st.button("抓取并提取", type="primary", key="run_url"):
        if not target_url.strip():
            st.warning("请输入 URL")
        else:
            with st.spinner(f"抓取 {target_url} ..."):
                try:
                    fetched_html, final_url = fetch_url(target_url.strip())
                except Exception as e:
                    st.error(f"抓取失败: {e}")
                    fetched_html, final_url = "", ""
            if fetched_html:
                st.session_state["__html"] = fetched_html
                st.session_state["__base_url"] = final_url

if st.session_state.get("__html"):
    html_in = st.session_state["__html"]
    base_url_in = st.session_state.get("__base_url", "")

    try:
        result = do_extract(html_in, base_url_in, html_type if html_type != "auto" else None)
    except Exception as e:
        st.error(f"提取失败: {type(e).__name__}: {e}")
        st.stop()

    body_html = result.get("html") or ""
    body_md = result.get("__markdown") or ""
    title = result.get("title") or ""

    st.caption(f"title: {title}" if title else "—")

    col_html, col_md = st.columns(2)

    with col_html:
        hdr_l, hdr_r = st.columns([6, 1])
        with hdr_l:
            st.subheader("HTML 渲染")
        with hdr_r:
            st.components.v1.html(copy_button(body_html, "复制 HTML"), height=36)
        if body_html:
            st.components.v1.html(
                f"<div style='font-family:sans-serif;line-height:1.6;padding:8px'>{body_html}</div>",
                height=600,
                scrolling=True,
            )
        else:
            st.info("无内容")

    with col_md:
        hdr_l, hdr_r = st.columns([6, 1])
        with hdr_l:
            st.subheader("Markdown 渲染")
        with hdr_r:
            st.components.v1.html(copy_button(body_md, "复制 Markdown"), height=36)
        if body_md:
            with st.container(height=600, border=True):
                st.markdown(body_md)
        else:
            st.info("无内容")
else:
    st.info("选择一种方式输入 HTML，再点「提取」。")
