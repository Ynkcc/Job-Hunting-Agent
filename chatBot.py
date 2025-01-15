# from langchain_community.document_loaders import PDFMinerPDFasHTMLLoader
# from langchain_community.docstore.document import Document
# from bs4 import BeautifulSoup
# from copy import deepcopy
# import re

# loader = PDFMinerPDFasHTMLLoader('CV-zh.pdf')
# data = loader.load()[0]
# # with open('CV.html', 'w', encoding='utf-8') as f:
# #     f.write(data.page_content)

# soup = BeautifulSoup(data.page_content,'html.parser')
# content = soup.find_all('span')

# cur_fs = None
# cur_text = ''
# snippets = []   # first collect all snippets that have the same font size
# for c in content:
#     st = c.get('style')
#     if not st:
#         continue
#     fs = re.findall('font-size:(\d+)px',st)
#     if not fs:
#         continue
#     fs = int(fs[0])
#     if not cur_fs:
#         cur_fs = fs
#     if fs == cur_fs:
#         cur_text += c.text
#     else:
#         snippets.append((cur_text,cur_fs))
#         cur_fs = fs
#         cur_text = c.text
# snippets.append((cur_text,cur_fs))

# # from langchain.docstore.document import Document
# # cur_idx = -1
# # semantic_snippets = []
# # # Assumption: headings have higher font size than their respective content
# # for s in snippets:
# #     # if current snippet's font size > previous section's heading => it is a new heading
# #     if not semantic_snippets or s[1] > semantic_snippets[cur_idx].metadata['heading_font']:
# #         metadata={'heading':s[0], 'content_font': 0, 'heading_font': s[1]}
# #         metadata.update(data.metadata)
# #         semantic_snippets.append(Document(page_content='',metadata=metadata))
# #         cur_idx += 1
# #         continue
    
# #     # if current snippet's font size <= previous section's content => content belongs to the same section (one can also create
# #     # a tree like structure for sub sections if needed but that may require some more thinking and may be data specific)
# #     if not semantic_snippets[cur_idx].metadata['content_font'] or s[1] <= semantic_snippets[cur_idx].metadata['content_font']:
# #         semantic_snippets[cur_idx].page_content += s[0]
# #         semantic_snippets[cur_idx].metadata['content_font'] = max(s[1], semantic_snippets[cur_idx].metadata['content_font'])
# #         continue
    
# #     # if current snippet's font size > previous section's content but less tha previous section's heading than also make a new 
# #     # section (e.g. title of a pdf will have the highest font size but we don't want it to subsume all sections)
# #     metadata={'heading':s[0], 'content_font': 0, 'heading_font': s[1]}
# #     metadata.update(data.metadata)
# #     semantic_snippets.append(Document(page_content='',metadata=metadata))
# #     cur_idx += 1

# class PdfLevelContent:
#     def __init__(self, title, title_font, **kwargs):
#         self.content_font = 0
#         self.titles = [title]
#         self.level = 0
#         self.title_fonts = [title_font]
#         self.additional_metadata = kwargs
#         self.page_content = ''
#         self.spans = []
        
#     @property
#     def metadata(self):
#         metadata = dict({
#             'content_font': self.content_font,
#             'level': self.level
#         })
#         metadata.update(self.additional_metadata)
#         for level in range(self.level+1):
#             metadata[f'{"sub"*level}title'] = self.titles[level]
#             metadata[f'{"sub"*level}title_font'] = self.title_fonts[level]
#         return metadata
    
#     def add_span(self, content, font_size):
#         content = re.sub(r'[^\u4e00-\u9fa5\x00-\x7F\u3000-\u303F]', '', content)     # 匹配中文汉字以及ASCII码
#         if not content:
#             return
#         self.spans.append((content, font_size))
#         self.page_content += content
#         self.content_font = max(font_size, self.content_font)
        
#     def split(self, overlap=20) -> list['PdfLevelContent']:
#         # 找到self.spans中字体最大的span，作为二级标题
#         def half_split(self):
#             mid = len(self.page_content) // 2
#             left_index = min(mid + overlap, len(self.page_content))
#             right_index = max(mid - overlap, 0)
#             left = self.page_content[:left_index]
#             right = self.page_content[right_index:]

