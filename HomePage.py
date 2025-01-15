import streamlit as st

# 子页面位于pages文件夹下
st.set_page_config(
    page_title="您的智能职位搜索助手",
    page_icon="🌈",
)

st.write("# 欢迎使用Job Agent：AI驱动的求职助手")

st.sidebar.success("请选择上方的子页面。")

st.markdown(
    """
    JobHuntingAgent是一款基于人工智能技术的求职助手，专为BOSS直聘等招聘网站设计。它通过分析职位描述、匹配简历、提供行业趋势等方式，帮助您快速评估职位并找到最合适的工作机会。
    
    ## 主要功能：📝
    - **职位分析**：通过BOSS直聘等招聘网站快速评估职位并获取行业信息，帮助您快速找到最适合自己的职位。💼
    - **简历匹配与提交**：自动匹配简历并提交至适合的职位，节省您的时间和精力。📄
    - **简历优化**：提供个性化的简历建议，使您的简历更加吸引人。✨
    - **面试准备**：提供经过筛选的面试题目和参考答案，帮助您在面试中更加自信。🗣️
    
    JobHuntingAgent是您效率和效益求职的最佳选择，帮助您轻松应对职场竞争。🌟
    
    想要了解更多？请访问我们的[GitHub网站](https://github.com/rebibabo/Job-Hunting-Agent/tree/main)
"""
)