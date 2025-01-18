from playwright.sync_api import Playwright, sync_playwright
from APIDataClass import JobQueryRequest, CachedIterator, JobInfo, cursor, connection
from loguru import logger
import time
import json
import pyautogui
from uiautomation import WindowControl
from datetime import datetime
import os

def login(browser):
    if os.path.exists("cache/state.json"):
        context = browser.new_context(storage_state="cache/state.json")
    else:
        context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.zhipin.com/")
    page.wait_for_timeout(1000)
    if page.locator(".header-login-btn[ka=header-login]").count() > 0:  # 没有登录
        page.goto("https://www.zhipin.com/web/user/?ka=header-login")
        page.wait_for_timeout(1000)
        if page.locator(".mini-app-login").count() == 0:
            page.locator(".wx-login-btn").click()       # 选择微信扫码登录
        
        while True:
            if page.locator('.mini-app-login').count() == 0:
                break
            time.sleep(1)
            
        context.storage_state(path="cache/state.json")
    page.close()
    return context
    

def get_job_info(job, jobType='', allow_duplicate=False) -> JobInfo:
    url = job.locator(".job-card-body > a").get_attribute("href").split('?')[0]       # 获取职位链接
    url = f'https://www.zhipin.com{url}'
    company = job.locator(".company-name").inner_text()                 # 获取公司名
    jobname = job.locator(".job-name").inner_text()                     # 获取职位名
    salary = job.locator(".salary").inner_text()                        # 获取薪资
    address = job.locator(".job-area").inner_text()                     # 获取工作地点
    city = address.split('·')[0]                                        # 获取城市名
    cursor.execute(f"SELECT * FROM job WHERE jobname='{jobname}' AND company='{company}' AND city='{city}'")              # 检查是否重复

    if cursor.rowcount > 0 and allow_duplicate:
        logger.warning(f'Get from database!')
        job = cursor.fetchone()
        return JobInfo.from_db(jobname, company, city)
    
    company_info = job.locator(".company-tag-list li").all_inner_texts()        # 获取公司信息
    if len(company_info) == 2:      
        industry = company_info[0]      
        stage = None
        scale = company_info[1]
    elif len(company_info) == 3:
        industry = company_info[0]      # 行业
        stage = company_info[1]         # 融资阶段
        scale = company_info[2]         # 人员规模
    else:
        industry = None
        stage = None
        scale = None
    experience = job.locator(".job-info .tag-list li").all_inner_texts()[0]             # 工作经验要求
    degree = job.locator(".job-info .tag-list li").all_inner_texts()[-1]                # 学历要求
    specialty = job.locator(".info-desc").inner_text()          # 职位特色
    bossTitle = job.locator(".info-public em").inner_text()     # boss职称
    bossName = job.locator(".info-public").inner_text().replace(bossTitle, '')          # boss姓名
    labels = '，'.join(job.locator(".job-card-footer .tag-list li").all_inner_texts())  # 职业标签
    date = datetime.now().strftime('%Y-%m-%d')
    return JobInfo(company, jobType, jobname, city, salary, address, industry, stage, scale, experience, 
                   degree, specialty, bossName, date, bossTitle, labels, url)
    
def startChat(page, file_path):
    page.locator(".btn-container .btn-startchat").click()       # 立即沟通
    page.wait_for_selector("#chat-input")
    input_box = page.locator("#chat-input")
    input_box.fill("您好，我是24届本科生，毕业于华中科技大学，已经拿到了港中文的研究生Offer了，明年9月份入学。我对这个岗位非常感兴趣，可以立即到岗，一周全勤，可连续实习6个月以上，这是我的简历，如果觉得合适的话，欢迎继续沟通，期待您的回复！")
    page.locator(".toolbar-btn-content [type=file]").click()            # 点击发送简历照片
    time.sleep(1)
    openWindow = WindowControl(name='打开')
    openWindow.SwitchToThisWindow()
    openWindow.EditControl(Name='文件名(N):').SendKeys(file_path)
    openWindow.SplitButtonControl(Name='打开(O)').Click()

def run(broswer, context: Playwright, url, jobType, max_page_num=30) -> None:      # 输入待爬取的网页和职业类型，暂时不获取职业的描述
    try:
        with open('cache/page.json', 'r', encoding='utf-8') as f:
            page_index = json.load(f)["index"]
    except:
        page_index = 1
    url = f'{url}&page={page_index}'
    logger.info(f'Start crawling: {url}')
    
    page = context.new_page()
    page.goto(url)
    
    # try:
    #     window_title = browser.contexts[0].pages[0].title()
    #     window = pyautogui.getWindowsWithTitle(window_title)[0]
    #     window.minimize()
    # except:
    #     pass
    
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
    iterator = CachedIterator([list(range(num))], 'cache/page.json')
    for page_num in iterator:
        if page.locator(".job-empty-icon").count() > 0:     # 如果没有职位
            logger.warning('No jobs found')
            return
        job_lists = page.locator(".job-list-box .job-card-wrapper").all()       # 获取当前页所有职位
        for job in job_lists:
            jobinfo = get_job_info(job, jobType)
            if jobinfo is None:
                continue
            log_info = f"{jobType:^10} - {page_num+1}/{num} - {city:^10} - {jobinfo.company:^25} - {jobinfo.jobname:^35}"
            try:
                jobinfo.commit_to_db()
                logger.success(f'Insert data: {log_info}')

            except Exception as e:
                logger.warning(f'Duplicate data: {log_info}')
                
            
        page.locator(".ui-icon-arrow-right").click()        # 点击下一页
        page.wait_for_timeout(500)
    page.close()

if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = login(browser)
        # cities = ['北京', '上海', '广州', '深圳', '杭州', '西安', '苏州', '武汉', '长沙', '成都', '重庆', '南京']
        cities = ['天津', '厦门', '郑州', '济南']
        industry = '互联网'
        jobclass = '互联网/AI'
        jobtype = '全职'
        degrees = ['本科', '硕士', '博士']
        positions = []
        cursor.execute(f"select name from jobtype where type='{jobclass}';")
        for row in cursor.fetchall():
            positions.append(row[0])
        iterator = CachedIterator([cities, positions], 'cache/filter.json')
        for city, position in iterator:
            logger.info(f'Start crawling: {city} - {position}')
            request = JobQueryRequest(
                city=city,
                jobType=jobtype,
                industry=[industry],
                position=[position],
            )
            url = request.to_url()
            run(browser, context, url, jobType=position)
            
        context.close()
        browser.close()