import json
import uuid
import asyncio
import logging
import aiofiles
from pathlib import Path
from threading import Thread
from typing import List, Optional, Self, TypeAlias, Union, Type, Any
from dataclasses import dataclass

from pydantic import BaseModel, Field

from cognitrix.tasks import Task
from cognitrix.llms.base import LLM
from cognitrix.tools.base import Tool
from cognitrix.utils import extract_json, json_return_format
from cognitrix.agents.templates import AUTONOMOUSE_AGENT_2
from cognitrix.config import AGENTS_FILE

logger = logging.getLogger('cognitrix.log')

AgentList: TypeAlias = List['Agent']

class Agent(BaseModel):
    name: str = Field(default='Avatar')
    llm: LLM
    tools: List[Tool] = Field(default_factory=list)
    prompt_template: str = Field(default=AUTONOMOUSE_AGENT_2)
    verbose: bool = Field(default=False)
    sub_agents: AgentList = Field(default_factory=list)
    task: Optional[Task] = None
    is_sub_agent: bool = Field(default=False)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: Optional[str] = None
    autostart: bool = False

    @property
    def available_tools(self) -> List[str]:
        return [tool.name for tool in self.tools]

    def format_system_prompt(self):
        tools_str = self._format_tools_string()
        subagents_str = self._format_subagents_string()
        llms_str = self._format_llms_string()

        prompt = self.prompt_template
        prompt = prompt.replace("{name}", self.name)
        prompt = prompt.replace("{tools}", tools_str)
        prompt = prompt.replace("{subagents}", subagents_str)
        prompt = prompt.replace("{available_tools}", json.dumps(self.available_tools))
        prompt = prompt.replace("{llms}", llms_str)
        prompt = prompt.replace("{return_format}", json_return_format)

        if 'json' not in prompt:
            prompt += f"\n{json_return_format}"

        self.llm.system_prompt = prompt

    def _format_tools_string(self) -> str:
        return "Available Tools:\n" + "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])

    def _format_subagents_string(self) -> str:
        subagents_str = "Available Subagents:\n"
        subagents_str += "\n".join([f"-- {agent.name}: {agent.task.description}" for agent in self.sub_agents if agent.task])
        subagents_str += "\nYou should always use a subagent for a task if there is one specifically created for that task."
        return subagents_str

    def _format_llms_string(self) -> str:
        llms = LLM.list_llms()
        llms_str = "Available LLM Platforms:\n" + ", ".join(llms) + "\nChoose one for each subagent."
        return llms_str

    def generate_prompt(self, query: str | dict, role: str = 'User') -> dict:
        processed_query = self._process_query(query)
        prompt: dict[str, Any] = {'role': role, 'type': 'text'}

        if isinstance(processed_query, dict):
            result = processed_query['result']
            if isinstance(result, list):
                if result[0] == 'image':
                    prompt['type'] = 'image'
                    prompt['image'] = result[1]
                elif result[0] == 'agent':
                    new_agent: Agent = result[1]
                    new_agent.parent_id = self.id
                    self.add_sub_agent(new_agent)

                    if new_agent.autostart:
                        self.start_task_thread(new_agent, self)

                    prompt['message'] = result[2]
                else:
                    prompt['message'] = result
            else:
                prompt['message'] = result
        else:
            prompt['message'] = processed_query

        return prompt

    def _process_query(self, query: str | dict) -> str | dict:
        return extract_json(query) if isinstance(query, str) else query

    def add_sub_agent(self, agent: 'Agent'):
        self.sub_agents.append(agent)

    def get_sub_agent_by_name(self, name: str) -> Optional['Agent']:
        return next((agent for agent in self.sub_agents if agent.name.lower() == name.lower()), None)

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        return next((tool for tool in self.tools if tool.name.lower() == name.lower()), None)

    def process_response(self, response: str) -> Union[dict, str]:
        response = response
        response_data = extract_json(response)

        try:
            if isinstance(response_data, dict):
                final_result_keys = ['final_answer', 'function_call_result']

                if response_data['type'].replace('\\', '') in final_result_keys:
                    return response_data['result']

                tool = self.get_tool_by_name(response_data['function'])
                if isinstance(response_data['arguments'], dict):
                    response_data['arguments'] = list(response_data['arguments'].values())

                if response_data['function'].lower() == 'create agents':
                    response_data['arguments'] = [*response_data['arguments'], self.id]

                if not tool:
                    raise Exception(f"Tool {response_data['function']} not found")

                print(f"\nRunning tool '{tool.name.title()}' with parameters: {response_data['arguments']}")

                if 'sub agent' in tool.name.lower():
                    response_data['arguments'].append(self)

                result = tool.run(*response_data['arguments'])

                response_json = {
                    'type': 'function_call_result',
                    'result': result
                }

                return response_json
            else:
                raise Exception('Not a json object')
        except Exception as e:
            logger.warning(str(e))
            return response_data

    def add_tool(self, tool: Tool):
        self.tools.append(tool)

    async def call_tool(self, tool, params):
        if asyncio.iscoroutinefunction(tool):
            return await tool(**params)
        else:
            return tool(**params)

    async def initialize(self):
        query: str | dict = input("\nUser (q to quit): ")
        while True:
            try:
                if not query:
                    query: str | dict = input("\nUser (q to quit): ")
                    continue
                if isinstance(query, str):
                    if query.lower() in ['q', 'quit', 'exit']:
                        print('Exiting...')
                        break

                    elif query.lower() == 'add agent':
                        new_agent = self.create_agent(is_sub_agent=True, parent_id=self.id)
                        if new_agent:
                            self.add_sub_agent(new_agent)
                            print(f"\nAgent {new_agent.name} added successfully!")
                        else:
                            print("\nError creating agent")

                        query = input("\nUser (q to quit): ")
                        continue

                    elif query.lower() == 'list agents':
                        agents_str = "\nAvailable Agents:"
                        sub_agents = [agent for agent in await self.list_agents() if agent.parent_id == self.id]
                        for index, agent in enumerate(sub_agents):
                            agents_str += (f"\n[{index}] {agent.name}")
                        print(agents_str)
                        query = input("\nUser (q to quit): ")
                        continue

                self.format_system_prompt()
                full_prompt = self.generate_prompt(query)
                response: Any = self.llm(full_prompt)
                self.llm.chat_history.append(full_prompt)
                self.llm.chat_history.append({'role': self.name, 'type': 'text', 'message': response})

                if self.verbose:
                    print(response)

                result: dict[Any, Any] | str = self.process_response(response)

                if isinstance(result, dict) and result['type'] == 'function_call_result':
                    query = result
                else:
                    print(f"\n{self.name}: {result}")
                    query = input("\nUser (q to quit): ")

            except KeyboardInterrupt:
                print('Exiting...')
                break
            except Exception as e:
                logger.exception(e)
                break

    def start(self):
        asyncio.run(self.initialize())

    @staticmethod
    def start_task_thread(agent: 'Agent', parent: 'Agent'):
        agent_thread = Thread(target=agent.run_task, args=(parent,))
        agent_thread.name = agent.name.lower()
        agent_thread.start()

    def run_task(self, parent: Self):
        self.format_system_prompt()
        query = self.task.description if self.task else None

        while query:
            full_prompt = self.generate_prompt(query)
            response: Any = self.llm(full_prompt)
            self.llm.chat_history.append(full_prompt)
            self.llm.chat_history.append({'role': 'user', 'type': 'text', 'message': response})

            agent_result = self.process_response(response)
            if isinstance(agent_result, dict) and agent_result['type'] == 'function_call_result':
                query = agent_result
            else:
                parent_prompt = parent.generate_prompt(response, 'user')
                parent_prompt['message'] = self.name + ": " + response
                parent_response: Any = parent.llm(parent_prompt)
                parent.llm.chat_history.append(parent_prompt)
                parent.llm.chat_history.append({'role': 'assistant', 'type': 'text', 'message': parent_response})
                parent_result = parent.process_response(parent_response)
                print(f"\n\n{parent.name}: {parent_result}")
                query = ""

    def call_sub_agent(self, agent_name: str, task_description: str):
        sub_agent = self.get_sub_agent_by_name(agent_name)
        if sub_agent:
            sub_agent.task = Task(description=task_description)
            if sub_agent.task:
                self.start_task_thread(sub_agent, self)
        else:
            full_prompt = self.generate_prompt(f'Sub-agent with name {agent_name} was not found.')
            self.llm(full_prompt)

    @classmethod
    def create_agent(cls, name: str = '', description: str = '', task_description: str = '', tools: List[Tool] = [],
                     llm: Optional[LLM] = None, is_sub_agent: bool = False, parent_id=None) -> Optional[Self]:
        try:
            name = name or input("\n[Enter agent name]: ")

            while not llm:
                llms = LLM.list_llms()
                llms_str = "\nAvailable LLMs:"
                for index, llm_l in enumerate(llms):
                    llms_str += (f"\n[{index}] {llm_l}")
                print(llms_str)
                agent_llm = int(input("\n[Select LLM]: "))
                selected_llm = llms[agent_llm]
                loaded_llm = LLM.load_llm(selected_llm)

                if loaded_llm:
                    llm = loaded_llm()
                    llm.model = input(f"\nEnter model name [{llm.model}]: ") or llm.model
                    llm.temperature = float(input(f"\nEnter model temperature [{llm.temperature}]: ")) or llm.temperature

            if llm:
                task = Task(description=task_description)
                new_agent = cls(name=name, llm=llm, task=task, tools=tools, is_sub_agent=is_sub_agent, parent_id=parent_id)
                if description:
                    new_agent.prompt_template = description

                agents = []
                with open(AGENTS_FILE, 'r') as file:
                    content = file.read()
                    agents = json.loads(content) if content else []
                    agents.append(new_agent.model_dump())

                with open(AGENTS_FILE, 'w') as file:
                    json.dump(agents, file, indent=4)

                return new_agent

        except Exception as e:
            logger.error(str(e))

    @classmethod
    async def list_agents(cls, parent_id: Optional[str] = None) -> AgentList:
        try:
            agents: AgentList = []
            async with aiofiles.open(AGENTS_FILE, 'r') as file:
                content = await file.read()
                loaded_agents: list[dict] = json.loads(content) if content else []
                for agent in loaded_agents:
                    llm = LLM.load_llm(agent["llm"]["platform"])
                    loaded_agent = Agent(**agent)
                    if llm:
                        loaded_agent.llm = llm(**agent["llm"])
                    agents.append(loaded_agent)

            if parent_id:
                agents = [agent for agent in agents if agent.parent_id == parent_id]

            return agents

        except Exception as e:
            logger.exception(e)
            return []

    @classmethod
    async def get(cls, id) -> Optional['Agent']:
        try:
            agents = await cls.list_agents()
            loaded_agents: list[Agent] = [agent for agent in agents if agent.id == id]
            if len(loaded_agents):
                return loaded_agents[0]
        except Exception as e:
            logger.exception(e)
            return None

    @classmethod
    def load_agent(cls, agent_name: str) -> Optional['Agent']:
        try:
            agent_name = agent_name.lower()
            agents = asyncio.run(cls.list_agents())
            loaded_agents: list[Agent] = [agent for agent in agents if agent.name.lower() == agent_name]
            if loaded_agents:
                agent = loaded_agents[0]
                agent.sub_agents = asyncio.run(cls.list_agents(agent.id))
                return agent
        except Exception as e:
            logger.exception(e)
            return None