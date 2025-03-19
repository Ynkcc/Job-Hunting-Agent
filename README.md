# 使用参考
### 配置环境/安装依赖

```
pip install -r requirements.txt
playwright install
```

### 首次运行

1. 下载SQL数据库软件，如mariadb、mysql
2. 手动创建jobhunting数据库
3. 将`.streamlit\secrets_template.toml` 复制一份  
   重命名为 `.streamlit\secrets.toml`，并修改
4. 运行 `init_database.py`,初始化数据库
5. 运行 `crawl.py`,进行一次爬取。(必要的)
6. 正式运行 `streamlit run HomePage.py`