import streamlit as st
import plotly.express as px
import pandas as pd
from APIDataClass import cursor
import plotly.graph_objects as go
from wordcloud import WordCloud

st.set_page_config(page_title="招聘岗位分析", page_icon="📈", layout="wide")

# 从数据库中加载数据
@st.cache_data
def get_data(query):
    cursor.execute(query)
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=[desc[0] for desc in cursor.description])
    return df

def draw_salary_bar_chart(df, group_col):
    group_high_salary = df.groupby(group_col)['hsalary'].mean()
    group_low_salary = df.groupby(group_col)['lsalary'].mean()
    sorted_indices = group_low_salary.sort_values(ascending=False).index
    group_low_salary = group_low_salary[sorted_indices]
    group_high_salary = group_high_salary.reindex(sorted_indices)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=group_low_salary.index,
        y=group_low_salary.values,
        name='Low Salary',
        marker_color='blue',
        text=[f"{val:.1f}" for val in group_low_salary.values],
        textposition='auto'
    ))
    fig.add_trace(go.Bar(
        x=group_high_salary.index,
        y=group_high_salary.values,
        name='High Salary',
        marker_color='red',
        text=[f"{val:.1f}" for val in group_high_salary.values],
        textposition='auto'
    ))
    fig.update_layout(
        barmode='stack',
        # title=f'Salary Analysis by {group_col.capitalize()}',
        xaxis_title=group_col.capitalize(),
        yaxis_title='年薪(万RMB)',
        height=600
    )
    st.plotly_chart(fig)

# 主程序
def main():
    st.title("招聘岗位分析")

    jobtypes = get_data("SELECT DISTINCT jobtype FROM job;")['jobtype'].tolist()
    cities = get_data("SELECT DISTINCT city FROM job;")['city'].tolist()
    industries = get_data("SELECT DISTINCT industry FROM job;")['industry'].tolist()
    degrees = get_data("SELECT DISTINCT degree FROM job;")['degree'].tolist()
    experiences = get_data("SELECT DISTINCT experience FROM job;")['experience'].tolist()
    
    "### 职位数量分析"
    data = get_data("SELECT city, jobtype FROM job")

    selected_cities = st.multiselect(
        "请选择城市（可多选，如果不选择，则默认显示全部城市）",
        options=['不限'] + cities,
        default=['不限']
    )
    
    selected_industry = st.selectbox(
        "请选择行业",
        options=industries,
        index=0
    )

    # 筛选数据
    if '不限' not in selected_cities:
        filtered_data = data[data['city'].isin(selected_cities)]
    else:
        filtered_data = data

    # 分组统计
    jobtype_counts = (
        filtered_data.groupby('jobtype')
        .size()
        .reset_index(name='count')
        .sort_values(by='count', ascending=False)
    )

    # 条形图
    if not jobtype_counts.empty:
        fig = px.bar(
            jobtype_counts,
            x='jobtype',
            y='count',
            text='count',
            labels={'jobtype': 'Job Type', 'count': 'Count'},
            height=500 
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig)
    else:
        st.warning("没有找到符合条件的岗位数据。")


    # 构建SQL查询语句
    query = "SELECT jobtype, experience, degree, city, lsalary, hsalary FROM job"
    df = get_data(query)

    # 可视化薪资与各因素的关系
    st.write('### 薪资分析')
        
    if not df.empty:
        if st.checkbox('薪资与职位类型关系', value=True): 
            draw_salary_bar_chart(df, 'jobtype')
        if st.checkbox('薪资与工作经验关系'):
            draw_salary_bar_chart(df, 'experience')
        if st.checkbox('薪资与学历要求关系'):
            draw_salary_bar_chart(df, 'degree')
        if st.checkbox('薪资与城市关系'):
            draw_salary_bar_chart(df, 'city')
    else:
        st.warning("没有找到符合条件的岗位数据。")

    # 分析薪资的直方图
    
    "### 薪资直方图"
    selected_jobtype = st.multiselect(
        "请选择职位类型",
        options=['不限'] + jobtypes,
        default=['不限']
    )

    selected_city = st.multiselect(
        "请选择城市",
        options=['不限'] + cities,
        default=['不限']
    )

    selected_degree = st.multiselect(
        "请选择学历要求",
        options=['不限'] + degrees,
        default=['不限']
    )

    selected_experience = st.multiselect(
        "请选择工作经验",
        options=['不限'] + experiences,
        default=['不限']
    )

    filtered_data = df

    # 检查是否选择了“不限”，如果没有选择“不限”，则应用相应的筛选条件
    if '不限' not in selected_jobtype:
        filtered_data = filtered_data[filtered_data['jobtype'].isin(selected_jobtype)]

    if '不限' not in selected_city:
        filtered_data = filtered_data[filtered_data['city'].isin(selected_city)]

    if '不限' not in selected_degree:
        filtered_data = filtered_data[filtered_data['degree'].isin(selected_degree)]

    if '不限' not in selected_experience:
        filtered_data = filtered_data[filtered_data['experience'].isin(selected_experience)]

    # 选择需要的列并去除缺失值
    filtered_data = filtered_data[["lsalary", "hsalary"]].dropna()

    df_melted = filtered_data.melt(var_name='Salary Type', value_name='Salary')
    fig = px.histogram(
        df_melted,
        x='Salary',
        color='Salary Type',
        barmode='overlay',  # 使用叠加模式
        nbins=300,  # 设置直方图的柱子数量
        title='工资直方图',
        labels={'Salary': 'Salary', 'Salary Type': 'Salary Type'},
        color_discrete_map={'lsalary': 'yellow', 'hsalary': 'red'}
    )
    fig.update_traces(marker_opacity=0.6)  # 设置透明度为0.6
    fig.update_layout(
        xaxis_title='年薪(万RMB)',
        yaxis_title='个数',
        height=600
    )
    st.plotly_chart(fig)
    
    "### 工作技能需求词云图"
    selected_jobtype = st.selectbox(
        "请选择职位类型",
        options=jobtypes,
        index=0
    )

    tips_placeholder = st.empty()
    tips_placeholder.write('正在分析职位描述中的技能要求...')
    data = get_data(f"SELECT labels FROM job WHERE jobtype='{selected_jobtype}'")
    # 每一个skills是用"，"分割的
    skill_freq = {}
    for labels in data['labels']:
        for skill in labels.split('，'):
            if '居家' not in skill:
                skill_freq.setdefault(skill, 0)
                skill_freq[skill] += 1
    wordcloud = WordCloud(background_color='white', 
        width=2000, 
        height=600,
        font_path=r'C:\Windows\Fonts\msyh.ttc'
    ).generate_from_frequencies(skill_freq)
    st.image(wordcloud.to_image(), use_container_width=True)
    tips_placeholder.empty()
    
if __name__ == "__main__":
    main()
