import streamlit as st
from playwright.sync_api import sync_playwright
from agents.JobAgent import GPTRanker, GPTFilter, ResumeLoader
from agents.SearchAgent import GetJobQueryStructure
from JobRender import render
from uiautomation import WindowControl
from loguru import logger
from crawl import get_job_info, login
import multiprocessing
import time
import json
import os

st.set_page_config(page_title="职位智能推荐", page_icon="🖥️", layout="wide")

def crawling_thread(job_queue, url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = login(browser)
        job_set = set()
        page = context.new_page()
        page.goto(url)
        page2 = context.new_page()
    
        try:
            page.wait_for_selector(".options-pages a", timeout=10000)
        except:
            logger.warning("Timeout!")
            return 0

        num = min(int(page.locator(".options-pages a").all_inner_texts()[-2]), 1)
        for i in range(1, num+1):
            try:
                page.wait_for_selector(".job-list-box .job-card-wrapper", timeout=10000)
            except:
                logger.warning("等待加载工作界面超时！")
                try:
                    page.locator(".ui-icon-arrow-right").click() 
                    continue
                except:
                    continue
            job_lists = page.locator(".job-list-box .job-card-wrapper").all()       # 获取当前页所有职位
            for job in job_lists:
                jobinfo = get_job_info(job, allow_duplicate=True)
                if jobinfo is None or jobinfo.sent==1:
                    continue
                if hash(jobinfo) in job_set:
                    continue
                job_set.add(hash(jobinfo))
                try:
                    page2.goto(jobinfo.url)
                    page2.wait_for_selector(".job-sec-text", timeout=10000)
                except:
                    logger.warning(f"Failed to load {jobinfo.jobname}")
                    continue
                description = page2.locator(".job-sec-text").all_inner_texts()[0]
                jobinfo.description = description
                job_queue.put(jobinfo)
                try:
                    jobinfo.commit_to_db()
                except Exception as e:
                    logger.error(f"Failed to commit to db: {e}")
                time.sleep(0.5)
                
            job_queue.put((i, num))
            page.locator(".ui-icon-arrow-right").click()        # 点击下一页
            time.sleep(0.5)
        job_queue.put(None)      # 最后一个元素为最大页数
        context.close()
        browser.close()

def sentCV(url, cv_path, message):
    loader = ResumeLoader(cv_path)
    png_path = loader.picture_path[0]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = login(browser)
        page = context.new_page()
        page.goto(url)
        page.wait_for_timeout(2000)
        page.locator(".btn-container .btn-startchat").click()       # 立即沟通
        page.wait_for_selector("#chat-input")
        input_box = page.locator("#chat-input")
        input_box.fill(message)
        page.wait_for_timeout(2000)
        page.locator("button[type=send]").click()
        page.wait_for_timeout(2000)
        page.locator(".toolbar-btn-content [type=file]").click()            # 点击发送简历照片
        page.wait_for_timeout(1000)
        openWindow = WindowControl(name='打开')
        openWindow.SwitchToThisWindow()
        openWindow.EditControl(Name='文件名(N):').SendKeys(png_path)
        openWindow.ButtonControl(Name='打开(O)').Click()
        time.sleep(1)

if __name__ == '__main__':
    uploaded_file = st.file_uploader("选择你的简历文件", type=["pdf"])

    TotalJobInfo = []
    col1, col2, col3, col4, col5 = st.columns(5)
    
    default_model = "gpt-4o-mini"
    default_batch_size = 10
    default_window_length = 20
    default_step = 10
    default_ratio = 0.5
    default_search_input = ""
    default_message_input = ""
    
    if os.path.exists("cache/last_search.json"):
        with open("cache/last_search.json", "r", encoding="utf-8") as f:
            js = json.load(f)
            default_model = js.get("model", default_model)
            default_batch_size = js.get("batch_size", default_batch_size)
            default_window_length = js.get("window_length", default_window_length)
            default_step = js.get("step", default_step)
            default_ratio = js.get("ratio", default_ratio)
            default_search_input = js.get("search_input", default_search_input)
            default_message_input = js.get("message_input", default_message_input)
            
    search_input = st.text_input("请输入你想找的职位", value=default_search_input)
    message_input = st.text_input("请输入发送给BOSS的话术", value=default_message_input)
    with col1:
        model = st.selectbox("选择模型", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0)
    with col2:
        batch_size = st.number_input("请输入批量处理的数量", value=10, min_value=1, max_value=100)
    with col3:
        window_length = st.number_input("请输入窗口长度", value=20, min_value=1, max_value=100)
    with col4:
        step = st.number_input("请输入步长", value=10, min_value=1, max_value=100)
    with col5:
        ratio = st.number_input("请输入筛选比例", value=0.5, min_value=0.1, max_value=1.0)
        
    with open("cache/last_search.json", "w", encoding="utf-8") as f:
        json.dump({"model": model, "batch_size": batch_size, "window_length": window_length, "step": step, \
            "ratio": ratio, "search_input": search_input, "message_input": message_input}, f, ensure_ascii=False, indent=4)

    if st.button("开始搜索"):
        if uploaded_file is None:
            st.error("请选择简历文件")
            st.stop()
        if search_input == "":
            st.error("请输入岗位要求")
            st.stop()
        jobquery = GetJobQueryStructure(search_input)
        url = jobquery.to_url()
        job_buffer = multiprocessing.Queue()
        writer_process = multiprocessing.Process(target=crawling_thread, args=(job_buffer, url))
        writer_process.start()
        
        bar = st.progress(0)
        while True:
            try:
                item = job_buffer.get()
                if item is None:
                    break
                if isinstance(item, tuple):
                    bar.progress(item[0]/item[1], f"已完成{item[0]}页，共{item[1]}页")
                else:
                    TotalJobInfo.append(item)
            except KeyboardInterrupt:
                writer_process.terminate()
                break
            except Exception as e:
                logger.error(e)
                pass
                
        cv_path = uploaded_file.name
        st.write(f"共找到{len(TotalJobInfo)}条职位信息")
        st.write("正在根据用户需求进行过滤...")
        filter = GPTFilter(TotalJobInfo, search_input)
        TotalJobInfo = filter.filter(batch_size, model=model)
        st.write(f"过滤后剩余{len(TotalJobInfo)}条职位信息\n正在排序中...")
        ranker = GPTRanker(TotalJobInfo, cv_path)  
        TotalJobInfo = ranker.rank(window_length=window_length, step=step, model=model)
        TotalJobInfo = TotalJobInfo[:int(len(TotalJobInfo)*ratio)]
        st.write(f"排序后剩余{len(TotalJobInfo)}条职位信息")
        
    render(TotalJobInfo)
    for job in TotalJobInfo:
        url = job.url
        process = multiprocessing.Process(target=sentCV, args=(url, cv_path, message_input))
        process.start()
        process.join()