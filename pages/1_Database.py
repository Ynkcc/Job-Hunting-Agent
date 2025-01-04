import streamlit as st

def main():
    st.set_page_config(page_title="Database", page_icon="📊", layout="wide")
    "#### Execute SQL queries on jobhunting database. 🔍️"

    select_table = 'job'
    conn = st.connection("jobhunting")
    if st.checkbox('Show available tables', key='select_table'):
        df = conn.query("show tables;")
        select_table = st.selectbox('Select a table to view', df['Tables_in_jobhunting'])

    if st.checkbox('Show table schema'):
        if select_table:
            df = conn.query(f"describe {select_table};")
            st.dataframe(df, height=300)

    st.slider('Please select the maximum number of rows to show', 1, 1000, 100, key='max_show')
    st.text_input('Please input the mysql statement', 
                value=f'select * from {select_table}', 
                key='input_mysql')

    if st.session_state.input_mysql:
        df = conn.query(st.session_state.input_mysql.replace(';', '') + \
            f" limit {st.session_state.max_show};")
        st.dataframe(df, height=400)
            
if __name__ == '__main__':
    main()