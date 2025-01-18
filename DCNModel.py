from APIDataClass import JobInfo
import json
import os
from tqdm import tqdm, trange
from openai import OpenAI
import numpy as np
import torch.nn as nn
import torch
import torch.optim as optim
import torch.nn.functional as F

LLM = OpenAI()

def get_embedding(text, model="text-embedding-ada-002"):
    response = LLM.embeddings.create(
        input=text,
        model=model
    )
    return np.array(response.data[0].embedding)

class JobDataset:
    def __init__(self, name):
        self.name = name
        self.data_path = f"cache/dataset/{name}/raw_data.jsonl"
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Dataset {name} not found.")
        self.data = []
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line in f:
                js = json.loads(line)
                jobname, company, city = js['jobname'], js['company'], js['city']
                jobinfo = JobInfo.from_db(jobname, company, city)
                jobinfo.related_jobs = js['related_jobs']
                self.data.append(jobinfo)
                
    def get_itemCF_data(self):
        # dataset第i行为职位i, 和他相关联的职位有6个，分别为i_j, 1<=j<=6
        # 第i个职位评分记作s_i，等于clicked_i + sent_i，点击+1分，发送简历+1分
        # 第i个职位的第j个相关职位评分记作s_ij，等于s_i * (1 / j)
        # 如果有重复的相关职位，则评分求和
        score_map: dict[str, float] = {}
        for job in self.data:
            related_jobs = job.related_jobs
            score = int(job.clicked > 0) + int(job.sent > 0)
            for idx, url in enumerate(related_jobs):
                if url not in score_map:
                    score_map[url] = score * (1 / (idx + 1))
                else:
                    score_map[url] += score * (1 / (idx + 1))
        return score_map
                
    def get_embeddings(self):
        embeddings = []
        embedding_dir = f"cache/dataset/{self.name}/embedding"
        if not os.path.exists(embedding_dir):
            os.makedirs(embedding_dir)
        for i, jobinfo in tqdm(enumerate(self.data), total=len(self.data), desc="Getting embeddings"):
            if os.path.exists(f"{embedding_dir}/{i}.npy"):
                with open(f"{embedding_dir}/{i}.npy", 'rb') as f:
                    embedding = np.load(f)
                    embeddings.append(torch.tensor(embedding).float())
            else:
                text = (
                    f"工作名称：{jobinfo.jobname}\n公司名称：{jobinfo.company}\n工作地点：{jobinfo.address}\n薪资范围：{jobinfo.salary}\n"
                    f"经验要求：{jobinfo.experience}\n学历要求：{jobinfo.degree}\n标签：{jobinfo.labels}\n行业：{jobinfo.industry}\n"
                    f"融资状态：{jobinfo.stage}\n人员规模：{jobinfo.scale}\n{jobinfo.description}"
                )
                embedding = get_embedding(text)
                np.save(f"{embedding_dir}/{i}.npy", embedding)
                embeddings.append(torch.tensor(embedding).float())
        return torch.stack(embeddings)
    
    def split(self, k=10, idx=0, seed=12):
        if k <= 1:
            raise ValueError("k should be greater than 1.")
        if idx < 0 or idx >= k:
            raise ValueError("idx should be in [0, k-1].")
        data_len = len(self.data)
        split_len = data_len // k
        if idx < data_len % k:
            split_len += 1
        np.random.seed(seed)
        np.random.shuffle(self.data)
        embeddings = self.get_embeddings()
        clicked = [job.clicked for job in self.data]
        sent = [job.sent for job in self.data]
        train_embeddings = torch.cat([embeddings[:split_len*idx, :], embeddings[split_len*(idx+1):, :]], dim=0)
        train_clicked = clicked[:split_len*idx] + clicked[split_len*(idx+1):]
        train_sent = sent[:split_len*idx] + sent[split_len*(idx+1):]
        test_embeddings = embeddings[split_len*idx:split_len*(idx+1), :]
        test_clicked = clicked[split_len*idx:split_len*(idx+1)]
        test_sent = sent[split_len*idx:split_len*(idx+1)]
        return train_embeddings, torch.tensor(train_clicked).float(), torch.tensor(train_sent).float(), \
               test_embeddings, torch.tensor(test_clicked).float(), torch.tensor(test_sent).float()
                
    def __len__(self):
        return len(self.data)
            
class WeightedBinaryCrossEntropyLoss(nn.Module):
    def __init__(self, weight_0=1.0, weight_1=1.0):
        super(WeightedBinaryCrossEntropyLoss, self).__init__()
        self.weight_0 = weight_0
        self.weight_1 = weight_1
        self.bce_loss = nn.BCELoss(reduction='none')  # 不直接计算平均损失

    def forward(self, inputs, targets):
        loss = self.bce_loss(inputs, targets)
        # 为标签为0和1的样本分别赋予权重
        weights = targets * self.weight_1 + (1 - targets) * self.weight_0
        weighted_loss = loss * weights
        return weighted_loss.mean()  # 返回加权后的平均损失        
        
