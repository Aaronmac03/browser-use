import asyncio
from typing import List
from pydantic import BaseModel, Field
from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.agent.prompts import SystemPrompt
from browser_use.llm.messages import SystemMessage, UserMessage


class SubTaskList(BaseModel):
    """
    A list of sub-tasks to be completed.
    """

    sub_tasks: List[str] = Field(
        ..., description="A list of sub-tasks to be completed to achieve the user's goal."
    )


class ManagerAgent:
    """
    The ManagerAgent is responsible for decomposing a high-level user goal into a list of concrete sub-tasks.
    """

    def __init__(
        self,
        task: str,
        llm: BaseChatModel | None = None,
        system_prompt_path: str = "browser_use/agent/manager_system_prompt.md",
    ):
        self.task = task
        if llm is None:
            llm = ChatOpenAI(model="gpt-4.1-mini")
        self.llm = llm
        with open(system_prompt_path) as f:
            self.system_prompt = f.read()

    async def run(self) -> List[str]:
        """
        Generates a list of sub-tasks from the user's goal.
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            UserMessage(content=self.task),
        ]

        response = await self.llm.ainvoke(messages, output_format=SubTaskList)
        if response and response.completion:
            return response.completion.sub_tasks
        return []

    def run_sync(self) -> List[str]:
        """Synchronous wrapper for the run method."""
        return asyncio.run(self.run())
