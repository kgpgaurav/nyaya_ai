"""Streamlit client for the Nyaya FastAPI legal-assistance backend."""
import os
from urllib.parse import urlparse
import requests
import streamlit as st

st.set_page_config(page_title="Nyaya AI | Legal guidance", page_icon="⚖️", layout="wide")
MODES = {"Auto":"auto","Build case":"build_case","Explain options":"explain","Draft a letter":"draft","Practice":"practice","Understand a notice":"notice"}
LANGUAGES = {"Auto-detect":"auto","English":"en","Hindi":"hi","Hinglish":"hinglish"}

def backend_url():
    try: configured = st.secrets.get("NYAYA_API_URL", "")
    except (FileNotFoundError, KeyError): configured = ""
    url = str(configured or os.environ.get("NYAYA_API_URL", "http://localhost:8000")).rstrip("/")
    if urlparse(url).scheme not in ("http","https"):
        raise ValueError("NYAYA_API_URL must be an http(s) URL")
    return url

def session():
    if "nyaya_session" not in st.session_state:
        s = requests.Session()
        s.headers["x-nyaya-client"] = "web"
        st.session_state.nyaya_session = s
    return st.session_state.nyaya_session

def api(method, path, **kwargs):
    try: r = session().request(method, backend_url()+path, timeout=90, **kwargs)
    except requests.RequestException as e:
        raise RuntimeError("Nyaya backend is unavailable. Check NYAYA_API_URL and the FastAPI service.") from e
    if not r.ok:
        try: detail = r.json().get("detail", r.text)
        except ValueError: detail = r.text
        raise RuntimeError(f"API error {r.status_code}: {detail}")
    return r.json() if "application/json" in r.headers.get("content-type","") else r.content

def load_case():
    try: st.session_state.case = api("GET","/api/case")["case"]
    except Exception: st.session_state.case = api("POST","/api/case")["case"]

st.title("⚖️ Nyaya AI")
st.caption("Practical legal guidance for everyday problems in India • English, Hindi & Hinglish")
st.info("Nyaya is general legal information, not legal representation. For urgent matters consult a lawyer. Free legal aid: NALSA 15100.")
with st.sidebar:
    st.header("Your case")
    mode = st.selectbox("Mode", list(MODES))
    lang = st.selectbox("Language", list(LANGUAGES))
    if st.button("New case", use_container_width=True):
        try: st.session_state.case = api("POST","/api/case")["case"]; st.rerun()
        except Exception as e: st.error(str(e))
    if st.button("Refresh case", use_container_width=True):
        try: st.session_state.case = api("GET","/api/case")["case"]; st.rerun()
        except Exception as e: st.error(str(e))
    if st.button("Delete my case", use_container_width=True):
        try:
            api("DELETE","/api/case")
            session().cookies.clear()
            st.session_state.pop("case",None)
            st.rerun()
        except Exception as e: st.error(str(e))
    st.caption("Supported: rental deposit, consumer refund, unpaid salary, notices. Cases are stored on the connected backend.")
if "case" not in st.session_state:
    try: load_case()
    except Exception as e: st.error(str(e)); st.stop()
case = st.session_state.case
left, right = st.columns([2.1,1], gap="large")
with left:
    st.subheader("Conversation")
    for message in case.get("messages",[]):
        with st.chat_message("user" if message.get("role")=="user" else "assistant"):
            st.write(message.get("content",""))
            meta = message.get("meta") or {}
            if meta.get("citations"):
                with st.expander("Legal source references"): st.json(meta["citations"])
            if meta.get("blocks"):
                with st.expander("Supporting details"): st.json(meta["blocks"])
    if not case.get("messages"): st.write(case.get("welcome","Describe your issue."))
    pending = case.get("pending")
    if pending:
        st.warning("Confirm your facts before drafting a letter.")
        st.write(pending.get("prompt","Please check the extracted facts."))
        with st.form("confirmation"):
            edits = {f["field"]: st.text_input(f.get("label",f["field"]),value=f.get("value","")) for f in case.get("facts",[])}
            a,b = st.columns(2)
            yes = a.form_submit_button("Confirm facts")
            no = b.form_submit_button("Reject")
            if yes or no:
                old = {f["field"]:f.get("value","") for f in case.get("facts",[])}
                changed = {k:v for k,v in edits.items() if old.get(k)!=v} if yes else {}
                try:
                    st.session_state.case = api("POST","/api/case/confirm",json={"confirmed":yes,"edits":changed})["case"]
                    st.rerun()
                except Exception as e: st.error(str(e))
    prompt = st.chat_input("Describe your problem or paste a notice",disabled=bool(pending))
    if prompt:
        try:
            with st.spinner("Checking the facts and references…"):
                st.session_state.case = api("POST","/api/case/messages",
                    json={"text":prompt,"mode":MODES[mode],"language":LANGUAGES[lang]})["case"]
            st.rerun()
        except Exception as e: st.error(str(e))
    with st.expander("🎤 Voice recording"):
        audio = st.audio_input("Record your issue")
        if audio is not None and st.button("Transcribe and send",disabled=bool(pending)):
            try:
                st.session_state.case = api("POST","/api/case/voice",
                    files={"audio":("recording.wav",audio.getvalue(),"audio/wav")},
                    data={"mode":MODES[mode],"language":LANGUAGES[lang]})["case"]
                st.rerun()
            except Exception as e: st.error(str(e))
with right:
    st.subheader("Case overview")
    st.write("**Area:**",(case.get("domain") or "Not determined").replace("_"," ").title())
    usage=case.get("usage") or {}
    if usage.get("limit"):
        st.progress(min(1.0,usage.get("calls",0)/usage["limit"]),
          text=f"Model calls: {usage.get('calls',0)} / {usage['limit']}")
    with st.expander("Facts",expanded=True):
        for f in case.get("facts",[]):
            st.markdown(f"**{f.get('label',f['field'])}:** {f.get('value','')}")
            if f.get("quote"): st.caption("From your words: "+f["quote"])
    if case.get("missing"):
        with st.expander("Missing facts"):
            for x in case["missing"]: st.write("•",x)
    if case.get("events"):
        with st.expander("Timeline"): st.json(case["events"])
    for doc in case.get("documents",[]):
        for ext in ("txt","docx"):
            try:
                data=api("GET",f"/api/case/documents/{doc['id']}.{ext}")
                st.download_button(f"Download {doc['kind']} ({ext})",data,
                    file_name=f"nyaya_{doc['id']}.{ext}",key=f"{doc['id']}-{ext}")
            except Exception as e: st.caption(str(e))
    if st.button("Export case JSON"):
        try: st.session_state.export_data=api("GET","/api/case/export")
        except Exception as e: st.error(str(e))
    if "export_data" in st.session_state:
        st.download_button("Download case.json",st.session_state.export_data,file_name="case.json")
st.caption("Facts require confirmation for drafting. References are checked against a curated legal corpus. Nothing is sent on your behalf.")