class DeepCrossNetwork(nn.Module):
    def __init__(self, embedding_dim, deep_layer_dims, cross_layer_num, weight_decay=0.01, dropout=0.5):
        # 有两个输入向量，一个是用户embedding，一个是职位embedding
        super(DeepCrossNetwork, self).__init__()
        self.weight_decay = weight_decay
        self.dropout = dropout
        self.cross_layer_num = cross_layer_num
        
        # 定义cross layer
        self.cross_layers = nn.ModuleList([nn.Linear(embedding_dim, embedding_dim, bias=True) for _ in range(cross_layer_num)])
        self.cross_LN_layers = nn.ModuleList([nn.LayerNorm(embedding_dim) for _ in range(cross_layer_num)])
                
        # 定义deep layer
        dims = [embedding_dim] + deep_layer_dims
        self.deep_layers = nn.ModuleList([nn.Linear(dims[i], dims[i+1], bias=True) for i in range(len(dims)-1)])
        self.deep_LN_layers = nn.ModuleList([nn.LayerNorm(dims[i + 1]) for i in range(len(dims) - 1)])
        self.deep_activation = nn.ReLU()
        self.deep_dropout = nn.Dropout(self.dropout)
        
        # 定义输出层
        self.output_layer = nn.Linear(dims[-1] + embedding_dim, 1, bias=True)
        self.output_activation = nn.Sigmoid()
        
    def forward(self, embedding, use_dropout=True):
        x_0 = embedding
        # 通过cross layer
        x_i = x_0
        for i in range(self.cross_layer_num):
            x_i_1 = self.cross_layers[i](x_i)
            x_i_1 = self.cross_layers[i](x_0)
            x_i = x_i * x_0  # 用非in-place操作
            x_i_1 = x_i_1 + x_i
            x_i = self.cross_LN_layers[i](x_i_1)
            
        # 通过deep layer
        y_i = x_0
        for i in range(len(self.deep_layers)):
            y_i = self.deep_layers[i](y_i)
            y_i = self.deep_LN_layers[i](y_i)
            y_i = self.deep_activation(y_i)
            if use_dropout:
                y_i = self.deep_dropout(y_i)
            
        x_stack = torch.cat([x_i, y_i], dim=1)
        output = self.output_layer(x_stack)
        return self.output_activation(output)
    
    def save(self, path):
        torch.save(self.state_dict(), path)
    
    def train(self, embeddings, labels, batch_size, lr, epochs):
        optimizer = optim.AdamW(self.parameters(), lr=lr, weight_decay=self.weight_decay)
        criterion = nn.BCELoss()  # 二分类损失函数
        for epoch in range(epochs):
            optimizer.zero_grad()  # 清空梯度
            
            total_loss = 0
            acc_num = 0
            for i in range(0, len(embeddings), batch_size):
                embedding_batch = embeddings[i:i+batch_size]
                label = labels[i:i+batch_size]
                
                output = self(embedding_batch, use_dropout=True)
                
                loss = criterion(output.squeeze(-1), label)
                total_loss += loss.item()
                pred = (output > 0.5).squeeze().float()
                print(pred)
                acc_num += (pred == label).sum().item()
                
                loss.backward()
                optimizer.step()
            
            print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss / len(embeddings):.4f}, Train Acc: {acc_num / len(embeddings)*100:.2f}%")

    def evaluate(self, embeddings, labels, batch_size=64):
        with torch.no_grad():
            acc_num = 0
            for i in trange(0, len(embeddings), batch_size):
                embedding_batch = embeddings[i:i+batch_size]
                label = labels[i:i+batch_size]
                
                output = self(embedding_batch, use_dropout=False)
                
                pred = (output > 0.5).squeeze().float()
                acc_num += (pred == label).sum().item()
                print(pred, label)
            print(f"Test Acc: {acc_num / len(embeddings)*100:.2f}%")
            
    def inference(self, embedding):
        with torch.no_grad():
            output = self(embedding, use_dropout=False)
            pred = (output > 0.5).squeeze().float()
            return pred
        
             
if __name__ == "__main__":   
    dataset = JobDataset("original")
    train_embeddings, train_clicked, train_sent, test_embeddings, test_clicked, test_sent = dataset.split(k=10, idx=1, seed=12)
    embedding_dim = len(train_embeddings[0])
    
    DCN = DeepCrossNetwork(embedding_dim=embedding_dim, deep_layer_dims=[1024, 2048, 1024], cross_layer_num=6, dropout=0.3)
    DCN.train(train_embeddings, train_clicked, batch_size=2, lr=0.01, epochs=5)
    DCN.evaluate(test_embeddings, test_clicked, batch_size=64)
    DCN = DeepCrossNetwork(embedding_dim=embedding_dim, deep_layer_dims=[1024, 2048, 1024], cross_layer_num=6, dropout=0.3)
    DCN.train(train_embeddings, train_sent, batch_size=64, lr=0.01, epochs=5)
    DCN.evaluate(test_embeddings, test_sent, batch_size=64)
    