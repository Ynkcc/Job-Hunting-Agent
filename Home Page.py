import streamlit as st

st.set_page_config(
    page_title="Job Agent",
    page_icon="🌈",
)

st.write("# Welcome to Job Agent: Your AI-Powered Job Search Assistant 🚀")

st.sidebar.success("Select a sub-menu above.")

st.markdown(
    """
    Discover JobHuntingAgent, the cutting-edge tool designed to simplify your job search on platforms like BOSS Zhipin. Our AI-driven platform offers a streamlined approach to finding the perfect job by analyzing job postings, matching your resume to job descriptions, and providing valuable insights into industry trends.
    ## Key Features: 📝
    - **Job Analysis**: Quickly assess job opportunities and industry outlooks on BOSS Zhipin, gaining insights into the most in-demand roles and skills. 💼
    - **Resume Matching and Submission**: Automatically match and submit your resume to suitable job postings, saving you time and effort. 📄
    - **Resume Optimization**: Receive personalized suggestions to enhance your resume, making it more appealing to potential employers. ✨
    - **Interview Preparation**: Access a curated list of interview questions and reference answers to help you prepare and perform confidently in interviews. 🗣️
    
    JobHuntingAgent is your go-to solution for an efficient and effective job search, helping you navigate the competitive job market with ease. 🌟
   
    Want to learn more? Check out our [github website](https://github.com/rebibabo/Job-Hunting-Agent/tree/main)
"""
)