import streamlit as st
from agents.job_agent import ResumeLoader, GPTRanker
from agents.search_agent import GetJobQueryStructure
from JobRender import render
from APIDataClass import select_jobinfo_from_db

st.set_page_config(page_title="职位智能推荐", page_icon="🖥️", layout="wide")

def Crawler():
    jobinfo = select_jobinfo_from_db("SELECT * from job where description is not null limit 10;")
    return jobinfo

if __name__ == '__main__':
    uploaded_file = st.file_uploader("选择一个文件", type=["pdf"])
    search_input = st.text_input("请输入你想找的职位")

    TotalJobInfo = []

    if st.button("开始搜索"):
        if uploaded_file is not None and search_input!= "":
            # jobquery = GetJobQueryStructure(search_input)
            jobinfo = Crawler()
            # ranker = GPTRanker(jobinfo, uploaded_file.name)
            # TotalJobInfo = ranker.rank()
            TotalJobInfo = jobinfo

    render(TotalJobInfo)