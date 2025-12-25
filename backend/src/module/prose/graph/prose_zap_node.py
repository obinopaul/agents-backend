import logging

from langchain_core.messages import HumanMessage, SystemMessage

from backend.src.llms.llm import get_llm
from backend.src.prompts.template import get_prompt_template
from backend.src.module.prose.graph.state import ProseState

logger = logging.getLogger(__name__)


def prose_zap_node(state: ProseState):
    logger.info("Generating prose zap content...")
    model = get_llm()
    prose_content = model.invoke(
        [
            SystemMessage(content=get_prompt_template("prose/prose_zap")),
            HumanMessage(content=state["content"]),
        ],
    )
    return {"output": prose_content.content}
