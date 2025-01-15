from playwright.sync_api import Playwright, sync_playwright
from APIDataClass import JobQueryRequest, CachedIterator, JobInfo, cursor, connection
from loguru import logger
import time
import json
import pyautogui
from datetime import datetime
import os

def login(context) -> None:
    page = context.new_page()
    page.goto("https://www.zhipin.com/web/user/?ka=header-login")
    page.get_by_role("link", name=" 微信登录/注册").click()
    
    while True:
        if page.locator('[ka=recommend_search_expand_click]').count():
            break
        time.sleep(1)
    

def get_job_info(job, jobType, allow_duplicate=False) -> JobInfo:
    url = job.locator(".job-card-body > a").get_attribute("href").split('?')[0]       # 获取职位链接
    url = f'https://www.zhipin.com{url}'
    company = job.locator(".company-name").inner_text()                 # 获取公司名
    jobname = job.locator(".job-name").inner_text()                     # 获取职位名
    salary = job.locator(".salary").inner_text()                        # 获取薪资
    address = job.locator(".job-area").inner_text()                     # 获取工作地点
    city = address.split('·')[0]                                        # 获取城市名
    cursor.execute(f"SELECT * FROM job WHERE jobname='{jobname}' AND company='{company}' AND city='{city}'")              # 检查是否重复

    if cursor.rowcount > 0:
        logger.warning(f'Duplicate data!')
        if allow_duplicate:
            job = cursor.fetchone()
            return JobInfo.from_db(jobname, company, city)
        else:
            return None
    
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

def run(broswer, context: Playwright, url, jobType, max_page_num=30) -> None:      # 输入待爬取的网页和职业类型，暂时不获取职业的描述
    with open('cache/page.json', 'r', encoding='utf-8') as f:
        page = json.load(f)["index"]
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
        # context = browser.new_context(viewport={'width': 600, 'height': 400})
        if not os.path.exists('cache/state.json'):
            context = browser.new_context()
            login(context)
            context.storage_state(path="cache/state.json")
        else:
            context = browser.new_context(storage_state="cache/state.json")
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