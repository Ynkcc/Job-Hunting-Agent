import streamlit as st

def main():
    st.set_page_config(page_title="数据库", page_icon="📊", layout="wide")
    "#### 数据库SQL查询工具 🔍️"

    select_table = 'job'
    conn = st.connection("jobhunting")
    if st.checkbox('显示数据库中的所有表', key='select_table'):
        df = conn.query("show tables;")
        select_table = st.selectbox('请选择要查询的表', df['Tables_in_jobhunting'])

    if st.checkbox('显示表结构'):
        if select_table:
            df = conn.query(f"""SELECT 
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_comment,
                    c.column_default,
                    IF(kcu.column_name IS NOT NULL, 'PRI', '') AS IS_KEY
                FROM 
                    information_schema.columns c
                LEFT JOIN 
                    information_schema.key_column_usage kcu 
                    ON c.column_name = kcu.column_name
                    AND c.table_name = kcu.table_name
                    AND c.table_schema = kcu.table_schema
                    AND kcu.constraint_name = 'PRIMARY'
                WHERE 
                    c.table_name = '{select_table}';"""
            )
            st.dataframe(df, height=200)

    st.slider('请选择最大显示条数', 1, 1000, 100, key='max_show')
    st.text_input('请在此输入SQL语句', 
                value=f'select * from {select_table}', 
                key='input_mysql')

    if st.session_state.input_mysql:
        df = conn.query(st.session_state.input_mysql.replace(';', '') + \
            f" limit {st.session_state.max_show};")
        st.dataframe(df, height=400)
            
if __name__ == '__main__':
    main()