#             leftContent = self._return_empty_class(
#                 page_content=left, 
#                 spans=[(left, self.content_font)],
#                 content_font=self.content_font
#             )
#             rightContent = self._return_empty_class(
#                 page_content=right, 
#                 spans=[(right, self.content_font)],
#                 content_font=self.content_font
#             )
#             return leftContent, rightContent
        
#         max_span_font = max(self.spans, key=lambda x:x[1])[1]
#         min_span_font = min(self.spans, key=lambda x:x[1])[1]
#         if max_span_font == min_span_font:
#             return half_split(self)
        
#         idx = 0
#         SplitContents = []
#         parentContent = self._return_empty_class()
#         while idx < len(self.spans) and self.spans[idx][1] < max_span_font:       # 上一级标题和二级标题之间的内容作为一级标题下的内容
#             parentContent.add_span(*self.spans[idx])
#             idx += 1
#         if len(parentContent):
#             SplitContents.append(parentContent)
#         while idx < len(self.spans):
#             # newContent = PdfLevelContent(self.spans[idx][0], max_span_font, level=self.level+1)
#             newContent = self._return_empty_class()
#             newContent.level = self.level+1
#             newContent.title_fonts.append(max_span_font)
#             newContent.titles.append(self.spans[idx][0])
#             idx += 1
#             while idx < len(self.spans) and self.spans[idx][1] < max_span_font:
#                 newContent.add_span(*self.spans[idx])
#                 idx += 1
#             SplitContents.append(newContent)
            
#         if len(SplitContents) == 1:
#             return half_split(self)
#         return SplitContents
        
#     def __len__(self):
#         return len(self.page_content)
    
#     def _return_empty_class(self, page_content='', spans=[], content_font=0) -> 'PdfLevelContent':
#         newContent = deepcopy(self)
#         newContent.page_content = page_content
#         newContent.spans = spans
#         newContent.content_font = content_font
#         return newContent
        
    
# contents = []
# for s in snippets:
#     if not contents or s[1] > contents[-1].title_fonts[-1]:
#         newContent = PdfLevelContent(s[0], s[1], **data.metadata)
#         contents.append(newContent)
#         continue

#     if not contents[-1].content_font or s[1] <= contents[-1].content_font:
#         contents[-1].add_span(*s)
#         continue
    
#     newContent = PdfLevelContent(s[0], s[1], **data.metadata)
#     contents.append(newContent)

    
# maxLevel = 3
# maxLength = 512
# for level in range(1, maxLevel+1):
#     new_contents = []
#     no_need_deepen = True
#     for content in contents:
#         if len(content) > maxLength:
#             new_contents.extend(content.split())
#             no_need_deepen = False
#         elif len(content):
#             new_contents.append(content)
#     contents = new_contents
#     if no_need_deepen:
#         break
    
# for s in contents:
#     print("="*30)
#     print(s.metadata)
#     print(s.page_content)

from langchain.document_loaders import PyMuPDFLoader

loader = PyMuPDFLoader("CV-zh.pdf")
pages = loader.load()
for page in pages:
    print(page.page_content)
    
import os

class ResumeLoader:
    def __init__(self, file_path):
        file_name = os.path.basename(file_path)
        self.cache_dir = f"cache/resume/{file_name}"
        content_file_path = os.path.join(self.cache_dir, 'content.txt')
        if os.path.exists(content_file_path):
            with open(content_file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
        else:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
            loader = PyMuPDFLoader(file_path)
            pages = loader.load()
            self.content = ''
            for page in pages:
                self.content += page.page_content
            
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
            with open(os.path.join(self.cache_dir, 'content.txt'), 'w', encoding='utf-8') as f:
                f.write(self.content)
                
    def summarize(self, max_length=1024):
        prompt = (
            "请你根据用户的简历，生成简历摘要，要求提取出以下内容"
            "1. 教育背景，包括学校以及专业"
            "2. 工作经验，即工作时间为几年"
            "3. 工作技能，从校内、实习、工作项目、经历或其他地方提取出掌握的技能"
            "4. 对每一个项目进行总结，每一个项目压缩至最多50字"
            "输出格式要求：按照markdown格式输出，只输出摘要，不要返回其他内容"
            "用户简历\n{content}"
        )
        
    