from typing import Optional, TypedDict


class PromptEnhancerState(TypedDict):
    """State for the prompt enhancer workflow."""

    prompt: str  # Original prompt to enhance
    context: Optional[str]  # Additional context
    locale: Optional[str]  # Locale for the prompt
    output: Optional[str]  # Enhanced prompt result
