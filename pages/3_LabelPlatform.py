from logging import log
import streamlit as st
from crawl import get_job_info, login
from playwright.sync_api import Playwright, sync_playwright
from APIDataClass import JobInfo, JobQueryRequest, cursor, connection
import streamlit.components.v1 as components
from loguru import logger
from JobRender import render
import pandas as pd
import json
import multiprocessing
import pyautogui
import os
import time

st.set_page_config(page_title="数据标注平台", page_icon="🏷️", layout="wide")

@st.cache_data
def get_data(query):
    cursor.execute(query)
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=[desc[0] for desc in cursor.description])
    return df

def crawling_thread(job_queue, jobType, url, output_file):
    with sync_playwright() as playwright, open(output_file, 'a', encoding='utf-8') as f:
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
        
        # window_title = browser.contexts[0].pages[0].title()
        # window = pyautogui.getWindowsWithTitle(window_title)[0]
        # window.minimize()
        
        num = min(int(page.locator(".options-pages a").all_inner_texts()[-2]), 10)
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
                jobinfo = get_job_info(job, jobType)
                if jobinfo is None:
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
                try:
                    page2.wait_for_selector(".look-job-box .look-job-list a", timeout=10000)
                except:
                    continue
                other_related_jobs = page2.locator(".look-job-box .look-job-list a").all()
                urls = []
                for related_job in other_related_jobs:
                    related_job_url = f'https://www.zhipin.com{related_job.get_attribute("href")}'
                    urls.append(related_job_url)
                jobinfo.description = description
                job_queue.put(jobinfo)
                try:
                    jobinfo.commit_to_db()
                except Exception as e:
                    logger.error(f"Failed to commit to db: {e}")
                data = {"jobname": jobinfo.jobname, "company": jobinfo.company, "city": jobinfo.city, "url": jobinfo.url, "related_jobs": urls}
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
                time.sleep(0.5)
                
            job_queue.put((i, num))
            page.locator(".ui-icon-arrow-right").click()        # 点击下一页
            time.sleep(0.5)
        job_queue.put(None)      # 最后一个元素为最大页数
        context.close()
        browser.close()
        
def main():
    jobtypes = get_data("SELECT DISTINCT name FROM jobtype;")['name'].tolist()
    city_json = json.load(open('metadata/city.json', 'r', encoding='utf-8'))
    provinces = []
    for item in city_json["zpData"]["cityList"]:
        provinces.append(item["name"])
    industries = get_data("SELECT DISTINCT name FROM industry;")['name'].tolist()
    degrees = list(JobQueryRequest.degree_map.keys())
    experiences = list(JobQueryRequest.experience_map.keys())
    scales = list(JobQueryRequest.scale_map.keys())
    stages = list(JobQueryRequest.stage_map.keys())

    selected_province = st.sidebar.selectbox(
        "请选择省份",
        options=['不限'] + provinces,
        index=1
    )
    
    if selected_province == '不限':
        cities = []
    else:
        for item in city_json["zpData"]["cityList"]:
            if item["name"] == selected_province:
                cities = [city["name"] for city in item["subLevelModelList"]]
                break

    selected_city = st.sidebar.selectbox(
        "请选择城市",
        options=['不限'] + cities,
        index=1 if cities else 0
    )

    if selected_city == '不限':
        regions = []
    else:
        for item in city_json["zpData"]["cityList"]:
            if item["name"] == selected_province:
                for subitem in item["subLevelModelList"]:
                    if subitem["name"] == selected_city:
                        regions = [region["name"] for region in subitem["subLevelModelList"]]
                        break
                break

    selected_region = st.sidebar.selectbox("请选择区域", options=['不限'] + regions, index=0)
    selected_jobtype = st.sidebar.multiselect("请选择职位类型", options=['不限'] + jobtypes, default=['不限'])
    selected_industry = st.sidebar.multiselect("请选择行业", options=['不限'] + industries, default=['互联网'])
    selected_degree = st.sidebar.multiselect("请选择学历", options=['不限'] + degrees, default=['不限'])
    selected_experience = st.sidebar.multiselect("请选择经验要求", options=['不限'] + experiences, default=['不限'])
    selected_scale = st.sidebar.multiselect("请选择人员规模", options=['不限'] + scales, default=['不限'])
    selected_stage = st.sidebar.multiselect("请选择公司融资阶段", options=['不限'] + stages, default=['不限'])

    # 在第一个列中添加文本输入框
    keyword = st.text_input("请输入搜索关键词", placeholder='例如：数据分析')
    
    TotalJobInfo = []
    
    if not os.path.exists('cache/dataset/'):
        os.makedirs('cache/dataset/')
    output_dirs = os.listdir('cache/dataset/')
    selected_file_or_new = st.selectbox(
        "加载已有数据集或输入新数据集名称：",
        options=["<输入新数据集名称>"] + output_dirs
    )
    if selected_file_or_new == "<输入新数据集名称>":
        new_dataset_name = st.text_input("请输入想要保存的数据集名称：", placeholder='例如：original')
        if new_dataset_name:
            if new_dataset_name in output_dirs:
                st.warning("数据集已存在！")
            output_file = f'cache/dataset/{new_dataset_name}/raw_data.jsonl'
            if st.button("提交"):
                bar = st.progress(0, "正在获取职位信息，请稍候...")
                
                request = JobQueryRequest(
                    city=selected_city if '不限' not in selected_city else '',
                    areaBusiness=selected_region if '不限' != selected_region else '',
                    position=selected_jobtype if '不限' not in selected_jobtype else [],
                    industry=selected_industry if '不限' != selected_industry else [],
                    degree=selected_degree if '不限' not in selected_degree else [],
                    experience=selected_experience if '不限' not in selected_experience else [],
                    scale=selected_scale if '不限' not in selected_scale else [],
                    stage=selected_stage if '不限' not in selected_stage else [],
                    keyword=keyword
                )
                url = request.to_url()
                job_buffer = multiprocessing.Queue()
                writer_process = multiprocessing.Process(target=crawling_thread, args=(job_buffer, request.jobType, url, output_file))
                writer_process.start()
                
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
    else:
        with open(f'cache/dataset/{selected_file_or_new}/raw_data.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                jobinfo = JobInfo.from_db(city=data['city'], company=data['company'], jobname=data['jobname'])
                TotalJobInfo.append(jobinfo)
    
    

    render(TotalJobInfo)
        
    
if __name__ == '__main__':
    main()