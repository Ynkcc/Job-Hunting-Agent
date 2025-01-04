import pymysql
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio

# MySQL数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'rebibabo',
    'password': '123456',
    'database': 'jobhunting',
    'charset': 'utf8mb4'
}

def get_job_urls():
    """从数据库中获取待爬取的URL"""
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM job WHERE description IS NULL")  # 仅获取description为空的行
    urls = cursor.fetchall()
    cursor.close()
    conn.close()
    return [url[0] for url in urls]  # 提取出url列，返回列表

def insert_job_description(url, description):
    """将抓取的工作描述插入数据库"""
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE job SET description = %s WHERE url = %s", (description, url))
    conn.commit()
    cursor.close()
    conn.close()

async def fetch_job_description(url, page):
    """使用Playwright抓取网页内容"""
    await page.goto(url)
    await page.wait_for_selector(".job-sec-text")  # 等待页面加载
    html_content = await page.content()
    soup = BeautifulSoup(html_content, "html.parser")
    job_sec_text = soup.select_one(".job-sec-text").get_text(strip=True)  # 提取工作描述
    return job_sec_text

async def process_job(url, page):
    """处理单个职位，获取描述并插入数据库"""
    try:
        description = await fetch_job_description(url, page)
        # 在爬取数据后插入到数据库
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, insert_job_description, url, description)
        print(f"Description for {url} inserted successfully.")
    except Exception as e:
        print(f"Failed to process {url}: {e}")

async def main():
    # 获取待爬取的职位URL
    urls = get_job_urls()

    # 使用async_playwright启动浏览器和页面
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 使用asyncio.gather并发执行多个职位的处理
        tasks = [process_job(url, page) for url in urls]
        await asyncio.gather(*tasks)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
