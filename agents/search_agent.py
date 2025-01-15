from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from typing import Optional, List, Annotated, Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from APIDataClass import JobQueryRequest
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    
class JobQueryStructure(BaseModel):
    """永远使用这个模式来规范化输出格式"""
    city: Optional[List[str]] = Field(None, description="工作城市列表")
    keyword: Optional[str] = Field(None, description="用户查询和工作相关的关键词，如果用户指明实习或兼职，请添加实习/兼职关键词")
    degree: Optional[List[Literal[
        "初中及以下", "中专/中技", "高中", "大专", "本科", "硕士", "博士"
    ]]] = Field(None, description="学历要求列表， 如果用户没有指明，默认为None")
    experience: Optional[List[Literal[
        "应届生", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上"
    ]]] = Field(None, description="工作经验要求列表， 如果用户没有指明， 默认为None")
    scale: Optional[List[Literal[
        "0-20人", "20-99人", "100-499人", "500-999人", "1000-9999人", "10000人以上"
    ]]] = Field(None, description="公司人员规模要求列表，如果用户没有指明，默认为None")
    stage: Optional[List[Literal[
        "未融资", "天使轮", "A轮", "B轮", "C轮", "D轮及以上", "不需要融资", "已上市"
    ]]] = Field(None, description="公司融资阶段要求列表， 如果用户没有指明， 默认为None")
    
gen_query_system = """You are a Job Hunting Assistant.
Please extract the following information from your query:
- city: The city where you want to work.
- keywords: Keywords related to your job and work.
- degree: The degree requirements for your job.
- experience: The experience requirements for your job.
- scale: The company population size requirements for your job.
- stage: The financing stage requirements for your job.

If there are any of the above information missing, leave it as None.

You will convert it into JobQueryStructure format.
"""
    
llm_with_structure = llm.with_structured_output(JobQueryStructure)

workflow = StateGraph(State)

def handle_query(state: State) -> State:
    state["messages"].append(AIMessage(content=gen_query_system))
    structured_query = llm_with_structure.invoke(state["messages"])
    ai_message = AIMessage(content=str(structured_query.__dict__))
    return {"messages": [ai_message]}

workflow.add_node('handle_query', handle_query)
workflow.add_edge(START, 'handle_query')
workflow.add_edge('handle_query', END)

workflow = workflow.compile()

def GetJobQueryStructure(user_input: str, verbose=False) -> JobQueryRequest:
    last_message = ''
    for event in workflow.stream({"messages": [("user", user_input)]}):
        for value in event.values():
            last_message = value["messages"][-1].content
            if verbose:
                print("Assistant:", last_message)
    if last_message:
        input_kwargs = eval(last_message)
        return JobQueryRequest(
            city=input_kwargs["city"] or '',
            keyword=input_kwargs["keyword"] or '',
            degree=input_kwargs["degree"] or [],
            scale=input_kwargs["scale"] or [],
            experience=input_kwargs["experience"] or [],
            stage=input_kwargs["stage"] or []
        )
    else:
        return JobQueryRequest()
      
if __name__ == '__main__':
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        print(GetJobQueryStructure(user_input, verbose=True))