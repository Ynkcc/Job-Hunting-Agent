from playwright.sync_api import Playwright, sync_playwright
from APIDataClass import JobQueryRequest, CachedIterator, cursor, connection
from datetime import datetime
import pymysql
from loguru import logger
import time
import json
import pyautogui

def login(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.zhipin.com/web/user/?ka=header-login")
    page.get_by_role("link", name=" 微信登录/注册").click()
    
    while True:
        if page.locator('[ka=recommend_search_expand_click]').count():
            break
        time.sleep(1)
    
    print("登录成功")
    
    # ---------------------
    context.close()
    browser.close()

def run(playwright: Playwright, url, jobType, max_num=30) -> None:      # 输入待爬取的网页和职业类型，暂时不获取职业的描述
    with open('cache/page.json', 'r', encoding='utf-8') as f:
        page = json.load(f)["index"]
    url = f'{url}&page={page}'
    logger.info(f'Start crawling: {url}')
    browser = playwright.chromium.launch(headless=False)
    
    context = browser.new_context(viewport={'width': 600, 'height': 400})
    page = context.new_page()
    page.goto(url)
    
    window_title = browser.contexts[0].pages[0].title()
    window = pyautogui.getWindowsWithTitle(window_title)[0]
    window.minimize()
    
    max_time = 10
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
    
    
    num = min(max_num, int(page.locator(".options-pages a").all_inner_texts()[-2]))     # 获取最大页数
    iterator = CachedIterator([list(range(num))], 'cache/page.json')
    for page_num in iterator:
        if page.locator(".job-empty-icon").count() > 0:     # 如果没有职位
            logger.warning('No jobs found')
            return
        job_lists = page.locator(".job-list-box .job-card-wrapper").all()       # 获取当前页所有职位
        for job in job_lists:
            url = job.locator(".job-card-body > a").get_attribute("href")       # 获取职位链接
            url = f'https://www.zhipin.com{url}'
            company = job.locator(".company-name").inner_text()                 # 获取公司名
            jobname = job.locator(".job-name").inner_text()                     # 获取职位名
            salary = job.locator(".salary").inner_text()                        # 获取薪资
            address = job.locator(".job-area").inner_text()                     # 获取工作地点
            city = address.split('·')[0]                                        # 获取城市名
            log_info = f"{jobType:^10} - {page_num+1}/{num} - {city:^10} - {company:^25} - {jobname:^35}"
            cursor.execute(f"SELECT * FROM job WHERE url='{url}' AND company='{company}' and salary='{salary}'")        # 检查是否重复
            if cursor.rowcount > 0:
                logger.warning(f'Duplicate data: {log_info}')
                continue
            
            try:
                if '面议' in salary or '天' in salary:      # 计算不准确薪资，跳过
                    continue
                else:
                    if '薪' in salary:
                        months = int(salary.split('·')[1][:-1])     # 月薪 * (12 - 18)
                    else:
                        months = 12
                    if 'K' in salary:       # 薪资单位为K
                        prefix = salary.split('K')[0]
                        lsalary = int(prefix.split('-')[0])*months//10      # 最低薪资
                        hsalary = int(prefix.split('-')[1])*months//10      # 最高薪资
                    elif '元' in salary:    # 薪资单位为元
                        prefix = salary.split('元')[0]
                        lsalary = int(prefix.split('-')[0])*months//10000
                        hsalary = int(prefix.split('-')[1])*months//10000
                    else:
                        continue
            except:
                continue
            time = datetime.now().strftime('%Y-%m-%d')
            
            if '·' in address:      # 如果还细分了地区
                region = address.split('·')[1]
            else:
                region = None
            
            campany_info = job.locator(".company-tag-list li").all_inner_texts()        # 获取公司信息
            if len(campany_info) == 2:      
                industry = campany_info[0]      
                stage = None
                scale = campany_info[1]
            elif len(campany_info) == 3:
                industry = campany_info[0]      # 行业
                stage = campany_info[1]         # 融资阶段
                scale = campany_info[2]         # 人员规模
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
            try:
                cursor.execute(f'''
                    INSERT INTO job (
                            jobType, company, url, jobname, salary, lsalary, hsalary, date, address, city, region, industry, 
                            stage, scale, experience, degree, specialty, bossName, bossTitle, labels) 
                        VALUES 
                        ('{jobType}', '{company}', '{url}', '{jobname}', '{salary}', '{lsalary}', '{hsalary}', '{time}', '{address}', 
                        '{city}', '{region}', '{industry}', '{stage}', '{scale}', '{experience}', '{degree}', 
                        '{specialty}', '{bossName}', '{bossTitle}', '{labels}')'''
                )
                connection.commit()
                logger.success(f'Insert data: {log_info}')
            except pymysql.err.IntegrityError:      # 插入元素不满足唯一性约束
                logger.warning(f'Duplicate data: {log_info}')
            
            
        page.locator(".ui-icon-arrow-right").click()        # 点击下一页
        page.wait_for_timeout(1000)
    
    context.close()
    browser.close()


with sync_playwright() as playwright:
    cities = ['北京', '上海', '广州', '深圳', '杭州', '西安', '苏州', '武汉', '长沙', '成都', '重庆', '南京']
    industry = '互联网/AI'
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
        try:
            run(playwright, url, jobType=position)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f'Error: {e}')