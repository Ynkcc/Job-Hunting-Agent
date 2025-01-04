from typing import Literal, List
from tool import timer
from loguru import logger
import pymysql
import requests
import json
import os
import toml

with open('.streamlit/secrets.toml', 'r') as file:
    data = toml.load(file)['connections']['jobhunting']

config = {
    'host': data['host'],
    'port': data['port'],
    'user': data['username'],
    'password': data['password']
}

connection = pymysql.connect(**config)

cursor = connection.cursor()
    
@timer
def init():
    if not os.path.exists('metadata'):
        logger.info('创建 metadata 目录')
        os.makedirs('metadata')
        
    if not os.path.exists('metadata/city.json'):
        url = "https://www.zhipin.com/wapi/zpCommon/data/city.json"
        response = requests.get(url)
        logger.info('获取城市信息')
        with open('metadata/city.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(response.json(), indent=4, ensure_ascii=False))
        
    if not os.path.exists('metadata/industry.json'):
        url = "https://www.zhipin.com/wapi/zpCommon/data/industry.json"
        response = requests.get(url)
        logger.info('获取行业信息')
        with open('metadata/industry.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(response.json(), indent=4, ensure_ascii=False))
        
    if not os.path.exists('metadata/jobtype.json'):
        url = "https://www.zhipin.com/wapi/zpCommon/data/intern.json"       # 这个是通过main.js代码中，搜索关键词职位类型找到的，通过网络找不到获取intern.json的api接口
        response = requests.get(url)
        logger.info('获取职位类型信息')
        with open('metadata/jobtype.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(response.json(), indent=4, ensure_ascii=False))

    
    cursor.execute("SHOW DATABASES")
    databases = []
    for row in cursor.fetchall():
        databases.append(row[0])

    if 'jobhunting' not in databases:
        logger.info('创建数据库 jobhunting')
        cursor.execute("CREATE DATABASE jobhunting")

    connection.select_db('jobhunting')

    cursor.execute("SHOW TABLES")
    tables = []
    for row in cursor.fetchall():
        tables.append(row[0])
        
    if 'city' not in tables:
        logger.info('创建 city 表')
        cursor.execute('''
            CREATE TABLE city (
                province VARCHAR(20) NOT NULL,
                city VARCHAR(20) NOT NULL,
                region VARCHAR(20) NOT NULL,
                city_id VARCHAR(20) NOT NULL,
                region_code VARCHAR(20) NOT NULL,
                longitude FLOAT NOT NULL,
                latitude FLOAT NOT NULL,
                PRIMARY KEY (province, city, region),
                CHECK (longitude >= -180 AND longitude <= 180),
                CHECK (latitude >= -90 AND latitude <= 90)
            )'''
        )
        
    cursor.execute("SELECT * FROM city")
    if cursor.rowcount == 0:
        logger.info('插入城市信息')
        with open('metadata/city.json', 'r', encoding='utf-8') as f:
            province_list = json.load(f)["zpData"]["cityList"]
        for province in province_list:
            province_name = province["name"]
            for city in province["subLevelModelList"]:
                city_name = city["name"]
                city_id = city["code"]
                if not city["subLevelModelList"]:
                    continue
                for region in city["subLevelModelList"]:
                    region_name = region["name"]
                    region_code = region["regionCode"]
                    region_center_geo = region["centerGeo"]
                    longitude = region_center_geo.split(",")[0]
                    latitude = region_center_geo.split(",")[1]
                    cursor.execute('''
                        INSERT INTO city (province, city, region, city_id, region_code, longitude, latitude)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (province_name, city_name, region_name, city_id, region_code, longitude, latitude)
                    )
                    
    if 'industry' not in tables:
        logger.info('创建 industry 表')
        cursor.execute('''
            CREATE TABLE industry (
                type VARCHAR(20) NOT NULL,
                name VARCHAR(20) NOT NULL,
                code VARCHAR(20) NOT NULL,
                PRIMARY KEY (code)
            )'''
        )
        
    cursor.execute("SELECT * FROM industry")
    if cursor.rowcount == 0:
        logger.info('插入行业信息')
        with open('metadata/industry.json', 'r', encoding='utf-8') as f:
            industry_list = json.load(f)["zpData"]
        for industry in industry_list:
            industry_type = industry["name"]
            for sub_industry in industry["subLevelModelList"]:
                industry_name = sub_industry["name"]
                industry_code = sub_industry["code"]
                cursor.execute('''
                    INSERT INTO industry (type, name, code)
                    VALUES (%s, %s, %s)
                    ''', (industry_type, industry_name, industry_code)
                )
        
    if 'jobtype' not in tables:
        logger.info('创建 jobtype 表')
        cursor.execute('''
            CREATE TABLE jobtype (
                type VARCHAR(20) NOT NULL,
                name VARCHAR(20) NOT NULL,
                code VARCHAR(20) NOT NULL,
                description VARCHAR(200) NOT NULL
            )'''
        )
        
    cursor.execute("SELECT * FROM jobtype")
    if cursor.rowcount == 0:
        logger.info('插入职位类型信息')
        with open('metadata/jobtype.json', 'r', encoding='utf-8') as f:
            jobtype_list = json.load(f)["zpData"]
        for jobtype in jobtype_list:
            jobtype_type = jobtype["name"]
            for sub_jobtype in jobtype["subList"]:
                jobtype_name = sub_jobtype["name"]
                jobtype_code = sub_jobtype["positionCode"]
                jobtype_description = sub_jobtype["level2Description"]
                cursor.execute('''
                    INSERT INTO jobtype (type, name, code, description)
                    VALUES (%s, %s, %s, %s)
                    ''', (jobtype_type, jobtype_name, jobtype_code, jobtype_description)
                    )
                
    if 'job' not in tables:
        logger.info('创建 job 表')
        cursor.execute('''
            CREATE TABLE job (
                jobname VARCHAR(100) NOT NULL,
                company VARCHAR(50) NOT NULL,
                url VARCHAR(500) NOT NULL,
                salary VARCHAR(20),
                lsalary SMALLINT,
                hsalary SMALLINT,
                date DATETIME,
                city VARCHAR(20) NOT NULL,
                region VARCHAR(20),
                experience VARCHAR(20),
                degree VARCHAR(20),
                address VARCHAR(100),
                industry VARCHAR(20),
                jobtype VARCHAR(30),    
                stage VARCHAR(20),
                scale VARCHAR(30),
                labels VARCHAR(300),
                specialty VARCHAR(300),
                description TEXT,
                bossName VARCHAR(50),
                bossTitle VARCHAR(50),
                sent BOOLEAN DEFAULT FALSE,
                reply BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (jobname, company, city)
            )'''
        )
    
if __name__ == '__main__':
    init()
