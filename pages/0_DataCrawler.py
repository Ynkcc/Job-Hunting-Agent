import streamlit as st
from tool.decorators import cache
from APIDataClass import cursor, JobQueryRequest, CachedIterator
from playwright.sync_api import Playwright, sync_playwright
from crawl import login, get_job_info
import pandas as pd
from loguru import logger
import json
import time
import pyautogui
import multiprocessing
import os

@st.cache_data
def get_data(query):
    cursor.execute(query)
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=[desc[0] for desc in cursor.description])
    return df

def run(url, jobType, cache_path, stop_event, max_page_num=30) -> None:      # 输入待爬取的网页和职业类型，暂时不获取职业的描述
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        # context = browser.new_context(viewport={'width': 600, 'height': 400})
        if not os.path.exists('cache/state.json'):
            context = browser.new_context()
            login(context)
            context.storage_state(path="cache/state.json")
        else:
            context = browser.new_context(storage_state="cache/state.json")
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                page = json.load(f)["index"]
        else:
            page = 0
        url = f'{url}&page={page}'
        logger.info(f'Start crawling: {url}')
        
        page = context.new_page()
        page.goto(url)
        
        try:
            window_title = browser.contexts[0].pages[0].title()
            window = pyautogui.getWindowsWithTitle(window_title)[0]
            window.minimize()
        except:
            pass
        
        max_time = 60
        while max_time > 0:     # 等待页面加载出来，最多10s
            if page.locator(".job-empty-icon").count() > 0:     # 如果没有职位
                logger.warning('No jobs found')
                return
            if page.locator(".job-card-body > a").count() > 0:  # 加载成功
                break
            max_time -= 1
            page.wait_for_timeout(1000)
        else:
            logger.warning("Timeout!")
            return
        
        num = min(max_page_num, int(page.locator(".options-pages a").all_inner_texts()[-2]))     # 获取最大页数
        iterator = CachedIterator([list(range(num))], cache_path)
        for page_num in iterator:
            if page.locator(".job-empty-icon").count() > 0:     # 如果没有职位
                logger.warning('No jobs found')
                return
            job_lists = page.locator(".job-list-box .job-card-wrapper").all()       # 获取当前页所有职位
            for job in job_lists:
                if stop_event.is_set():
                    context.close()
                    browser.close()
                    return
                jobinfo = get_job_info(job, jobType)
                if jobinfo is None:
                    continue
                log_info = f"{jobType:^10} - {page_num+1}/{num} - {jobinfo.city:^10} - {jobinfo.company:^25} - {jobinfo.jobname:^35}"
                try:
                    jobinfo.commit_to_db()
                    logger.success(f'Insert data: {log_info}')

                except Exception as e:
                    logger.warning(f'Duplicate data: {log_info}')
                    
                
            page.locator(".ui-icon-arrow-right").click()        # 点击下一页
            if stop_event.is_set():
                context.close()
                browser.close()
                exit()
            page.wait_for_timeout(500)
        page.close()
        context.close()
        browser.close()

def main():
    st.set_page_config(page_title="爬虫工具", page_icon="🕷")
    "#### 数据库爬虫工具"
    
    city_json = json.load(open('metadata/city.json', 'r', encoding='utf-8'))
    cities = []
    for item in city_json["zpData"]["hotCityList"]:
        cities.append(item["name"])
    industries = get_data("SELECT DISTINCT industry FROM job;")['industry'].tolist()
    jobclasses = get_data("SELECT DISTINCT type FROM jobtype;")['type'].tolist()
    
    try:
        with open("cache/last_crawl.json", "r", encoding='utf-8') as f:
            data = json.load(f)
            selected_cities = st.multiselect("城市", cities, default=data['selected_cities'])
            selected_industry = st.selectbox("行业", industries, index=data['selected_industry'])
            selected_jobclass = st.selectbox("职位类别", jobclasses, index=data['selected_jobclass'])
    except:
        selected_cities = st.multiselect("城市", cities, default=['北京'])
        selected_industry = st.selectbox("行业", industries, index=0)
        selected_jobclass = st.selectbox("职位类别", jobclasses, index=0)

    cache_dir = f"cache/{selected_industry}_{selected_jobclass.replace('/', '_')}_{','.join(selected_cities)}"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    positions = get_data(f"select name from jobtype where type='{selected_jobclass}';")['name'].tolist()
    
    if "crawler_process" not in st.session_state:
        st.session_state.crawler_process = None
    
    stop_event = multiprocessing.Event()
    
    if st.button("开始爬取"):
        if st.session_state.crawler_process is not None and st.session_state.crawler_process.is_alive():
            st.warning("爬虫已经在运行中！请先停止当前爬虫。")
        else:
            stop_event.clear()
            with open("cache/last_crawl.json", "w", encoding='utf-8') as f:
                json.dump({'selected_cities': selected_cities, 'selected_industry': industries.index(selected_industry), 
                        'selected_jobclass': jobclasses.index(selected_jobclass)}, f, indent=4, ensure_ascii=False)
                if '全国' in selected_cities:
                    selected_cities = cities[1:]
                iterator = CachedIterator([selected_cities, positions], cache_path=f"{cache_dir}/filter.json")
                total_length = len(iterator)
                accumulated_length = 1 / total_length
                
                if st.button("停止爬虫"):
                    if st.session_state.crawler_process is not None and st.session_state.crawler_process.is_alive():
                        stop_event.set()  # 发送停止信号
                        st.session_state.crawler_process.join()  # 等待进程结束
                        st.session_state.crawler_process = None
                        st.success("爬虫已停止！")
                    else:
                        st.warning("当前没有正在运行的爬虫进程！")
                        
                bar = st.progress(iterator.index * accumulated_length, "正在爬取数据中...")
                for city, position in iterator:
                    logger.info(f'Start crawling: {city} - {position}')
                    request = JobQueryRequest(
                        city=city,
                        jobType='全职',
                        industry=[selected_industry],
                        position=[position],
                    )
                    url = request.to_url()
                    
                    st.session_state.crawler_process = multiprocessing.Process(target=run, args=
                                    (url, position, f"{cache_dir}/page.json", stop_event))
                    st.session_state.crawler_process.start()
                    bar.progress(accumulated_length * min(total_length, (iterator.index)), f"正在爬取 {city} - {position} 的数据 ({iterator.index}/{total_length})")
                    st.session_state.crawler_process.join()
                    
                bar.empty()
        
        
        
if __name__ == '__main__':
    main()