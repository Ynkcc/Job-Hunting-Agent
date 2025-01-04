from tool import timer
import pymysql
from typing import List
import itertools
import os
import json
from loguru import logger
import toml

with open('.streamlit/secrets.toml', 'r') as file:
    data = toml.load(file)

config = {
    'host': data['mysql']['host'],
    'port': data['mysql']['port'],
    'user': data['mysql']['username'],
    'password': data['mysql']['password'],
    'database': data['mysql']['database']
}

connection = pymysql.connect(**config)

cursor = connection.cursor()

class JobQueryRequest:
    query = ''          # 搜索关键词
    city = ''           # 城市名称
    experience = ''     # 经验要求
    degree = ''         # 学历要求
    industry = ''       # 行业
    jobType = ''        # 全职/兼职 
    scale = ''          # 公司人员规模
    stage = ''          # 融资情况
    position = ''       # 职位类型
    salary = ''         # 薪资范围
    areaBusiness = ''   # 区域商圈
    
    def __init__(self,
                 keyword: str='',
                 city: str='',
                 experience: List[str]=[],
                 degree: List[str]=[],
                 industry: List[str]=[],
                 scale: List[str]=[],
                 stage: List[str]=[],
                 position: List[str]=[],
                 jobType: str='',       # 兼职、全职
                 salary: str='',    
                 areaBusiness: str='',
        ):
        jobType_map = {'全职': '1901', '兼职': '1903'}
        self.jobType = jobType_map.get(jobType, '')
        
        expereince_map = {'经验不限': '101', '应届生': '102', '1年以内': '103', '1-3年': '104', '3-5年': '105', '5-10年': '106', '10年以上': '107', '在校生': '108'}
        expereinces = []
        for exp in experience:
            exp_id = expereince_map.get(exp, '')
            if exp_id:
                expereinces.append(exp_id)
        self.experience = ','.join(expereinces)
        
        salary_map = {'3K以下': '402', '3-5K': '403', '5-10K': '404', '10-20K': '405', '20-50K': '406', '50K以上': '407'}
        self.salary = salary_map.get(salary, '')
        
        degrees = ['', '不限', '初中及以下', '中专/中技', '高中', '大专', '本科', '硕士', '博士']
        
        degree_map = {'初中及以下': '209', '中专/中技': '208', '高中': '206', '大专': '202', '本科': '203', '硕士': '204', '博士': '205'}
        degrees = []
        for deg in degree:
            deg_id = degree_map.get(deg, '')
            if deg_id:
                degrees.append(deg_id)
        self.degree = ','.join(degrees)
        
        scale_map = {'0-20人': '301', '20-99人': '302', '100-499人': '303', '500-999人': '304', '1000-9999人': '305', '10000人以上': '306'}
        scales = []
        for sc in scale:
            sc_id = scale_map.get(sc, '')
            if sc_id:
                scales.append(sc_id)
        self.scale = ','.join(scales)
        
        stage_map = {'未融资': '801', '天使轮': '802', 'A轮': '803', 'B轮': '804', 'C轮': '805', 'D轮及以上': '806', '已上市': '807', '不需要融资': '808'}
        stages = []
        for st in stage:
            st_id = stage_map.get(st, '')
            if st_id:
                stages.append(st_id)
        self.stage = ','.join(stages)
        
        self.query = keyword
        
        jobs = []
        for job in position:
            cursor.execute("SELECT DISTINCT code FROM jobtype WHERE name=%s", job)
            if cursor.rowcount:
                jobs.append(cursor.fetchone()[0])
        self.position = ','.join(jobs)
        
        cursor.execute("SELECT DISTINCT city_id FROM city WHERE city=%s", city)
        if cursor.rowcount:
            self.city = cursor.fetchone()[0]
        else:
            self.city = '100010000'     # 全国
        
        if areaBusiness:
            cursor.execute("SELECT DISTINCT region_code FROM city WHERE city=%s AND region=%s", (city, areaBusiness))
            if cursor.rowcount:
                self.areaBusiness = cursor.fetchone()[0]
                
        industries = []
        for industry in industry:
            cursor.execute("SELECT DISTINCT code FROM industry WHERE name=%s", industry)
            if cursor.rowcount:
                industries.append(cursor.fetchone()[0])
        self.industry = ','.join(industries)
                    
    def to_dict(self):
        return self.__dict__
    
    def to_url(self):
        base_url = "https://www.zhipin.com/web/geek/job?"
        params = '&'.join([f'{k}={v}' for k, v in self.to_dict().items() if v])
        return base_url + params
    
class CachedIterator:
    def __init__(self, arrays, cache_path=None):
        """
        :param arrays: 输入的数组列表，例如 [a, b, c]。
        :param cache_path: 缓存文件路径，用于保存和加载索引。
        """
        self.arrays = arrays
        self.cache_path = cache_path

        # 使用范围生成索引组合
        self.combinations = list(itertools.product(*[range(len(arr)) for arr in arrays]))
        self.index = 0  # 当前主索引
        self.array_indices = [
            {"index": 0, "value": arr[0]} if arr else {"index": 0, "value": None}
            for arr in arrays
        ]

        # 如果缓存路径存在，则加载索引
        if cache_path and os.path.exists(cache_path):
            self._load_cache()

    def _load_cache(self):
        """加载缓存文件中的索引"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                if "index" in cache_data and "array_indices" in cache_data:
                    self.index = cache_data["index"]
                    self.array_indices = cache_data["array_indices"]
                else:
                    logger.warning("缓存数据无效，重新从 0 开始。")
        except (json.JSONDecodeError, IOError):
            logger.warning("缓存文件无效，重新从 0 开始。")

    def _save_cache(self):
        """保存当前索引到缓存文件"""
        if self.cache_path:
            if not os.path.exists(os.path.dirname(self.cache_path)):
                os.makedirs(os.path.dirname(self.cache_path))
            cache_data = {
                "index": self.index,
                "array_indices": self.array_indices
            }
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=4, ensure_ascii=False)

    def __iter__(self):
        return self

    def __next__(self):
        """返回下一个元组，并更新缓存"""
        if self.index < len(self.combinations):
            current_indices = self.combinations[self.index]
            result = []

            for i, idx in enumerate(current_indices):
                value = self.arrays[i][idx]
                self.array_indices[i] = {"index": idx, "value": value}
                result.append(value)

            self._save_cache()
            self.index += 1
            if len(result) == 1:
                return result[0]
            else:
                return tuple(result)
        else:
            self.clear()
            raise StopIteration    
        
    def clear(self):
        self.index = 0
        self.array_indices = [
            {"index": 0, "value": arr[0]} if arr else {"index": 0, "value": None}
            for arr in self.arrays
        ]
        self._save_cache()
        
    def get_index(self):
        return self.index

    
if __name__ == '__main__':
    # request = JobQueryRequest(
    #     keyword='大模型',
    #     city='深圳',
    #     degree=['本科'],
    #     industry=['互联网'],
    #     position=['数据挖掘'],
    #     jobType='全职',
    # )
    request = JobQueryRequest(position=['数据开发'])
    print(request.to_dict())
    print(request.to_url())
    