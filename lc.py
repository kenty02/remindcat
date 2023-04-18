import re
from datetime import datetime
from typing import List, Union

from dotenv import load_dotenv
from langchain import LLMChain
from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent, AgentOutputParser, tool
from langchain.chat_models import ChatOpenAI
from langchain.prompts import BaseChatPromptTemplate
from langchain.schema import AgentAction, AgentFinish, HumanMessage, BaseMessage
from sqlmodel import Session

from db import engine, Reminder

load_dotenv()  # take environment variables from .env.

# Set up the base template
template = """You are an assistant that provides reminders. Guess what time and what name of reminder to set. The current time is {current_time}. You have access to the following tools:

{tools}

Use the following format:

Question: the user input
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the result of the action
Final Answer: the final answer to the original input, with the tone of voice: "{tone_of_voice}".

Begin! Please speak in Japanese. Clearly indicate to the user what action has been taken.

Question: {input}
{agent_scratchpad}"""


# Set up a prompt template
class CustomPromptTemplate(BaseChatPromptTemplate):
    # The template to use
    template: str
    # The list of tools available
    tools: List[Tool]

    def format_messages(self, **kwargs) -> List[BaseMessage]:
        # Get the intermediate steps (AgentAction, Observation tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps")
        thoughts = ""
        for action, observation in intermediate_steps:
            thoughts += action.log
            thoughts += f"\nObservation: {observation}\nThought: "
        # Set the agent_scratchpad variable to that value
        kwargs["agent_scratchpad"] = thoughts
        # Create a tools variable from the list of tools provided
        kwargs["tools"] = "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
        # Create a list of tool names for the tools provided
        kwargs["tool_names"] = ", ".join([tool.name for tool in self.tools])
        kwargs["current_time"] = datetime.now().strftime('%Y-%m-%d %H:%M')
        tone_of_voice = "語尾に、にゃ、にゃー、にゃーんなどをつけて話してください。"
        kwargs["tone_of_voice"] = tone_of_voice
        formatted = self.template.format(**kwargs)
        return [HumanMessage(content=formatted)]


class CustomOutputParser(AgentOutputParser):

    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        # Check if agent should finish
        if "Final Answer:" in llm_output:
            return AgentFinish(
                # Return values is generally always a dictionary with a single `output` key
                # It is not recommended to try anything else at the moment :)
                return_values={"output": llm_output.split("Final Answer:")[-1].strip()},
                log=llm_output,
            )
        # Parse out the action and action input
        regex = r"Action: (.*?)[\n]*Action Input:[\s]*(.*)"
        match = re.search(regex, llm_output, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse LLM output: `{llm_output}`")
        action = match.group(1).strip()
        action_input = match.group(2)
        # Return the action and action input
        return AgentAction(tool=action, tool_input=action_input.strip(" ").strip('"'), log=llm_output)


output_parser = CustomOutputParser()
llm = ChatOpenAI(temperature=0)

# LLM chain consisting of the LLM and a prompt

NULL_USER = "NULL_USER"


def get_agent_executor(to: str) -> AgentExecutor:
    @tool("Set a reminder")
    def register_reminder(text):
        """
        This is useful when you want to set a reminder to inform users of something later.
        The input for this tool is the date (yyyy-mm-dd HH:MM) and the reminder name, separated by commas.
        Example: 2020-09-24 15:08,Birthday party
        """
        time_str, reminder_text = text.split(",")
        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if to != NULL_USER:
            with Session(engine) as session:
                session.add(Reminder(name=reminder_text, time=time, line_to=to))
                session.commit()

        print(f"Reminder set for {time} with name {reminder_text}")
        return f"Reminder set for {time} with name {reminder_text}"

    tools = [
        Tool(
            name=register_reminder.name,
            func=register_reminder,
            description=register_reminder.description,
        ),
    ]

    prompt = CustomPromptTemplate(
        template=template,
        tools=tools,
        # This omits the `agent_scratchpad`, `tools`, and `tool_names` variables because those are generated dynamically
        # This includes the `intermediate_steps` variable because that is needed
        input_variables=["input", "intermediate_steps"]
    )

    llm_chain = LLMChain(llm=llm, prompt=prompt)
    tool_names = [tool.name for tool in tools]
    agent = LLMSingleActionAgent(
        llm_chain=llm_chain,
        output_parser=output_parser,
        stop=["\nObservation:"],
        allowed_tools=tool_names
    )
    agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)
    return agent_executor


if __name__ == "__main__":
    agent_executor = get_agent_executor(NULL_USER)
    print(agent_executor.run("なにができますか？"))
