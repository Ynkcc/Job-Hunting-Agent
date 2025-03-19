from typing import Literal, List

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
                province VARCHAR(20) NOT NULL COMMENT '省份',
                city VARCHAR(20) NOT NULL COMMENT '城市',
                region VARCHAR(20) NOT NULL COMMENT '区域',
                city_id VARCHAR(20) NOT NULL COMMENT '城市代码',
                region_code VARCHAR(20) NOT NULL COMMENT '区域代码/邮编',
                longitude FLOAT NOT NULL COMMENT '经度',
                latitude FLOAT NOT NULL COMMENT '纬度',
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
                type VARCHAR(20) NOT NULL COMMENT '行业类型',
                name VARCHAR(20) NOT NULL COMMENT '岗位名称',
                code VARCHAR(20) NOT NULL COMMENT '行业代码',
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
                type VARCHAR(20) NOT NULL COMMENT '岗位类型',
                name VARCHAR(20) NOT NULL COMMENT '岗位名称',
                code VARCHAR(20) NOT NULL COMMENT '岗位代码',
                description VARCHAR(200) NOT NULL COMMENT '岗位描述',
                PRIMARY KEY (code)
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
                # 检查数据库中是否已存在相同的 code 值
                cursor.execute("SELECT code FROM jobtype WHERE code = %s", (jobtype_code,))
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO jobtype (type, name, code, description)
                        VALUES (%s, %s, %s, %s)
                        ''', (jobtype_type, jobtype_name, jobtype_code, jobtype_description)
                    )
                
    if 'job' not in tables:
        logger.info('创建 job 表')
        cursor.execute('''
            CREATE TABLE job (
                jobname VARCHAR(100) NOT NULL COMMENT '职位名称',
                company VARCHAR(50) NOT NULL COMMENT '公司名称',
                url VARCHAR(500) COMMENT '职位链接',
                salary VARCHAR(20) COMMENT '薪水',
                lsalary SMALLINT COMMENT '最低薪水',
                hsalary SMALLINT COMMENT '最高薪水',
                date DATETIME COMMENT '获取职位时的日期',
                city VARCHAR(20) NOT NULL COMMENT '城市',
                region VARCHAR(20) COMMENT '区域',
                experience VARCHAR(20) COMMENT '工作经验要求',
                degree VARCHAR(20) COMMENT '学历要求',
                address VARCHAR(100) COMMENT '工作地址',
                industry VARCHAR(20) COMMENT '行业',
                jobtype VARCHAR(30) COMMENT '职位类型',
                stage VARCHAR(20) COMMENT '融资阶段',
                scale VARCHAR(30) COMMENT '公司人员规模',
                labels VARCHAR(300) COMMENT '工作技能需求标签',
                specialty VARCHAR(300) COMMENT '职位特长标签',
                description TEXT COMMENT '职位描述',
                bossName VARCHAR(50) COMMENT '招聘人员姓名',
                bossTitle VARCHAR(50) COMMENT '招聘人员职位',
                sent SMALLINT DEFAULT 0 COMMENT '是否已投递简历',
                clicked SMALLINT DEFAULT 0 COMMENT '是否收到回复',
                PRIMARY KEY (jobname, company, city)
            )'''
        )
    
if __name__ == '__main__':
    init()
