import logging

from langchain_core.messages import HumanMessage, SystemMessage

from backend.src.config.agents import AGENT_LLM_MAP
from backend.src.llms.llm import get_llm_by_type
from backend.src.prompts.template import get_prompt_template
from backend.src.prose.graph.state import ProseState

logger = logging.getLogger(__name__)


def prose_longer_node(state: ProseState):
    logger.info("Generating prose longer content...")
    model = get_llm_by_type(AGENT_LLM_MAP["prose_writer"])
    prose_content = model.invoke(
        [
            SystemMessage(content=get_prompt_template("prose/prose_longer")),
            HumanMessage(content=f"The existing text is: {state['content']}"),
        ],
    )
    logger.info(f"prose_content: {prose_content}")
    return {"output": prose_content.content}
