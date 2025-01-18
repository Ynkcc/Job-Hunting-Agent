from APIDataClass import JobInfo
from agents.JobAgent import GPTRanker, GPTFilter, Metrics
import json
import os

if not os.path.exists("result"):
    os.makedirs("result")

if __name__ == '__main__':
    dataset = 'original'
    model = 'gpt-4o-mini'
    k = 100
    window_length = 20
    step = 10
    batch_size = 10
    rank = True
    filter = True
    clicked = []
    sent = []
    TotalJobInfo = []
    with open(f'cache/dataset/{dataset}/raw_data.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            jobname, company, city = data['jobname'], data['company'], data['city']
            jobinfo = JobInfo.from_db(jobname, company, city)
            TotalJobInfo.append(jobinfo)

    if rank:
        ranker = GPTRanker(TotalJobInfo, "CV-zh.pdf")  
        TotalJobInfo = ranker.rank(window_length=window_length, step=step, model=model)

    if filter:
        filter = GPTFilter(TotalJobInfo, "公司规模必须超过1000人，不要多模态岗位，只要实习岗位（按天来算薪资），不要正式工作")
        TotalJobInfo = filter.filter(batch_size, model=model)

    for jobinfo in TotalJobInfo:
        clicked.append(jobinfo.clicked)
        sent.append(jobinfo.sent)

    clicked_metrics = Metrics(clicked[:k])
    sent_metrics = Metrics(sent[:k])
    
    result = {"clicked": {}, "sent": {}}
    result["clicked"]["hit_ratio"] = clicked_metrics.getHitRatio()
    result["clicked"]["map"] = clicked_metrics.getMAP()
    result["clicked"]["ndcg"] = clicked_metrics.getNDCG()
    result["sent"]["hit_ratio"] = sent_metrics.getHitRatio()
    result["sent"]["map"] = sent_metrics.getMAP()
    result["sent"]["ndcg"] = sent_metrics.getNDCG()

    print(result)
    output_file = f"result/{dataset}_k{k}"
    if rank:
        output_file += f"_ranked_{model}_{window_length}_{step}"
    if filter:
        output_file += f"_filtered_{model}_{batch_size}"
    output_file += ".json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)