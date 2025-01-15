import streamlit as st
from typing import List
from APIDataClass import JobInfo, connection, cursor
from loguru import logger

@st.dialog("职位描述", width='large')
def description(jobinfo, idx):
    filter_condition = f"jobname='{jobinfo.jobname}' AND company='{jobinfo.company}' AND city='{jobinfo.city}'"
    desc = jobinfo.description.replace('\n', '<br>') if jobinfo.description else ""
    st.markdown(desc, unsafe_allow_html=True)
    button_text = "发送简历" if jobinfo.sent == 0 else "已发送"
    col1, col2, _ = st.columns([1, 1, 5])
    with col1:
        if st.button(button_text, key=f"send_resume_{idx}"):
            jobinfo.sent = 1
            jobinfo.commit_to_db()
            st.rerun()
    with col2:
        if st.button("关闭", key=f"close_dialog_{idx}"):
            st.rerun()

def render_job(jobinfo: JobInfo, idx: int):
    filter_condition = f"jobname='{jobinfo.jobname}' AND company='{jobinfo.company}' AND city='{jobinfo.city}'"
    col1, col2, col3 = st.columns([8, 4, 1])
    with col1:
        st.markdown(f'<p style="font-size: 26px; font-weight: bold;">{jobinfo.jobname} &nbsp;&nbsp;&nbsp;&nbsp; 【{jobinfo.address}】</p>', unsafe_allow_html=True)       
        st.markdown(f"""<div class="row">
            <div><span class="info1">{jobinfo.salary}</span></div>
            <div><span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span></div>
            <div><span class="info2">{jobinfo.experience if jobinfo.experience else ''}</span></div>
            <div><span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span></div>
            <div><span class="info3">{jobinfo.degree if jobinfo.degree else ''}</span></div>
            <div><span></span></div>
        </div>""", unsafe_allow_html=True)
        st.markdown('')
        st.markdown(f'<p class="tags">{" | ".join(jobinfo.labels.split("，"))}</p>', unsafe_allow_html=True)

    with col2:
        st.markdown('####')
        st.markdown(f'<p style="font-size: 22px; font-weight: bold; color: #ADD8E6;">{jobinfo.company}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="info">{jobinfo.industry} · {jobinfo.stage if jobinfo.stage else ""} · {jobinfo.scale if jobinfo.scale else ""}</p>', unsafe_allow_html=True)

    with col3:
        st.markdown('####')
        st.markdown('<p></p>', unsafe_allow_html=True)
        button_text = "查看详情" if jobinfo.clicked == 0 else ("已发送" if jobinfo.sent == 1 else "已查看")
        if st.button(button_text, key=jobinfo.url):
            jobinfo.clicked = 1
            jobinfo.commit_to_db()
            description(jobinfo, idx)
    st.markdown("---")
    
def render(TotalJobInfo: List[JobInfo]=[]):
    if "jobinfo" not in st.session_state:
        st.session_state.jobinfo = []
    if "page" not in st.session_state:
        st.session_state.page = 1
    if TotalJobInfo:
        st.session_state.jobinfo = TotalJobInfo
        st.session_state.sent = [False]*len(TotalJobInfo)
        st.session_state.click = [False]*len(TotalJobInfo)
    st.markdown(f"""<style>{open(".streamlit/style.css", "r", encoding="utf-8").read()}</style>""", unsafe_allow_html=True)
    for i in range(st.session_state.page*10-10, st.session_state.page*10):
        if i >= len(st.session_state.jobinfo):
            break
        render_job(st.session_state.jobinfo[i], i)
    
    _, col1, col2, col3, _ = st.columns([4, 1, 1, 1, 4])
    with col1:
        if st.button("上一页") and st.session_state.page > 1:
            st.session_state.page -= 1
            st.rerun()
    with col2:
        st.write(f"第{st.session_state.page}页 / 共{(len(st.session_state.jobinfo)-1)//10+1}页")
    with col3:
        if st.button("下一页") and st.session_state.page < (len(st.session_state.jobinfo)-1)//10+1:
            st.session_state.page += 1
            st.rerun()
                
if __name__ == '__main__':
    from APIDataClass import cursor, select_jobinfo_from_db
    TotalJobInfo = select_jobinfo_from_db("SELECT * FROM job LIMIT 100;")
    render(TotalJobInfo)