from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from typing import Any, Annotated, Literal
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages


def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

host = 'localhost'
user = 'rebibabo'
password = '123456'
database = 'jobhunting'
db = SQLDatabase.from_uri(f"mysql+pymysql://{user}:{password}@{host}:{3306}/{database}")

toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o-mini"))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

# print(list_tables_tool.invoke(""))

# print(get_schema_tool.invoke("city"))

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    try:
        result = db.run(query)
        if not result:
            return "No results found."
        return result
    except Exception as e:
        return f"Error: {e}. Please fix your query and try again."



query_check_system = """You are a SQL expert with a strong attention to detail.
Double check the SQLite query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

You will call the appropriate tool to execute the query after running this check."""

query_check_prompt = ChatPromptTemplate.from_messages(
    [("system", query_check_system), ("placeholder", "{messages}")]
)

query_check = query_check_prompt | ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
    [db_query_tool], tool_choice="required"         # must call the db_query_tool to execute the query
)

# print(query_check.invoke({"messages": [("user", "SELECT * FROM Artist LIMIT 10;")]}))


# Define the state for the agent
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Define a new graph
workflow = StateGraph(State)


# Add a node for the first tool call
def first_tool_call(state: State) -> dict[str, list[AIMessage]]:        # the input of the node is the previous state, and output the next state
    return {        
        "messages": [
            AIMessage(
                content="",
                tool_calls=[        # force-call the list_tables_tool to fetch the available tables from the database
                    {   
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }


def model_check_query(state: State) -> dict[str, list[AIMessage]]:
    """
    Use this tool to double-check if your SQL query is correct before executing it.
    """
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}


workflow.add_node("first_tool_call", first_tool_call)   # return AIMessage with a tool_call to the list_tables_tool

workflow.add_node("list_tables_tool", create_tool_node_with_fallback([list_tables_tool]))       # return ToolMessage with the list of tables from list_tables_tool

# Add a node for a model to choose the relevant tables based on the question and available tables
model_get_schema = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(
    [get_schema_tool], tool_choice="required"
)
workflow.add_node(          # return AIMessage with a tool_call to the get_schema_tool
    "model_get_schema",
    lambda state: {
        "messages": [model_get_schema.invoke(state["messages"])],
    },
)

workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))         # return ToolMessage with the schema of a table from get_schema_tool


# Add a node for a model to generate a query based on the question and schema
query_gen_system = """You are a SQL expert with a strong attention to detail.

Given an input question, output a syntactically correct SQLite query to run, then look at the results of the query and return the answer.

When generating the query:

If the user specifies a specific number of examples they wish to obtain, limit your query to that number, otherwise return 10 examples by default.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

If you get an error while executing a query, rewrite the query and try again according to the error message.

If you get an empty result set, you should try to rewrite the query to get a non-empty result set. 
NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database."""
query_gen_prompt = ChatPromptTemplate.from_messages(
    [("system", query_gen_system), ("placeholder", "{messages}")]
)

query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0)

def query_gen_node(state: State):
    return {"messages": [query_gen.invoke(state)]}


workflow.add_node("query_gen", query_gen_node)      # return AIMessage with the generated SQL query

# Add a node for the model to check the query before executing it
workflow.add_node("correct_query", model_check_query)       # return AImessage with the corrected query with the help of the model_check_query tool

# Add node for executing the query
workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))     # return ToolMessage with the result of the query


# Define a conditional edge to decide whether to continue or end the workflow
def should_continue(state: State) -> Literal[END, "query_gen"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.content.startswith("Error:") or last_message.content.startswith("No results found."):
        return "query_gen"
    else:  
        return END


# Specify the edges between the nodes
workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_edge("query_gen", "correct_query")
workflow.add_edge("correct_query", "execute_query")
workflow.add_conditional_edges(
    "execute_query",
    should_continue,
)

# Compile the workflow into a runnable
app = workflow.compile()

app.get_graph().draw_mermaid_png(output_file_path="graph.png")

# for event in app.stream(        # event: AIMessage
#     {"messages": [("user", "帮我搜索数据分析师岗位有哪些标签")]}
# ):
#     for value in event.values():
#         print("Assistant:", value["messages"][-1].content)

for event in app.stream(
    {"messages": [("user", "帮我查询和大模型相关的50个实习职位, 要求地点是北京")]}
):
    print(event)
    print()
    
# 分三个功能：
# 1. 根据自然语言描述，生成SQL语句
# 2. 根据SQL语句执行结果，进行总结
# 3. 询问SQL语句的语法含义

