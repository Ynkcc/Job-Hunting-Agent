from APIDataClass import cursor
from openai import OpenAI, Embedding
from typing import List, Dict, Literal, TypeAlias
from langchain_community.document_loaders import PyMuPDFLoader
from APIDataClass import JobInfo, select_jobinfo_from_db
from tqdm import trange
import numpy as np
import fitz  # pip install PyMuPDF
import re
import os
LLM = OpenAI()
Message: TypeAlias = Dict[Literal["role", "content"], str]

def get_response(messages: List[Message], 
    model: str = "gpt-4o-mini-2024-07-18", 
    temperature: float = 0.5, 
    max_tokens: int = 2000, 
) -> str:
    ''' Query OpenAI API to generate a response to a given input. '''
    completion = LLM.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,  
        temperature=temperature
    )

    return completion.choices[0].message.content

def get_embedding(text, model="text-embedding-ada-002"):
    response = openai.Embedding.create(
        input=text,
        model=model
    )
    return response['data'][0]['embedding']

class ResumeLoader:
    def __init__(self, file_path):
        self.file_path = file_path
        file_name = os.path.basename(file_path)
        self.cache_dir = f"cache/resume/{file_name}"
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
    @property
    def content(self):
        content_file_path = os.path.join(self.cache_dir, 'content.txt')
        if os.path.exists(content_file_path):
            with open(content_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            loader = PyMuPDFLoader(self.file_path)
            pages = loader.load()
            content = ''
            for page in pages:
                content += page.page_content
            
            with open(os.path.join(self.cache_dir, 'content.txt'), 'w', encoding='utf-8') as f:
                f.write(content)
            return content
                
    @property
    def summary(self, max_length=2048):
        summary_file_path = os.path.join(self.cache_dir,'summary.md')
        if os.path.exists(summary_file_path):
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            prompt = (
                "请你根据用户的简历，生成简历摘要，要求提取出以下内容"
                "1. 教育背景，包括学校以及专业"
                "2. 工作经验，即工作时间为几年"
                "3. 工作技能，从校内、实习、工作项目、经历或其他地方提取出掌握的所有技能"
                "4. 对每一个项目进行总结"
                "输出格式要求：按照markdown格式输出，只输出摘要，不要返回其他内容"
                "用户简历\n{content}"
            )
            messages = [
                {"role": "system", "content": "你是一个智能的简历生成助手，能够根据用户的简历生成简历摘要。"},
                {"role": "user", "content": prompt.format(content=self.content)},
            ]
            response = get_response(messages, max_tokens=max_length)
            with open(os.path.join(self.cache_dir,'summary.txt'), 'w', encoding='utf-8') as f:
                f.write(response)
            return response
        
    @property
    def embedding_vector(self):
        embedding_file_path = os.path.join(self.cache_dir, 'embedding.npy')
        if not os.path.exists(embedding_file_path):
            embedding = get_embedding(self.content)
            np.save(embedding_file_path, embedding)
        return np.load(embedding_file_path)
    
    @property
    def picture_path(self):
        imagePath = os.path.join(self.cache_dir, 'images')
        if not os.path.exists(imagePath):  # 判断存放图片的文件夹是否存在
            os.makedirs(imagePath)  # 若图片文件夹不存在就创建
            pdfDoc = fitz.open(self.file_path)
            for pg in range(pdfDoc.page_count):
                page = pdfDoc[pg]
                rotate = int(0)
                # 每个尺寸的缩放系数为1.3，这将为我们生成分辨率提高2.6的图像。
                # 此处若是不做设置，默认图片大小为：792X612, dpi=96
                zoom_x = 3 
                zoom_y = 3
                mat = fitz.Matrix(zoom_x, zoom_y).prerotate(rotate)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                pix.save(f"{imagePath}/CV_{pg}.png")
            pdfDoc.close()
        return [os.path.abspath(os.path.join(imagePath, f)) for f in os.listdir(imagePath)] if os.path.exists(imagePath) else []

class GPTRanker:
    def __init__(self, jobinfo: List[JobInfo], cv_path: str):
        self.jobinfo = jobinfo
        self.jobs = [(i, job.description) for i, job in enumerate(jobinfo)]
        self.cv = ResumeLoader(cv_path).summary
        
    def batch_ranker(
        self,
        jobs: tuple[int, str],     
        model: str = "gpt-4o-mini-2024-07-18", 
        temperature: float = 0.5, 
    ) -> List[int]:
        ''' Query OpenAI API to generate a response to a given input. '''
        
        num = len(jobs)
        messages = [
            {"role": "system", "content": "你是一个智能的排序助手，能够根据用户的个人简历，对招聘岗位进行匹配度排名，排名依据包括但不限于学历要求、工作经验、技能、项目经历、工作经历等。"},
            {"role": "user", "content": f"我将提供给你{num}个招聘岗位信息，每一个岗位通过数字和[]标识，根据简历对岗位需求的匹配程度来进行排序"},
            {"role": "assistant", "content": "好的，请提供各个岗位"},
        ]
        
        for i, job in jobs:
            messages.append({"role": "user", "content": f"[{i}] {job}"})
            messages.append({"role": "assistant", "content": f"收到岗位[{i}]"})
            
        messages.append({"role": "user", "content": f"用户个人简历如下\n{self.cv}"})
        messages.append({"role": "assistant", "content": "收到简历"})
        messages.append({"role": "user", "content": f"请根据用户个人简历对上面{num}个招聘岗位进行匹配度排名，岗位需要使用他们的标识符按照降序排列，最相关的岗位应该排在前面，输出的格式应该是 [] > [], eg., [0] > [2]。只要回答排名结果，不要解释任何理由。"})
            
        response = get_response(messages, model, temperature)
        
        ans = []
        for each in response.split(">"):
            pattern = r"\[(\d+)\]"
            numbers = re.findall(pattern, each)
            if len(numbers) == 1:
                ans.append(int(numbers[0]))
            else:
                return []
        return ans
        
    def rank(self, 
        window_length=4, 
        step=2,
        model: str = "gpt-4o-mini-2024-07-18", 
    ) -> List[JobInfo]:
        ans = []

        left = max(len(self.jobs)-window_length, 0)
        batch_jobs = self.jobs[left+step:] 

        while left >= 0:
            left = max(left, 0)
            batch_jobs.extend(self.jobs[left:left+step])
            for _ in range(3):
                rank = self.batch_ranker(batch_jobs, model=model)
                if rank:
                    print(rank)
                    break
            if not rank:
                print("Max retries reached, skipping...")
                continue
            i = step
            while i > 0 and rank:
                ans.append(rank.pop())
                i -= 1
            left -= step
            batch_jobs = [self.jobs[i] for i in rank]

        while batch_jobs:
            ans.append(batch_jobs.pop()[0])

        return [self.jobinfo[i] for i in ans[::-1] if 0<=i<len(self.jobinfo)]

class GPTFilter:
    def __init__(self, jobinfo: List[JobInfo], query: str):
        self.jobinfo = jobinfo
        self.query = query
        
    def batch_filter(
        self,
        batch_job: List[JobInfo],
        model: str = "gpt-4o-mini-2024-07-18", 
        temperature: float = 0.5, 
    ) -> List[JobInfo]:
        num = len(batch_job)
        messages = [
            {"role": "system", "content": "你是一个智能的职位筛选助手，能够根据用户的要求，筛选掉不符合要求的简历，包括实习/全职、学历要求、岗位要求、公司要求、地点要求等。"},
            {"role": "user", "content": f"我将提供给你{num}个招聘岗位信息，每一个岗位通过数字和[]标识，根据用户的要求，筛选出符合要求的岗位列表。"},
            {"role": "assistant", "content": "好的，请提供各个岗位信息。"},
        ]
        for i, jobinfo in enumerate(batch_job):
            job_text = (f"[{i}]\n工作名称：{jobinfo.jobname}\n公司名称：{jobinfo.company}\n工作地点：{jobinfo.address}\n薪资范围：{jobinfo.salary}\n"
                    f"经验要求：{jobinfo.experience}\n学历要求：{jobinfo.degree}\n标签：{jobinfo.labels}\n行业：{jobinfo.industry}\n"
                    f"融资状态：{jobinfo.stage}\n人员规模：{jobinfo.scale}")
            messages.append({"role": "user", "content": f"[{i}]\n{job_text}"})
            messages.append({"role": "assistant", "content": f"收到岗位[{i}]"})

        messages.append({"role": "user", "content": f"用户要求：{self.query}"})
        messages.append({"role": "assistant", "content": "收到!"})
        messages.append({"role": "user", "content": f"请根据用户个人简历对上面{num}个招聘岗位进行筛选，返回符合条件的岗位列表，输出的格式应该是 [a, b, c], eg., [0, 3, 5]。只要回答岗位列表，不要解释任何理由。"})

        response = get_response(messages, model, temperature)
        try:
            indices = eval(response)
            return [batch_job[i] for i in indices]
        except:
            print(f"Wrong response format: {response}")
            return None

    def filter(self, batch_size: int=16, model: str = "gpt-4o-mini-2024-07-18", temperature: float = 0.5) -> List[JobInfo]:
        ans = []
        for i in trange(0, len(self.jobinfo), batch_size):
            for _ in range(3):
                batch_job = self.jobinfo[i:i+batch_size]
                selected_job = self.batch_filter(batch_job, model=model, temperature=temperature)
                if selected_job:
                    ans.extend(selected_job)
                    break
            if selected_job is None:
                print("Max retries reached, skipping...")
                continue
        return ans
            

class Metrics:
    def __init__(self, relevance: List[int]):
        self.relevance = np.array(relevance)
        
    def getNDCG(self, k=100):
        ''' Calculate NDCG@k for a given click list. '''
        k = min(k, len(self.relevance))
        relevance = self.relevance[:k]     # 0/1表示是否点击或者是否发送简历
        weights = 1 / np.log2(np.arange(2, k+2))  # 计算权重
        dcg = np.sum(relevance * weights)
        idcg = np.sum(np.sort(relevance)[::-1] * weights)
        return dcg / idcg if idcg != 0 else 0
        
    def getHitRatio(self, k=100):
        ''' Calculate click rate@k for a given click list. '''
        k = min(k, len(self.relevance))
        return sum(self.relevance[:k]) / k
    
    def getMAP(self):
        ''' Calculate mean average precision for a given click list. '''
        relevant_map = {}
        rank = 1
        for i in range(len(self.relevance)):
            if self.relevance[i] == 1:
                relevant_map[rank] = i+1
                rank += 1
        map_score = sum([rank / idx for rank, idx in relevant_map.items()])
        return map_score / len(relevant_map) if len(relevant_map) != 0 else 0


if __name__ == '__main__':
    cv_path = 'CV-zh.pdf'
    # jobinfo = select_jobinfo_from_db("SELECT * from job where description is not null limit 10;")
    # ranker = GPTRanker(jobinfo, cv_path)
    # for each in ranker.rank():
    #     print(each)
    loader = ResumeLoader(cv_path)
    print(loader.picture_path)